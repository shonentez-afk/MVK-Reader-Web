package main

// One full local integration cycle, not individual protocol microtests.
// Original Task2: operator Measure -> real TCP PARAM -> approved original
// 36-byte SetRate FIFO -> ADC/TACH -> WriteData and PARAM 0x3100 WriteValues
// -> clean stop -> unchanged RAW and fully referenced local writer files.
// The test never connects to a physical MVK01 and never includes private
// IDP/PAS/DFM/SQLite bytes. All commands are restricted to loopback.
import (
    "bytes"
    "context"
    "encoding/json"
    "io"
    "net"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestMode2WholeMeasurementStartToFinishOnOneTCPWithBothWriters(t *testing.T){
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil{t.Fatal(e)}
    defer ln.Close()
    root:=t.TempDir()
    run:=filepath.Join(root,"TEST_2026-11-16_10-01-00.000")
    m,e:=NewMonitor(run,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    c,e:=newFrameMarkController(root,run)
    if e!=nil{t.Fatal(e)}
    m.frameMarks=c
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceLiveDataWriter=newSourceLiveDataWriter(run)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(run)
    m.sourceTask2TX=newSourceLiveTask2TX()
    queueMark(t,c,1,"data_begin")
    queueMark(t,c,2,"values_begin")
    ctx,cancel:=context.WithTimeout(context.Background(),6*time.Second)
    defer cancel()
    payloadADC:=sourceLiveWriterSample(
        typeADC,0,65536,0,0x3f800000,0x40000000)
    payloadTach:=sourceLiveWriterSample(
        typeTach,8,65536,0,0x01020304,0x05060708)
    param3100:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
        Payload:[]byte{0x9A,0xBC,0xCD,0xEF}}})
    first:=task2Status0Param(0).Raw
    expectedRaw:=append(append(append(append(
        []byte{},first...),payloadADC...),payloadTach...),param3100...)
    expectedRate,_:=sourceSetRateWireBytes(65536)
    evidence:=make(chan []byte,1)
    errorsServer:=make(chan error,1)
    go func(){
        socket,err:=ln.Accept()
        if err!=nil{errorsServer<-err;return}
        defer socket.Close()
        _=socket.SetDeadline(time.Now().Add(5*time.Second))
        if _,err=socket.Write(first);err!=nil{errorsServer<-err;return}
        sent:=make([]byte,36)
        if _,err=io.ReadFull(socket,sent);err!=nil{
            errorsServer<-err;return
        }
        evidence<-sent
        for _,p:=range [][]byte{payloadADC,payloadTach,param3100}{
            if _,err=socket.Write(p);err!=nil{errorsServer<-err;return}
        }
        // After a complete packet burst a local operator STOP, not
        // the original 5s network ReadTimeout or remote EOF, ends Task2.
        // Keep this fake source socket alive until receiver notices STOP.
        time.Sleep(450*time.Millisecond)
        cancel()
        <-ctx.Done()
        time.Sleep(1200*time.Millisecond)
        errorsServer<-nil
    }()
    reason,e:=sourceTask2CaptureAddressRetry(
        ctx,m,ln.Addr().String(),0,4*1024*1024,nil)
    if e!=nil && reason!="STOPPED_BY_USER"{
        t.Fatalf("Task2 original integration %s: %v",reason,e)
    }
    if reason!="STOPPED_BY_USER"{
        t.Fatalf("operator STOP in full source chain: %s",reason)
    }
    select{
    case got:=<-evidence:
        if !bytes.Equal(got,expectedRate){
            t.Fatal("actual source SetRate not original 36-byte command")
        }
    default:t.Fatal("native TCP never sent its original Task2 SetRate")
    }
    report,_,e:=m.Finalize(reason)
    if e!=nil{t.Fatal(e)}
    original,e:=os.ReadFile(filepath.Join(run,"incoming.raw"))
    if e!=nil || !bytes.Equal(original,expectedRaw){
        t.Fatal("Source RX RAW differs from exact TCP bytes",e)
    }
    if report.SourceLiveWriteDataWindows!=1 ||
       report.SourceLiveValuesWindows!=1 ||
       report.SourceLiveValuesEventRecords!=1 ||
       report.SourceLiveWriteDataPacketRecords!=2 ||
       report.SourceSetRateBytes!=36 ||
       report.ReadOnly || report.ValuesTicks!=1 ||
       report.Channels[0].Samples!=2 ||
       report.Channels[8].Samples!=2 ||
       report.FrameMarkCount!=2 ||
       report.CaptureOnly || report.SourceTCPMultiSocket{
        t.Fatalf("Original end-to-end measurement receipt: %+v",report)
    }
    adcOut,e:=os.ReadFile(filepath.Join(run,
        "SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"))
    if e!=nil || !bytes.Equal(adcOut,payloadADC[28:]){
        t.Fatal("source WriteData gate lost original ADC bytes",e)
    }
    tachOut,e:=os.ReadFile(filepath.Join(run,
        "SOURCE_W01_TACH1_LIVE_RX_UNSCALED.bin"))
    if e!=nil || !bytes.Equal(tachOut,payloadTach[28:]){
        t.Fatal("source WriteData lost original TACH bytes",e)
    }
    valuesOut,e:=os.ReadFile(filepath.Join(run,
        "SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
    if e!=nil{t.Fatal(e)}
    var receipt sourceLiveValuesEvent
    if e=json.Unmarshal(bytes.TrimSpace(valuesOut),&receipt);e!=nil{t.Fatal(e)}
    if receipt.TickIndex!=0 ||
       receipt.ParamPayloadLEHex!="9abccdef" ||
       receipt.Address!="0x3100"{
        t.Fatalf("original WriteValues 0x3100 event not received: %+v",receipt)
    }
    for _,name:=range []string{
        sourceLiveWriterAudit,sourceLiveWriterPackets,
        sourceLiveValuesAuditName,frameMarkAuditName,
    }{
        if info,e:=os.Stat(filepath.Join(run,name));e!=nil||info.Size()==0{
            t.Fatalf("missing verified same-TCP lifecycle artifact %s: %v",name,e)
        }
    }
    select{
    case e:=<-errorsServer:
        if e!=nil{t.Fatal(e)}
    case <-time.After(4*time.Second):t.Fatal("fake source fixture timed out")
    }
}
