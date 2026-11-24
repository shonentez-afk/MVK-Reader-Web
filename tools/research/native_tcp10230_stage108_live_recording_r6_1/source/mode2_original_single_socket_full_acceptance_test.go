package main

// Unified original Mode2 acceptance. Every TCP byte in this test uses a
// synthetic loopback source, NEVER an industrial network. The original
// Pascal/DFM, IDP, SQLite and private PCAP data stay outside GitHub.
// Exercises ONE connection and ONE original Go 2^21 ADC ring from:
// IP -> Measure/Task2 -> SetRate -> 8 ADC/2 TACH/PARAM ->
// exact GetSignal and GetSpectrum source windows -> both writers -> Stop.
import (
    "archive/zip"
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "encoding/binary"
    "fmt"
    "io"
    "math"
    "net"
    "os"
    "path/filepath"
    "testing"
    "time"
)

type mode2WindowProof struct {
    receipt sourceLongWindowResult
    source []byte
}

func mode2ReadActualWindow(path string) (mode2WindowProof,error) {
    z,e:=zip.OpenReader(path)
    if e!=nil{return mode2WindowProof{},e}
    defer z.Close()
    proof:=mode2WindowProof{}
    foundManifest,foundADC:=false,false
    for _,file:=range z.File {
        reader,e:=file.Open()
        if e!=nil{return proof,e}
        payload,e:=io.ReadAll(reader)
        reader.Close()
        if e!=nil{return proof,e}
        switch file.Name {
        case "MANIFEST.json":
            if e=json.Unmarshal(payload,&proof.receipt);e!=nil{return proof,e}
            foundManifest=true
        case "ADC1.f32":
            if file.Method!=zip.Store{return proof,fmt.Errorf("source original Float32 unexpectedly compressed")}
            proof.source=payload
            foundADC=true
        default:
            return proof,fmt.Errorf("unknown source GetSignal window member %s",file.Name)
        }
    }
    if !foundManifest || !foundADC || len(z.File)!=2 {
        return proof,fmt.Errorf("incomplete source window ZIP")
    }
    digest:=sha256.Sum256(proof.source)
    if proof.receipt.SHA256!=hex.EncodeToString(digest[:]) {
        return proof,fmt.Errorf("source Go window SHA does not match its bytes")
    }
    return proof,nil
}

func mode2WaitForSourceReceiver(run string,want uint64,deadline time.Time)error{
    for time.Now().Before(deadline){
        raw,e:=os.ReadFile(filepath.Join(run,liveStatusName))
        if e==nil{
            var status LiveStatus
            if json.Unmarshal(raw,&status)==nil &&
                status.Phase=="RECORDING" &&
                status.SourceOriginalStorage!=nil &&
                len(status.SourceOriginalStorage.Channels)==10 &&
                status.SourceOriginalStorage.Channels[0].RxPos==want &&
                sourceIsLiveADC(status.SourceOriginalStorage.Channels[0].Domain) &&
                status.SourceOriginalStorage.Channels[0].OriginalLiveFRangeSingle!=nil &&
                status.SourceOriginalReceiveGate!=nil &&
                status.SourceOriginalReceiveGate.Channels[0].StoredGateElements==want &&
                status.SourceTCPConnectionCount==1 &&
                !status.SourceTCPMultiSocket {
                return nil
            }
        }
        time.Sleep(30*time.Millisecond)
    }
    return fmt.Errorf("one-socket original ring/status never reached %d",want)
}

func mode2WaitForWindow(run,id string,deadline time.Time)(mode2WindowProof,error){
    for time.Now().Before(deadline){
        proof,e:=mode2ReadActualWindow(filepath.Join(run,sourceLongWindowResultName))
        if e==nil && proof.receipt.RequestID==id {return proof,nil}
        time.Sleep(30*time.Millisecond)
    }
    return mode2WindowProof{},fmt.Errorf("source Go did not serve local window %s",id)
}

