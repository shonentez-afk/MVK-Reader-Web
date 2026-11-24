package main

// Entire real GUI Stop-file control path with one synthetic loopback socket.
// The same original-shaped RX feeds the ADC ring, local source WriteData,
// PARAM 0x3100 WriteValues, Task2 SetRate and the immutable RAW ledger.
// NO MVK01, no original Win32 EXE, no private Pascal/IDP/SQLite/PCAP data.
// Checks operator Stop -> context cancellation -> forced file close -> EOF,
// not just a unit-test call to Monitor.Finalize("STOPPED_BY_USER").
import (
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "io"
    "net"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalQtStopFileEndsSameSocketAndClosesWriteDataWriteValues(t *testing.T) {
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil{t.Fatal(e)}
    defer ln.Close()

    root:=t.TempDir()
    run:=filepath.Join(root,"TEST_2026-11-23_09-32-00.000")
    m,e:=NewMonitor(run,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    marks,e:=newFrameMarkController(root,run)
    if e!=nil{t.Fatal(e)}
    m.frameMarks=marks
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.sourceLiveDataWriter=newSourceLiveDataWriter(run)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(run)
    m.sourceTCP=&sourceTCPLedger{}
    m.sourceOperatorRateChan=make(chan string,1) // no stdin or hardware
    m.liveProgressEnabled=true
    mode2QueueMark(t,marks,run,1,"data_begin")
    mode2QueueMark(t,marks,run,2,"values_begin")

    // Same source RAW with one PARAM 0x3100 row strictly BETWEEN ADC frames.
    first:=task2Status0Param(0).Raw
    // The same socket carries two updates surrounding the VALUES trigger.
    // The final register image must be 3, while the saved SPEC row is 2.
    values:=makeParam([]RegBlock{
        {Addr:0x2002,Words:2,Payload:sourceRawTestWords(0x40000000)},
        {Addr:0x3100,Words:2,Payload:[]byte{0x11,0x22,0x33,0x44}},
        {Addr:0x2002,Words:2,Payload:sourceRawTestWords(0x40400000)},
    })
    frames:=make([][]byte,0,7)
    wire:=append([]byte{},first...)
    expectedADC:=make([]byte,0,1536*4)
    for i:=0;i<6;i++ {
        frame:=syntheticFrame(0,uint32(i*256),float32(i+1)*0.125).Raw
        frames=append(frames,frame)
        expectedADC=append(expectedADC,frame[28:]...)
        wire=append(wire,frame...)
        if i==0 {
            frames=append(frames,values)
            wire=append(wire,values...)
        }
    }
    stopPath:=filepath.Join(root,stopRequestName)
    if e=validateStopRequestPath(stopPath);e!=nil{t.Fatal(e)}
    ctx,cancel:=context.WithCancel(context.Background())
    defer cancel()
    go watchStopRequest(ctx,stopPath,cancel)

    senderResult:=make(chan error,1)
    go func(){
        socket,err:=ln.Accept()
        if err!=nil{senderResult<-err;return}
        defer socket.Close()
        _=socket.SetDeadline(time.Now().Add(18*time.Second))
        if _,err=socket.Write(first);err!=nil{senderResult<-err;return}
        sent:=make([]byte,sourceSetRateWriteLen)
        if _,err=io.ReadFull(socket,sent);err!=nil{senderResult<-err;return}
        expected,makeErr:=sourceSetRateWireBytes(65536)
        if makeErr!=nil || !bytes.Equal(expected,sent) {
            senderResult<-errors.New("original SetRate(65536) request changed")
            return
        }
        for _,frame:=range frames {
            if _,err=socket.Write(frame);err!=nil{senderResult<-err;return}
        }
        <-ctx.Done()
        senderResult<-nil
    }()

    stopIssued:=make(chan error,1)
    go func(){
        deadline:=time.Now().Add(12*time.Second)
        err:=mode2WaitForSourceReceiver(run,1536,deadline)
        if err==nil {
            // Real Qt writes this exact regular file; watcher alone
            // cancels capture without any extra TCP command.
            err=os.WriteFile(stopPath,[]byte("STOP\n"),0600)
        }else{
            cancel()
        }
        stopIssued<-err
    }()

    reason,runErr:=sourceTask2CaptureAddressRetry(
        ctx,m,ln.Addr().String(),0,4*1024*1024,nil)
    if stopErr:=<-stopIssued;stopErr!=nil{t.Fatal(stopErr)}
    if reason!="STOPPED_BY_USER" || runErr!=nil {
        t.Fatalf("Qt Stop request did not stop original-shaped Task2: %s %v",reason,runErr)
    }
    if senderErr:=<-senderResult;senderErr!=nil{t.Fatal(senderErr)}
    if m.sourceTCP.Active!=0 || m.sourceLiveDataWriter.active!=nil ||
        m.sourceLiveValuesWriter.active!=nil {
        t.Fatal("Task2 socket/WriteData/WriteValues still open after Stop")
    }
    summary,_,err:=m.Finalize(reason)
    if err!=nil{t.Fatal(err)}
    raw,err:=os.ReadFile(filepath.Join(run,"incoming.raw"))
    if err!=nil || !bytes.Equal(raw,wire) {
        t.Fatal("Stop changed/shortened complete original source RAW")
    }
    digest:=sha256.Sum256(wire)
    if summary.RawSHA256!=hex.EncodeToString(digest[:]) ||
        summary.EndReason!="STOPPED_BY_USER" ||
        summary.SourceTCPConnectionCount!=1 || summary.SourceTCPMultiSocket ||
        summary.SourceSetRateCount!=1 || summary.SourceSetRateBytes!=36 ||
        summary.SourceLiveWriteDataWindows!=1 ||
        summary.SourceLiveValuesWindows!=1 ||
        summary.SourceLiveValuesEventRecords!=1 ||
        summary.Channels[0].Samples!=1536 ||
        summary.InvalidFrames!=0 || summary.Denials!=0 || summary.CaptureOnly {
        t.Fatalf("Stop/source-file summary differs from same RAW: %+v",summary)
    }
    adc,err:=os.ReadFile(filepath.Join(run,"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"))
    if err!=nil || !bytes.Equal(adc,expectedADC) {
        t.Fatal("WriteData changed accepted ADC1 packets after operator Stop")
    }
    row,err:=os.ReadFile(filepath.Join(run,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
    if err!=nil{t.Fatal(err)}
    var received sourceLiveValuesEvent
    if err=json.Unmarshal(bytes.TrimSpace(row),&received);err!=nil{t.Fatal(err)}
    if received.Address!="0x3100" || received.PayloadLEHex!="11223344" {
        t.Fatalf("WriteValues event not tied to source PARAM register: %+v",received)
    }
    if received.RawTickEvidence==nil || len(received.RawTickEvidence.OrderedFields)==0{
        t.Fatal("Stop lost VALUES prefix snapshot")
    }
    spec:=received.RawTickEvidence.OrderedFields[0]
    if spec.Channel!=1 || spec.Group!="SPEC" || spec.CellIndex!=0 ||
        spec.RawLE==nil || *spec.RawLE!="00000040" {
        t.Fatalf("same socket VALUES used post-trigger suffix: %+v",spec)
    }
    for _,name:=range []string{
        sourceLiveWriterAudit,sourceLiveValuesAuditName,
        sourceLiveWriterPackets,frameMarkAuditName,
        "SOURCE_TCP_SEGMENT_0001.raw",
    }{
        info,statErr:=os.Stat(filepath.Join(run,name))
        if statErr!=nil || info.Size()==0 {
            t.Fatalf("Stop did not finalize original writer audit %s: %v",name,statErr)
        }
    }
    var dataDoc sourceLiveDataAudit
    dataBytes,err:=os.ReadFile(filepath.Join(run,sourceLiveWriterAudit))
    if err!=nil{t.Fatal(err)}
    if err=json.Unmarshal(dataBytes,&dataDoc);err!=nil{t.Fatal(err)}
    if len(dataDoc.Windows)!=1 ||
        dataDoc.Windows[0].Outcome!="CLOSED_BY_SOURCE_THREAD" ||
        dataDoc.Windows[0].StageAtEnd!=1 {
        t.Fatalf("WriteData unexpected close: reason=%s, outcome=%s, stage=%d",
            summary.EndReason,dataDoc.Windows[0].Outcome,
            dataDoc.Windows[0].StageAtEnd)
    }
    var valuesDoc sourceLiveValuesAudit
    valueBytes,err:=os.ReadFile(filepath.Join(run,sourceLiveValuesAuditName))
    if err!=nil{t.Fatal(err)}
    if err=json.Unmarshal(valueBytes,&valuesDoc);err!=nil{t.Fatal(err)}
    if len(valuesDoc.Windows)!=1 ||
        valuesDoc.Windows[0].Outcome!="CLOSED_BY_SOURCE_THREAD" {
        t.Fatal("WriteValues not force-closed after Qt Stop")
    }
}
