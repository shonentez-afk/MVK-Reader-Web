package main

// Source _Unit125 TMVKThread.Execute: at 008089A3..008089AD
// CloseFiles(00809414) runs after EVERY TCP connection, not only
// when the overall capture ends. A subsequent socket MUST use new
// independent WriteData and WriteValues windows.
//
// Purely synthetic local file and Source PARAM/ADC fixtures.
// No hardware commands or private vendor source bytes are shipped.
import (
    "bytes"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalTask2ClosesBothWritersPerSocketAndNeverMergesRawWindows(t *testing.T){
    m,marks:=markFixture(t)
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceTCP=&sourceTCPLedger{}
    m.sourceLiveDataWriter=newSourceLiveDataWriter(m.dir)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    now:=time.Now()
    runSocket:=func(first bool){
        t.Helper()
        if e:=m.sourceTCP.begin(m);e!=nil{t.Fatal(e)}
        n:=1
        if !first{n=3}
        queueMark(t,marks,n,"data_begin")
        queueMark(t,marks,n+1,"values_begin")
        if e:=m.ProcessChunk(task2Status0Param(0).Raw,now);e!=nil{t.Fatal(e)}
        adcVal:=uint32(0x3F800000)
        if !first{adcVal=0x40000000}
        frame:=sourceLiveWriterSample(typeADC,0,65536,0,adcVal)
        if e:=m.ProcessChunk(frame,now);e!=nil{t.Fatal(e)}
        values:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
            Payload:[]byte{byte(n),0,0,0}}})
        if e:=m.ProcessChunk(values,now);e!=nil{t.Fatal(e)}
        if m.sourceLiveDataWriter.active==nil ||
           m.sourceLiveValuesWriter.active==nil {
            t.Fatal("original source writers did not start")
        }
        reason:="SOURCE_INVALID_PACKET"
        if !first{reason="STOPPED_BY_USER"}
        m.sourceTCP.finish(m,reason)
        if m.sourceLiveDataWriter.active!=nil ||
           m.sourceLiveValuesWriter.active!=nil {
            t.Fatal("old socket writer survived original CloseFiles")
        }
        if m.sourceLiveDataWriter.windows[len(m.sourceLiveDataWriter.windows)-1].Outcome!=
          func()string{if first{return "SOURCE_SOCKET_SOURCE_INVALID_PACKET"};return "CLOSED_BY_SOURCE_THREAD"}() ||
           m.sourceLiveValuesWriter.windows[len(m.sourceLiveValuesWriter.windows)-1].Outcome!=
          func()string{if first{return "SOURCE_SOCKET_SOURCE_INVALID_PACKET"};return "CLOSED_BY_SOURCE_THREAD"}(){
            t.Fatal("original thread exit incorrectly labelled clean writer window")
        }
    }
    runSocket(true)
    runSocket(false)
    report,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    if report.SourceTCPConnectionCount!=2 ||
        !report.SourceTCPMultiSocket || !report.SourceTCPSegmentCopiesVerified ||
        report.SourceLiveWriteDataWindows!=2 ||
        report.SourceLiveValuesWindows!=2 ||
        report.SourceLiveValuesEventRecords!=2 ||
        m.captureOnly || report.InvalidFrames!=0 {
        t.Fatalf("per-socket source writer trace wrong: %+v",report)
    }
    for i,want:=range [][]byte{{0,0,0x80,0x3F},{0,0,0,0x40}}{
        path:=filepath.Join(m.dir,func()string{
            if i==0{return "SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"}
            return "SOURCE_W02_ADC1_LIVE_RX_UNSCALED.bin"
        }())
        got,e:=os.ReadFile(path)
        if e!=nil||!bytes.Equal(got,want){
            t.Fatalf("socket %d ADC file crossed a disconnect: %v",i+1,e)
        }
        valuesPath:=filepath.Join(m.dir,func()string{
            if i==0{return "SOURCE_W01_VALUES_3100_RECEIVED.jsonl"}
            return "SOURCE_W02_VALUES_3100_RECEIVED.jsonl"
        }())
        val,e:=os.ReadFile(valuesPath)
        if e!=nil || len(val)==0{
            t.Fatalf("source socket %d Values file missing: %v",i+1,e)
        }
    }
    if isSafeCaptureForExport(report)==nil{
        t.Fatal("separate source TCP writer windows incorrectly certified one BIN")
    }
}