func mode2WriteSourceWindowRequest(run string,id string,hTag int,count uint32,end uint64)error{
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(run),
        RequestID:id,ADC:1,HTag:hTag,Samples:count,
        CaptureEnd:end,SampleRateHz:65536,DeviceEnd:uint32(end),
    }
    raw,e:=os.ReadFile(filepath.Join(run,liveStatusName))
    if e!=nil{return e}
    var status LiveStatus
    if e=json.Unmarshal(raw,&status);e!=nil{return e}
    if status.SourceOriginalStorage==nil{return fmt.Errorf("missing original range state")}
    req.SourceRangeState=status.SourceOriginalStorage.Channels[0].SourceRangeState
    if req.SourceRangeState==nil{return fmt.Errorf("missing latched range state")}
    content,e:=json.Marshal(req)
    if e!=nil{return e}
    return os.WriteFile(filepath.Join(run,sourceLongWindowRequestName),content,0600)
}

// Unlike older fixtures, this test must use its OWN run identity.
func mode2QueueMark(t *testing.T,c *frameMarkController,run string,seq int,event string){
    t.Helper()
    channels:=make([]bool,10)
    spec:=make([]bool,43)
    values:=make([]bool,73)
    for i:=range channels{channels[i]=true}
    for i:=range spec{spec[i]=true}
    for i:=range values{values[i]=true}
    req:=frameMarkRequest{
        Schema:frameMarkRequestSchema,Sequence:seq,SessionID:filepath.Base(run),
        Event:event,RequestedUTC:"2026-11-19T12:00:00Z",
        Channels:channels,Spec:spec,Values:values,
    }
    body,e:=json.Marshal(req)
    if e!=nil{t.Fatal(e)}
    if e=os.WriteFile(filepath.Join(c.inbox,fmt.Sprintf("%04d.json",seq)),body,0600);e!=nil{
        t.Fatal(e)
    }
}

