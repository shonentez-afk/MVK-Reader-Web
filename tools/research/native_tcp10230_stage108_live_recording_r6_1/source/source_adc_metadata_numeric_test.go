package main

import (
 "bytes"
 "encoding/binary"
 "encoding/json"
 "math"
 "os"
 "path/filepath"
 "testing"
 "time"
)

func TestSourceMetadataNumericalCoreFixture(t *testing.T){
 root:=os.Getenv("MVK_RANGE_FIXTURE_DIR")
 if root==""{root=t.TempDir()}
 run:=filepath.Join(root,"TEST_2026-11-24_10-00-00.000")
 m,e:=NewMonitor(run,"OFFLINE_REPLAY","192.0.2.84");if e!=nil{t.Fatal(e)}
 defer m.CloseFiles()
 m.liveProgressEnabled=true
 m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
 m.sourceContract=newSourceMetadataLatchCandidate()
 m.sourceContract.newSocket()
 m.syncSourceADCMetadata()
 m.sourceParamGate,e=newSourceOriginalParamGateJournal(run);if e!=nil{t.Fatal(e)}
 m.sourceTachGate,e=newSourceTachGateJournal(run);if e!=nil{t.Fatal(e)}
 marks,e:=newFrameMarkController(root,run);if e!=nil{t.Fatal(e)}
 m.frameMarks=marks
 m.sourceLiveDataWriter=newSourceLiveDataWriter(run)
 now:=time.Now().UTC()
 wire:=[]byte{}
 push:=func(frame []byte){
  t.Helper()
  wire=append(wire,frame...)
  if err:=m.ProcessChunk(frame,now);err!=nil{t.Fatal(err)}
  if m.captureOnly{t.Fatal("unexpected parser/writer rejection")}
 }
 config:=func(f float32,unit byte)RegBlock{
  return RegBlock{Addr:0x10e,Words:4,Payload:append(sourceRawTestWords(math.Float32bits(f)),[]byte{unit,0,0,0}...)}
 }
 push(sourceLiveWriterSample(typeADC,0,65536,0,math.Float32bits(2),math.Float32bits(-2),math.Float32bits(1),0))
 stale:=m.sourceOriginalStorage.channels[0].metadata
 push(makeParam([]RegBlock{config(4,'V'),config(9,'A')}))
 if got:=m.sourceOriginalStorage.channels[0].metadata;got.factor()!=4 || got.Units!="V" || !got.FromDescriptor || sameSourceADCMetadata(stale,got){t.Fatal("first descriptor range/unit identity",got)}
 var channels [10]bool;channels[0]=true
 var spec [43]bool
 var values [73]bool
 sourceSelectedMark(t,marks,m,1,"data_begin",channels,spec,values)
 bits:=make([]uint32,2048)
 for i:=range bits{bits[i]=math.Float32bits([]float32{1,0,-1,0}[i%4])}
 frame:=sourceLiveWriterSample(typeADC,0,65536,4,bits...)
 push(frame)
 m.sourceOriginalRXGate.setFreeze(true)
 push(makeParam([]RegBlock{config(12,'X')}))
 m.sourceOriginalRXGate.setFreeze(false)
 sourceSelectedMark(t,marks,m,2,"data_end",channels,spec,values)
 // Close occurs before this following PARAM; its later metadata must not leak.
 push(makeParam([]RegBlock{config(16,'Z')}))
 ring:=m.sourceOriginalStorage
 data,e:=ring.window(0,0,2052);if e!=nil{t.Fatal(e)}
 if binary.LittleEndian.Uint32(data[:4])!=math.Float32bits(2) ||
  binary.LittleEndian.Uint32(data[16:20])!=math.Float32bits(4) ||
  binary.LittleEndian.Uint32(data[24:28])!=math.Float32bits(-4){t.Fatal("range not applied exactly once or older data rewritten")}
 c:=&ring.channels[0]
 req:=sourceLongWindowRequest{Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(run),
  RequestID:"00000000000000000000000000000001",ADC:1,HTag:-1,Samples:1024,
  CaptureEnd:c.rxPos,SampleRateHz:65536,DeviceEnd:c.nextDeviceIndex,Metadata:stale}
 writeReq:=func(r sourceLongWindowRequest){
  t.Helper();raw,e:=json.Marshal(r);if e!=nil{t.Fatal(e)}
  if e=os.WriteFile(filepath.Join(run,sourceLongWindowRequestName),raw,0600);e!=nil{t.Fatal(e)}
 }
 writeReq(req)
 if e=m.handleSourceLongWindowRequest(now);e==nil{t.Fatal("stale pre-PARAM identity accepted")}
 req.RequestID="00000000000000000000000000000002"
 req.Metadata=c.metadata
 writeReq(req)
 if e=m.handleSourceLongWindowRequest(now);e!=nil{t.Fatal(e)}
 if e=os.WriteFile(filepath.Join(run,"FIXTURE_FFT.zip"),prefixTestRead(t,run,sourceLongWindowResultName),0600);e!=nil{t.Fatal(e)}
 req.RequestID="00000000000000000000000000000003"
 req.HTag=-3;req.EnvelopeCode=20;req.OriginalHTag=9
 req.Samples=1361
 writeReq(req)
 if e=m.handleSourceLongWindowRequest(now);e!=nil{t.Fatal(e)}
 if e=os.WriteFile(filepath.Join(run,"FIXTURE_FIR.zip"),prefixTestRead(t,run,sourceLongWindowResultName),0600);e!=nil{t.Fatal(e)}
 live:=m.snapshotLiveStatus("RECORDING",now)
 status,e:=json.Marshal(live);if e!=nil{t.Fatal(e)}
 if e=os.WriteFile(filepath.Join(run,"FIXTURE_STATUS.json"),status,0600);e!=nil{t.Fatal(e)}
 result,_,e:=m.Finalize("STOPPED_BY_USER");if e!=nil{t.Fatal(e)}
 if result.CaptureOnly || result.RawSHA256!=prefixTestSHA(wire) || !bytes.Equal(prefixTestRead(t,run,"incoming.raw"),wire){t.Fatal("RAW changed")}
 if !bytes.Equal(prefixTestRead(t,run,"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"),frame[28:]){t.Fatal("source WriteData got scaled instead of wire bytes")}
 if result.SourceMetadataObservation==nil || !result.SourceMetadataObservation.NumericScalingApplied || *result.SourceMetadataObservation.ADC[0].RangeFactor!=4{t.Fatal("incorrect range receipt")}
}

