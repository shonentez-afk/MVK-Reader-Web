package main

// Source-backed acceptance: original Task2 framing, register image,
// 8 ADC + 2 TACH, rate/freeze gate, both local source writers, RAW and STOP.
// Offline synthetic frames ONLY. Not physical Delphi 1:1 parity.
import (
 "bytes"
 "crypto/sha256"
 "encoding/binary"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "testing"
 "time"
)

func TestMode2OriginalReceiveAlgorithmTenChannelsFragmentedToStop(t *testing.T) {
 m,marks:=markFixture(t)
 defer m.CloseFiles()
 m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
 m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
 m.sourceLiveDataWriter=newSourceLiveDataWriter(m.dir)
 m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
 m.sourceOriginalTask2Stage.onConnected(0)
 now:=time.Date(2026,11,18,8,0,0,0,time.UTC)
 expected:=make([]byte,0,16384)
 sizes:=[]int{1,2,3,5,7,11,17}
 push:=func(frame []byte){
  t.Helper()
  expected=append(expected,frame...)
  for start,i:=0,0;start<len(frame);i++{
   end:=start+sizes[i%len(sizes)]
   if end>len(frame){end=len(frame)}
   if e:=m.ProcessChunk(frame[start:end],now);e!=nil{
    t.Fatalf("fragment %d..%d: %v",start,end,e)
   }
   now=now.Add(time.Millisecond);start=end
  }
 }
 push(task2Status0Param(0).Raw)
 if m.sourceOriginalTask2Stage.stage!=1 || !m.summary.ReadOnly {
  t.Fatal("Task2 must enter Stage1 only after a true nonempty PARAM")
 }
 queueMark(t,marks,1,"data_begin")
 queueMark(t,marks,2,"values_begin")
 unknown:=make([]byte,12)
 binary.LittleEndian.PutUint32(unknown[:4],0x12345678)
 binary.LittleEndian.PutUint32(unknown[4:8],12)
 binary.LittleEndian.PutUint32(unknown[8:12],0xAABBCCDD)
 push(unknown)
 push(sourceStageTestReply(typeAck)) // unsolicited ACK is not a paired TX
 push(sourceLiveWriterSample(typeADC,0,65536,0)) // empty packet
 push(sourceLiveWriterSample(typeADC,1,65536,0,0x3F000000))
 push(sourceLiveWriterSample(typeADC,0,8192,0,0x3F200000))
 m.sourceOriginalRXGate.setFreeze(true)
 push(sourceLiveWriterSample(typeADC,0,65536,1,0x3F400000))
 m.sourceOriginalRXGate.setFreeze(false)
 firstADC1:=sourceLiveWriterSample(typeADC,0,65536,2,0x3F800000,0x40000000)
 push(firstADC1)
 wanted:=map[int][]byte{0:firstADC1[28:]}
 for ch:=1;ch<8;ch++{
  idx:=uint32(0);if ch==1{idx=1}
  f:=sourceLiveWriterSample(typeADC,ch,65536,idx,0x3F800000+uint32(ch))
  push(f);wanted[ch]=f[28:]
 }
 for ch:=8;ch<10;ch++{
  f:=sourceLiveWriterSample(typeTach,ch,65536,0,0x01020304+uint32(ch),0x05060708+uint32(ch))
  push(f);wanted[ch]=f[28:]
 }
 push(makeAux())
 if m.summary.ValuesTicks!=0 || m.sourceLiveValuesWriter.events!=0 {
  t.Fatal("AUX4700 is not an original WriteValues 0x3100 trigger")
 }
 tick:=makeParam([]RegBlock{{Addr:0x3100,Words:2,Payload:[]byte{0x9A,0xBC,0xCD,0xEF}}})
 push(tick)
 queueMark(t,marks,3,"data_end")
 queueMark(t,marks,4,"values_end")
 push(makeIdentity())
 if m.sourceLiveDataWriter.active!=nil || m.sourceLiveValuesWriter.active!=nil {
  t.Fatal("writer end did not close before the next complete frame")
 }
 m.sourceOriginalTask2Stage.onDisconnected("STOPPED_BY_USER")
 summary,_,e:=m.Finalize("STOPPED_BY_USER")
 if e!=nil{t.Fatal(e)}
 actual,e:=os.ReadFile(filepath.Join(m.dir,"incoming.raw"))
 if e!=nil || !bytes.Equal(actual,expected){t.Fatalf("RAW changed: %v",e)}
 sha:=sha256.Sum256(expected)
 if summary.RawSHA256!=hex.EncodeToString(sha[:]){t.Fatal("RAW SHA mismatch")}
 if summary.CaptureOnly || summary.InvalidFrames!=0 || !summary.ReadOnly ||
  summary.SourceSetRateBytes!=0 || summary.SourceLiveWriteDataWindows!=1 ||
  summary.SourceLiveValuesWindows!=1 || summary.SourceLiveValuesEventRecords!=1 ||
  summary.SourceLiveWriteDataPacketRecords!=13 || summary.ValuesTicks!=1 ||
  summary.Aux4700!=1 || summary.FrameMarkCount!=4 || len(marks.records)!=4 ||
  summary.TailBytes!=0{
   t.Fatalf("original receive path failed: %+v",summary)
 }
 if summary.Channels[0].Samples!=4 || summary.Channels[1].Samples!=2 ||
  summary.Channels[8].Samples!=2 || summary.Channels[9].Samples!=2 {
   t.Fatal("source 8 ADC / 2 TACH counters mismatch")
 }
 if m.sourceOriginalTask2Stage.stage!=0 || m.sourceOriginalTask2Stage.lastLiveStage!=1 {
  t.Fatal("Task2 original Stage1 -> Stage0 stop incorrect")
 }
 ring:=m.sourceOriginalStorage.receipt()
 if len(ring.Channels)!=10 || ring.Channels[0].RxPos!=2 ||
   ring.Channels[1].RxPos!=2 || ring.Channels[8].RxPos!=8 ||
   ring.Channels[9].RxPos!=8 {
  t.Fatal("original ring ADC Float32 / TACH Byte width or gate mismatch")
 }
 gate:=m.sourceOriginalRXGate.receipt()
 if gate.Channels[0].RateSkippedElements!=1 ||
  gate.Channels[0].FrozenSkippedElements!=1 ||
  gate.Channels[0].StoredGateElements!=2 {
  t.Fatal("original Fs/Freeze acceptance mismatch")
 }
 for ch:=0;ch<10;ch++ {
  kind,index:="ADC",ch+1
  if ch>=8{kind,index="TACH",ch-7}
  path:=filepath.Join(m.dir,fmt.Sprintf("SOURCE_W01_%s%d_LIVE_RX_UNSCALED.bin",kind,index))
  payload,e:=os.ReadFile(path)
  if e!=nil || !bytes.Equal(payload,wanted[ch]){
   t.Fatalf("source byte mismatch %s: %v",path,e)
  }
 }
 file,e:=os.ReadFile(filepath.Join(m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
 if e!=nil{t.Fatal(e)}
 var value sourceLiveValuesEvent
 if e=json.Unmarshal(bytes.TrimSpace(file),&value);e!=nil{t.Fatal(e)}
 if value.Address!="0x3100" || value.PayloadLEHex!="9abccdef" ||
  value.TickIndex!=0 || value.Words!=2 {t.Fatalf("PARAM source mismatch %+v",value)}
 if len(summary.SourceLiveWriteDataAuditSHA256)!=64 ||
  len(summary.SourceLiveValuesAuditSHA256)!=64 {
  t.Fatal("source writers require independent SHA audits")
 }
}

func TestMode2OriginalReceiveMalformedLengthPreservesRAWButNeverInventsADC(t *testing.T){
 m,_:=markFixture(t)
 defer m.CloseFiles()
 m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
 m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
 m.sourceOriginalTask2Stage.onConnected(0)
 start:=task2Status0Param(0).Raw
 bad:=make([]byte,8)
 binary.LittleEndian.PutUint32(bad[:4],typeADC)
 binary.LittleEndian.PutUint32(bad[4:8],10)
 after:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000)
 all:=append(append(append([]byte{},start...),bad...),after...)
 now:=time.Now()
 // The OS TCP read can already contain bytes AFTER the invalid
 // application envelope. Save them ALL in RAW, but NEVER decode them:
 // the original Task2 socket raises immediately at that bad length.
 e:=m.ProcessChunk(all,now)
 if !errors.Is(e,errTask2SourceInvalidPacket){
  t.Fatalf("invalid original Task2 header must abort socket: %v",e)
 }
 m.sourceOriginalTask2Stage.onDisconnected("SOURCE_INVALID_PACKET")
 summary,_,e:=m.Finalize("SOURCE_INVALID_PACKET")
 if e!=nil{t.Fatal(e)}
 raw,e:=os.ReadFile(filepath.Join(m.dir,"incoming.raw"))
 if e!=nil || !bytes.Equal(raw,all){t.Fatalf("broken frame RAW loss: %v",e)}
 if !summary.CaptureOnly || summary.InvalidFrames!=1 || summary.SourceTask2ProtocolExceptions!=1 ||
  summary.Channels[0].Samples!=0 || summary.SourceLiveWriteDataWindows!=0 ||
  summary.RawBytes!=uint64(len(all)) || !summary.ReadOnly {
  t.Fatalf("malformed bytes misreported as ADC: %+v",summary)
 }
}