func TestMode2OneRealLoopbackSocketSignalSpectrumWritersStopSourceProof(t *testing.T){
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil{t.Fatal(e)}
    defer ln.Close()
    root:=t.TempDir()
    run:=filepath.Join(root,"TEST_2026-11-19_15-00-00.000")
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
    m.sourceOperatorRateChan=make(chan string,1) // no stdin/hardware listener
    m.liveProgressEnabled=true
    mode2QueueMark(t,marks,run,1,"data_begin")
    mode2QueueMark(t,marks,run,2,"values_begin")

    // First descriptor includes ADC1 range, units and system Status0.
    // Stage0->1 must see 2.5; later PARAM may alter configuration
    // without altering the already-latched live storage range.
    config:=make([]byte,(0x1008-0x10e)*2)
    binary.LittleEndian.PutUint32(config,math.Float32bits(2.5))
    copy(config[4:],[]byte("m/s2"))
    first:=makeParam([]RegBlock{{Addr:0x10e,Words:uint16(len(config)/2),Payload:config}})
    wire:=append([]byte{},first...)
    accepted:=make([]byte,0,1536*4)
    burst:=make([][]byte,0,17)
    for i:=0;i<6;i++{
        frame:=syntheticFrame(0,uint32(i*256),float32(i+1)*0.125).Raw
        burst=append(burst,frame)
        accepted=append(accepted,frame[28:]...)
        wire=append(wire,frame...)
    }
    for ch:=1;ch<8;ch++{
        frame:=syntheticFrame(ch,0,0.125).Raw
        burst=append(burst,frame)
        wire=append(wire,frame...)
    }
    for ch:=8;ch<10;ch++{
        frame:=syntheticFrame(ch,0,0.125).Raw
        burst=append(burst,frame)
        wire=append(wire,frame...)
    }
    changed:=make([]byte,4)
    binary.LittleEndian.PutUint32(changed,math.Float32bits(4))
    update:=makeParam([]RegBlock{{Addr:0x10e,Words:2,Payload:changed}})
    burst=append(burst,update);wire=append(wire,update...)
    values:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
        Payload:[]byte{0x11,0x22,0x33,0x44}}})
    burst=append(burst,values)
    wire=append(wire,values...)
    ctx,cancel:=context.WithTimeout(context.Background(),15*time.Second)
    defer cancel()
    txProof:=make(chan []byte,1)
    serverError:=make(chan error,1)
    go func(){
        socket,err:=ln.Accept()
        if err!=nil{serverError<-err;return}
        defer socket.Close()
        _=socket.SetDeadline(time.Now().Add(14*time.Second))
        if _,err=socket.Write(first);err!=nil{serverError<-err;return}
        sent:=make([]byte,sourceSetRateWriteLen)
        if _,err=io.ReadFull(socket,sent);err!=nil{serverError<-err;return}
        txProof<-sent
        for _,frame:=range burst{
            if _,err=socket.Write(frame);err!=nil{serverError<-err;return}
        }
        <-ctx.Done()
        serverError<-nil
    }()
    type sourceWindows struct{
        timeWindow mode2WindowProof
        fftWindow mode2WindowProof
        err error
    }
    windows:=make(chan sourceWindows,1)
    go func(){
        out:=sourceWindows{}
        defer func(){windows<-out;cancel()}()
        deadline:=time.Now().Add(11*time.Second)
        if out.err=mode2WaitForSourceReceiver(run,1536,deadline);out.err!=nil{return}
        n,e:=sourceLongWindowLength(65536,9)
        if e!=nil{out.err=e;return}
        if out.err=mode2WriteSourceWindowRequest(run,
            "12345678123456781234567812345678",9,n,1536);out.err!=nil{return}
        out.timeWindow,out.err=mode2WaitForWindow(run,
            "12345678123456781234567812345678",deadline)
        if out.err!=nil{return}
        if out.err=mode2WriteSourceWindowRequest(run,
            "abcdefabcdefabcdefabcdefabcdefab",-1,1024,1536);out.err!=nil{return}
        out.fftWindow,out.err=mode2WaitForWindow(run,
            "abcdefabcdefabcdefabcdefabcdefab",deadline)
    }()
    reason,runErr:=sourceTask2CaptureAddressRetry(ctx,m,ln.Addr().String(),0,
        4*1024*1024,nil)
    if reason!="STOPPED_BY_USER" || runErr!=nil{
        t.Fatalf("original complete source Task2 ended incorrectly: %s %v",reason,runErr)
    }
    proof:=<-windows
    if proof.err!=nil{t.Fatal(proof.err)}
    cmd:=<-txProof
    expectedCommand,_:=sourceSetRateWireBytes(65536)
    if !bytes.Equal(cmd,expectedCommand){t.Fatal("wrong original 36-byte SetRate")}
    if e:=<-serverError;e!=nil{t.Fatal(e)}
    n,_:=sourceLongWindowLength(65536,9)
    for _,item:=range []struct{
        proof mode2WindowProof
        id string
        tag int
        count uint32
    }{
        {proof.timeWindow,"12345678123456781234567812345678",9,n},
        {proof.fftWindow,"abcdefabcdefabcdefabcdefabcdefab",-1,1024},
    }{
        r:=item.proof.receipt
        expected,scaleErr:=sourceApplyOriginalFRange(accepted[(1536-int(item.count))*4:],2.5)
        if scaleErr!=nil{t.Fatal(scaleErr)}
        if r.Schema!=sourceLongWindowResultSchema ||
           r.RequestID!=item.id || r.HTag!=item.tag ||
           r.Samples!=item.count || r.CaptureEnd!=1536 ||
           r.NextIndex!=1536 || r.FirstIndex!=1536-item.count ||
           r.InputDomain!=sourceStorageOriginalConfigADC ||
           r.SourceRangeState==nil || r.SourceRangeState.Single!=2.5 ||
           r.SourceRangeState.RegisterRawLE!="00002040" ||
           r.SampleRateHz!=65536 || !r.CalibrationAlreadyApplied ||
           len(item.proof.source)!=len(expected) ||
           !bytes.Equal(item.proof.source,expected){
            t.Fatalf("one physical TCP / source ring signal-spectrum mismatch: %+v",r)
        }
    }
    report,_,e:=m.Finalize(reason)
    if e!=nil{t.Fatal(e)}
    raw,e:=os.ReadFile(filepath.Join(run,"incoming.raw"))
    if e!=nil || !bytes.Equal(raw,wire){t.Fatal("one-socket RAW not byte-exact",e)}
    digest:=sha256.Sum256(wire)
    if report.RawSHA256!=hex.EncodeToString(digest[:]) ||
       report.SourceTCPConnectionCount!=1 ||
       report.SourceTCPMultiSocket || report.CaptureOnly ||
       report.SourceSetRateCount!=1 || report.SourceSetRateBytes!=36 ||
       report.SourceLiveWriteDataWindows!=1 ||
       report.SourceLiveValuesWindows!=1 ||
       report.SourceLiveValuesEventRecords!=1 ||
       report.SourceLiveWriteDataPacketRecords!=15 ||
       report.Channels[0].Samples!=1536 ||
       report.Channels[8].Samples!=64 ||
       report.Channels[9].Samples!=64 ||
       report.InvalidFrames!=0 || report.Denials!=0 ||
       report.EndReason!="STOPPED_BY_USER" {
        t.Fatalf("original full measurement/Stop audit differs: %+v",report)
    }
    stored,e:=os.ReadFile(filepath.Join(run,"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"))
    if e!=nil || !bytes.Equal(stored,accepted) {
        t.Fatal("WriteData must match real ADC1 frames, not BIN gain",e)
    }
    sourceValue,e:=os.ReadFile(filepath.Join(run,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
    if e!=nil {t.Fatal(e)}
    var received sourceLiveValuesEvent
    if e=json.Unmarshal(bytes.TrimSpace(sourceValue),&received);e!=nil {t.Fatal(e)}
    if received.Address!="0x3100" || received.PayloadLEHex!="11223344" {
        t.Fatalf("WriteValues must preserve exact real 0x3100 PARAM: %+v",received)
    }
    for _,name:=range []string{
        sourceLiveWriterAudit,sourceLiveValuesAuditName,sourceLiveWriterPackets,
        frameMarkAuditName,"SOURCE_TCP_SEGMENT_0001.raw",
    }{
        stat,e:=os.Stat(filepath.Join(run,name))
        if e!=nil || stat.Size()==0{t.Fatalf("missing source audit %s: %v",name,e)}
    }
}

func TestMode2NonselectedWireFsSkipsOnlySourceRingAndDoesNotPoisonFutureWindows(t *testing.T){
    dir:=filepath.Join(t.TempDir(),"TEST_2026-11-19_16-00-00.000")
    m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.liveProgressEnabled=true
    if e=m.EnableLiveBinSpool();e!=nil{t.Fatal(e)}
    source:=make([]byte,0,9*256*4)
    for i:=0;i<10;i++{
        frame:=syntheticFrame(0,uint32(i*256),float32(i+1)*0.125).Raw
        if i==1{
            // Fs outside original menu: valid uint32, rejected ONLY
            // from selected-rate storage, not malformed network data.
            binary.LittleEndian.PutUint32(frame[24:28],44100)
        }else{source=append(source,frame[28:]...)}
        if e=m.ProcessChunk(frame,time.Now());e!=nil{t.Fatal(e)}
    }
    if m.sourceRateTransitionDetected || m.summary.SourceRateTransition ||
       m.summary.InvalidFrames!=0 || m.captureOnly ||
       len(m.summary.Channels[0].rates)!=2 {
        t.Fatal("valid wrong-Fs frame falsely poisoned source rate state")
    }
    c:=m.sourceOriginalStorage.channels[0]
    if c.rxPos!=9*256 || c.validPos!=256 ||
        m.sourceOriginalRXGate.skippedRate[0]!=256 ||
        m.sourceOriginalRXGate.allowed[0]!=9*256 ||
        c.domain!=sourceStorageOriginalLiveADC {
        t.Fatalf("source skipped Fs damaged original ring: %+v",c)
    }
    n,_:=sourceLongWindowLength(65536,9)
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(dir),
        RequestID:"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ADC:1,HTag:9,Samples:n,CaptureEnd:c.rxPos,
        SampleRateHz:65536,DeviceEnd:c.nextDeviceIndex,
    }
    body,_:=json.Marshal(req)
    if e=os.WriteFile(filepath.Join(dir,sourceLongWindowRequestName),body,0600);e!=nil{t.Fatal(e)}
    if e=m.handleSourceLongWindowRequest(time.Now());e!=nil {
        t.Fatalf("original ring after wrong Fs should recover with real contiguous history: %v",e)
    }
    got,e:=mode2ReadActualWindow(filepath.Join(dir,sourceLongWindowResultName))
    if e!=nil{t.Fatal(e)}
    if got.receipt.InputDomain!=sourceStorageOriginalLiveADC ||
       !bytes.Equal(got.source,source[(len(source)/4-int(n))*4:]){
        t.Fatal("GetSignal used rejected wrong-Fs TCP samples or BIN calibration")
    }
}
