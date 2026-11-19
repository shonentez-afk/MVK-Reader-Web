package main

// Original TMVKThread.Execute invalid-packet exception and recovery.
//
// PRIVATE, checked jointly: Projects.7z/_Unit125.pas
// 00807F8B..00807FA1, 00808871..0080897E, 008089A3..00808B15;
// mvkview.idp + mvk_idr(1).sqlite function/call references.
// Never use a physical MVK01: test actual read/write only through
// synthetic local TCP listener, with independent SHA/byte evidence.
import (
    "bytes"
    "context"
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "errors"
    "fmt"
    "io"
    "net"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceProtocolCorruptHeader()[]byte{
    bad:=make([]byte,8)
    binary.LittleEndian.PutUint32(bad[:4],typeADC)
    binary.LittleEndian.PutUint32(bad[4:8],10) // source length is not divisible by 4
    return bad
}

// Original Execute dispatches its FIFO before the following ReadUInt32,
// even when valid PARAM and invalid packet header are coalesced in one
// OS-level TCP Read. Closing that one socket must retain byte-exact RAW
// and prevent treating following ADC bytes as valid data.
func TestSourceTask2InvalidLengthClosesSameSocketPreservesCoalescedRAWAndTX(t *testing.T){
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil{t.Fatal(e)}
    defer ln.Close()
    prefix:=task2Status0Param(0).Raw
    bad:=sourceProtocolCorruptHeader()
    after:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000)
    exact:=append(append(append([]byte{},prefix...),bad...),after...)
    got:=make(chan []byte,1)
    errorsServer:=make(chan error,1)
    go func(){
        c,e:=ln.Accept()
        if e!=nil{errorsServer<-e;return}
        defer c.Close()
        _=c.SetDeadline(time.Now().Add(5*time.Second))
        if _,e=c.Write(exact);e!=nil{errorsServer<-e;return}
        cmd:=make([]byte,sourceSetRateWriteLen)
        if _,e=io.ReadFull(c,cmd);e!=nil{errorsServer<-e;return}
        got<-cmd; errorsServer<-nil
    }()
    dir:=filepath.Join(t.TempDir(),"original_invalid_packet_single_socket")
    m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceTCP=&sourceTCPLedger{}
    ctx,cancel:=context.WithTimeout(context.Background(),6*time.Second)
    defer cancel()
    reason,err:=sourceTask2CaptureAddressRetry(ctx,m,ln.Addr().String(),
        0,4*1024*1024,nil)
    if reason!="SOURCE_INVALID_PACKET" || !errors.Is(err,errTask2SourceInvalidPacket) {
        t.Fatalf("original source must unwind invalid socket: %s %v",reason,err)
    }
    select{
    case sent:=<-got:
        expected,_:=sourceSetRateWireBytes(65536)
        if !bytes.Equal(sent,expected){t.Fatal("original FIFO before invalid header mismatch")}
    case <-time.After(5*time.Second):t.Fatal("no source SetRate before invalid header")
    }
    if e:=<-errorsServer;e!=nil{t.Fatal(e)}
    report,_,e:=m.Finalize(reason)
    if e!=nil{t.Fatal(e)}
    raw,e:=os.ReadFile(filepath.Join(dir,"incoming.raw"))
    if e!=nil || !bytes.Equal(raw,exact){
        t.Fatalf("source RAW after exception must be all OS-received bytes: %v",e)
    }
    checksum:=sha256.Sum256(exact)
    if report.RawSHA256!=hex.EncodeToString(checksum[:]) ||
        report.SourceTask2ProtocolExceptions!=1 ||
        report.InvalidFrames!=1 ||
        !report.CaptureOnly ||
        report.SourceTCPConnectionCount!=1 ||
        report.SourceTCPMultiSocket ||
        report.Channels[0].Samples!=0 || // ADC after bad header is not decoded
        report.SourceSetRateCount!=1 ||
        report.SourceSetRateBytes!=36 ||
        report.TailBytes!=len(bad)+len(after) ||
        !report.SourceTCPSegmentCopiesVerified ||
        report.EndReason!="SOURCE_INVALID_PACKET"{
        t.Fatalf("source Task2 invalid header receipt %+v",report)
    }
    if isSafeCaptureForExport(report)==nil{
        t.Fatal("protocol exception falsely certified valid single-rate BIN")
    }
}