func TestSourceMetadataNumericalExceptionalAndZero(t *testing.T){
 for _,tc:=range []struct{name string;addr uint16;bits uint32;sample float32;want float32;reject bool}{
  {"zero",0x10e,0,2,2,false},
  {"unknown",0x3100,0,2,0,true},
  {"nan",0x10e,0x7fc00000,2,0,true},
  {"negative",0x10e,math.Float32bits(-2),2,0,true},
  {"overflow",0x10e,math.Float32bits(math.MaxFloat32),2,0,true},
 }{
  t.Run(tc.name,func(t *testing.T){
   m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST"),"OFFLINE_REPLAY","192.0.2.84");if e!=nil{t.Fatal(e)}
   defer m.CloseFiles()
   m.sourceContract=newSourceMetadataLatchCandidate();m.sourceContract.newSocket()
   m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
   at:=time.Now()
   if e=m.ProcessChunk(makeParam([]RegBlock{prefixTestBlock(tc.addr,tc.bits)}),at);e!=nil{t.Fatal(e)}
   wire:=sourceLiveWriterSample(typeADC,0,65536,0,math.Float32bits(tc.sample))
   if e=m.ProcessChunk(wire,at);e!=nil{t.Fatal(e)}
   c:=m.sourceOriginalStorage.channels[0]
   if tc.reject{
    if c.rxPos!=0 || c.rejectedScalingElements!=1 || m.captureOnly{t.Fatal("exceptional input not safely refused")}
   }else{
    data,e:=m.sourceOriginalStorage.window(0,0,1);if e!=nil{t.Fatal(e)}
    if math.Float32frombits(binary.LittleEndian.Uint32(data))!=tc.want{t.Fatal("zero fallback wrong")}
   }
  })
 }
}
