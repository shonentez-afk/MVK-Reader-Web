package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceLiveWriterSample(typ uint32,channel int,rate uint32,index uint32,words ...uint32)[]byte{
    raw:=make([]byte,28+4*len(words))
    binary.LittleEndian.PutUint32(raw[0:4],typ)
    binary.LittleEndian.PutUint32(raw[4:8],uint32(len(raw)))
    binary.LittleEndian.PutUint32(raw[12:16],index)
    binary.LittleEndian.PutUint32(raw[20:24],uint32(channel))
    binary.LittleEndian.PutUint32(raw[24:28],rate)
    for i,n:=range words {
        binary.LittleEndian.PutUint32(raw[28+i*4:],n)
    }
    return raw
}
func testLiveWriterMonitor(t *testing.T)(*Monitor,*frameMarkController){
    t.Helper()
    m,c:=markFixture(t)
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceLiveDataWriter=newSourceLiveDataWriter(m.dir)
    return m,c
}
func TestOriginalWriteDataFirstAcceptedADC1AndRealRateFreezeGate(t *testing.T){
    m,c:=testLiveWriterMonitor(t)
    now:=time.Now()
    push:=func(raw []byte){
        t.Helper()
        if e:=m.ProcessChunk(raw,now);e!=nil {t.Fatal(e)}
        now=now.Add(time.Millisecond)
    }
    // Before the operator selects WriteData, NO channel is written.
    push(sourceLiveWriterSample(typeADC,1,65536,0,0x42))
    queueMark(t,c,1,"data_begin")
    // Stage0: ADC2 and other channels do not start a writer.
    push(sourceLiveWriterSample(typeADC,1,65536,1,0x43))
    if w:=m.sourceLiveDataWriter.active;w==nil||w.stage!=0 {
        t.Fatal("original WriteData must wait for first accepted ADC1")
    }
    // The first ADC1 at the wrong Fs MUST NOT activate the writer.
    push(sourceLiveWriterSample(typeADC,0,8192,0,0x123))
    m.sourceOriginalRXGate.setFreeze(true)
    push(sourceLiveWriterSample(typeADC,0,65536,1,0x124))
    if m.sourceLiveDataWriter.active.stage!=0 {
        t.Fatal("rate/freeze rejected ADC1 may not activate WriteData")
    }
    m.sourceOriginalRXGate.setFreeze(false)
    adc1First:=sourceLiveWriterSample(typeADC,0,65536,2,0x3f800000,0x40000000)
    push(adc1First)
    if m.sourceLiveDataWriter.active.stage!=1 ||
       m.sourceLiveDataWriter.active.FirstAcceptedADC1Frame!=5 {
        t.Fatal("source Stage0 -> Stage1 did not happen on real ADC1 packet")
    }
    tach:=sourceLiveWriterSample(typeTach,8,65536,0,0x11223344,0x55667788)
    push(tach)
    adc2:=sourceLiveWriterSample(typeADC,1,65536,2,0x41400000)
    push(adc2)
    // A local RATE selection immediately changes original in-memory
    // MvkSampleRate independently of hardware ACK or the last packet.
    if e:=m.sourceOriginalRXGate.selectRate(8192);e!=nil{t.Fatal(e)}
    push(sourceLiveWriterSample(typeADC,0,65536,4,0xC0))
    adc1Second:=sourceLiveWriterSample(typeADC,0,8192,5,0x40400000)
    push(adc1Second)
    m.sourceOriginalRXGate.setFreeze(true)
    push(sourceLiveWriterSample(typeADC,0,8192,6,0xC1))
    m.sourceOriginalRXGate.setFreeze(false)
    // Real source closes BEFORE reading this next complete ADC1:
    // it must not accidentally append the stop-trigger packet.
    queueMark(t,c,2,"data_end")
    push(sourceLiveWriterSample(typeADC,0,8192,7,0xC2))
    if m.sourceLiveDataWriter.active!=nil {t.Fatal("source WriteData did not close before next frame")}
    summary,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil {t.Fatal(e)}
    if summary.SourceLiveWriteDataWindows!=1 ||
       summary.SourceLiveWriteDataPacketRecords!=9 ||
       len(summary.SourceLiveWriteDataAuditSHA256)!=64 || !summary.ReadOnly {
        t.Fatalf("source writer audit missing or fake hardware TX: %+v",summary)
    }
    adc1:=append(append([]byte{},adc1First[28:]...),adc1Second[28:]...)
    adc1Path:=filepath.Join(m.dir,"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin")
    adc2Path:=filepath.Join(m.dir,"SOURCE_W01_ADC2_LIVE_RX_UNSCALED.bin")
    tachPath:=filepath.Join(m.dir,"SOURCE_W01_TACH1_LIVE_RX_UNSCALED.bin")
    for _,pair:=range [][2]interface{}{
        {adc1Path,adc1},{adc2Path,adc2[28:]},{tachPath,tach[28:]},
    }{
        got,e:=os.ReadFile(pair[0].(string))
        if e!=nil || !bytes.Equal(got,pair[1].([]byte)) {
            t.Fatalf("source write byte parity %v: %v",pair[0],e)
        }
    }
    auditBytes,e:=os.ReadFile(filepath.Join(m.dir,sourceLiveWriterAudit))
    if e!=nil {t.Fatal(e)}
    sha:=sha256.Sum256(auditBytes)
    if hex.EncodeToString(sha[:])!=summary.SourceLiveWriteDataAuditSHA256 {
        t.Fatal("Go Native source writer receipt SHA mismatch")
    }
    var doc sourceLiveDataAudit
    if e=json.Unmarshal(auditBytes,&doc);e!=nil{t.Fatal(e)}
    if doc.OriginalDelphiByteParityVerified || doc.OperatorClickTimingParityVerified ||
       len(doc.Windows)!=1 || doc.Windows[0].StageAtEnd!=1 ||
       doc.Windows[0].Outcome!="CLOSED_BY_OPERATOR" ||
       doc.Windows[0].FirstAcceptedADC1Frame!=5 ||
       doc.Windows[0].SkippedBeforeADC1!=1 ||
       doc.Windows[0].SkippedRate!=2 ||
       doc.Windows[0].SkippedFrozen!=2 ||
       doc.Windows[0].WrittenPackets!=4 {
        t.Fatalf("source packet gate/rate/freeze not original: %+v",doc.Windows)
    }
    gate,e:=os.ReadFile(filepath.Join(m.dir,sourceLiveWriterPackets))
    if e!=nil{t.Fatal(e)}
    packetSHA:=sha256.Sum256(gate)
    if hex.EncodeToString(packetSHA[:])!=doc.PacketGateSHA256 {
        t.Fatal("source packet gate was not SHA-audited")
    }
    if !bytes.Contains(gate,[]byte(`"freeze_update":true`)) ||
       !bytes.Contains(gate,[]byte(`"wrote_source_bytes":false`)) {
        t.Fatal("source recording gate audit omits frozen/rejected samples")
    }
}
func TestOriginalWriteDataThreadStopClosesOnlyCleanSource(t *testing.T){
    for _,tc:=range []struct{reason,outcome string}{
        {"STOPPED_BY_USER","CLOSED_BY_SOURCE_THREAD"},
        {"REMOTE_DISCONNECTED","INTERRUPTED"},
    }{
        t.Run(tc.reason,func(t *testing.T){
            m,c:=testLiveWriterMonitor(t)
            queueMark(t,c,1,"data_begin")
            data:=sourceLiveWriterSample(typeADC,0,65536,0,0x3f800000)
            if e:=m.ProcessChunk(data,time.Now());e!=nil{t.Fatal(e)}
            _,_,e:=m.Finalize(tc.reason)
            if e!=nil{t.Fatal(e)}
            raw,e:=os.ReadFile(filepath.Join(m.dir,"incoming.raw"))
            if e!=nil||!bytes.Equal(raw,data){t.Fatal("RAW changed by live writer",e)}
            payload,e:=os.ReadFile(filepath.Join(m.dir,
                "SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"))
            if e!=nil||!bytes.Equal(payload,data[28:]){
                t.Fatal("writer failed to close its true local file",e)
            }
            b,e:=os.ReadFile(filepath.Join(m.dir,sourceLiveWriterAudit))
            if e!=nil{t.Fatal(e)}
            var doc sourceLiveDataAudit
            if e=json.Unmarshal(b,&doc);e!=nil{t.Fatal(e)}
            if len(doc.Windows)!=1 || doc.Windows[0].Outcome!=tc.outcome ||
                doc.Windows[0].EndAfterFrame!=1 {
                t.Fatalf("source thread close outcome false: %+v",doc.Windows)
            }
        })
    }
}