// Source loop: one failed TCP segment, original retry delay, brand new
// socket, re-send initial SetRate and read actual valid data. The
// two RAW segments have independent SHA and are NEVER exported as one
// certified Delphi measurement.
func TestSourceTask2ApprovedReconnectAfterInvalidLengthFreshStageAndRAW(t *testing.T){
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil{t.Fatal(e)}
    defer ln.Close()
    ctx,cancel:=context.WithTimeout(context.Background(),9*time.Second)
    defer cancel()
    first:=append(append([]byte{},task2Status0Param(0).Raw...),sourceProtocolCorruptHeader()...)
    secondADC:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000,0x40000000)
    second:=append(append([]byte{},task2Status0Param(0).Raw...),secondADC...)
    sent:=make(chan []byte,2)
    serverError:=make(chan error,1)
    go func(){
        for i,wire:=range [][]byte{first,second}{
            c,err:=ln.Accept()
            if err!=nil{serverError<-err;return}
            _=c.SetDeadline(time.Now().Add(5*time.Second))
            if _,err=c.Write(wire);err!=nil{
                _=c.Close();serverError<-err;return
            }
            command:=make([]byte,sourceSetRateWriteLen)
            if _,err=io.ReadFull(c,command);err!=nil{
                _=c.Close();serverError<-err;return
            }
            sent<-command
            if i==1{
                // Give receiver time to decode the ADC in this socket
                // before the operator-initiated cancellation.
                time.Sleep(300*time.Millisecond)
                cancel()
            }
            _=c.Close()
        }
        serverError<-nil
    }()
    dir:=filepath.Join(t.TempDir(),"original_invalid_packet_reconnect")
    m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceTCP=&sourceTCPLedger{}
    m.sourceAfterRAWReconnect=true
    reason,err:=sourceTask2CaptureAddressRetry(ctx,m,ln.Addr().String(),
        0,8*1024*1024,nil)
    if reason!="STOPPED_BY_USER" || err!=nil{
        t.Fatalf("source approved reconnect did not stop cleanly: %s %v",reason,err)
    }
    select{
    case e:=<-serverError:
        if e!=nil{t.Fatal(e)}
    case <-time.After(4*time.Second):t.Fatal("local fake server not complete")
    }
    expectedTX,_:=sourceSetRateWireBytes(65536)
    for i:=0;i<2;i++{
        select{
        case wire:=<-sent:
            if !bytes.Equal(wire,expectedTX){t.Fatalf("socket %d original SetRate differs",i+1)}
        default:t.Fatalf("socket %d did not send original SetRate",i+1)
        }
    }
    report,_,e:=m.Finalize(reason)
    if e!=nil{t.Fatal(e)}
    if report.SourceTask2ProtocolExceptions!=1 ||
       report.InvalidFrames!=1 ||
       report.SourceTCPConnectionCount!=2 ||
       !report.SourceTCPMultiSocket ||
       report.SourceTCPReconnectAfterRAW==0 ||
       !report.SourceTCPSegmentCopiesVerified ||
       report.SourceSetRateCount!=2 ||
       report.SourceSetRateBytes!=72 ||
       report.Channels[0].Samples!=2 ||
       report.SourceNonemptyParameters!=2 ||
       !report.CaptureOnly ||
       m.sourceOriginalTask2Stage.attempts!=2 ||
       m.sourceOriginalTask2Stage.stage!=0 {
        t.Fatalf("approved new socket did not rebuild original Task2 state: %+v stage=%+v",
            report,m.sourceOriginalTask2Stage)
    }
    combined:=append(append([]byte{},first...),second...)
    raw,e:=os.ReadFile(filepath.Join(dir,"incoming.raw"))
    if e!=nil||!bytes.Equal(raw,combined){t.Fatal("combined original RAW byte mismatch")}
    digest:=sha256.Sum256(combined)
    if report.RawSHA256!=hex.EncodeToString(digest[:]){t.Fatal("combined RAW sha mismatch")}
    for i,exp:=range [][]byte{first,second}{
        path:=filepath.Join(dir,fmt.Sprintf("SOURCE_TCP_SEGMENT_%04d.raw",i+1))
        payload,e:=os.ReadFile(path)
        if e!=nil || !bytes.Equal(payload,exp){
            t.Fatalf("independent physical socket segment %d differs: %v",i+1,e)
        }
    }
    if isSafeCaptureForExport(report)==nil{
        t.Fatal("two sockets with one invalid packet falsely certified a single BIN")
    }
}
