package main
import (
 "bytes"
 "context"
 "encoding/binary"
 "errors"
 "io"
 "net"
 "path/filepath"
 "testing"
 "time"
)
func task2Status0Param(v uint32) Frame {
 body:=make([]byte,4);binary.LittleEndian.PutUint32(body,v)
 return Frame{Type:typeParam,Raw:makeParam([]RegBlock{{Addr:0x1006,Words:2,Payload:body}})}
}
func TestApprovedSourceTask2WritesRealPCAPExact36AfterParam(t *testing.T) {
 c,s:=net.Pipe();defer c.Close();defer s.Close()
 m:=&Monitor{};m.sourceTask2TX=newSourceLiveTask2TX()
 tx:=m.sourceTask2TX;tx.conn=c;m.summary.ReadOnly=true
 if e:=tx.sendNext(m);e!=nil||tx.sentBytes!=0{t.Fatal("sent before stage1")}
 // Monitor.consume has already processed this RX PARAM (single goroutine).
 m.summary.SourceNonemptyParameters=1
 m.image.Valid[0x1006]=true;m.image.Valid[0x1007]=true
 payload:=make([]byte,4);binary.LittleEndian.PutUint32(payload,0)
 copy(m.image.Data[0x1006*2:],payload)
 got:=make(chan []byte,1);fail:=make(chan error,1)
 go func(){buf:=make([]byte,36);_,e:=io.ReadFull(s,buf);if e!=nil{fail<-e}else{got<-buf}}()
 if e:=tx.afterReceivedFrame(m,task2Status0Param(0));e!=nil{t.Fatal(e)}
 select{
 case raw:=<-got:
  want,_:=sourceSetRateWireBytes(65536)
  if !bytes.Equal(raw,want){t.Fatal("original A/B command mismatch")}
 case e:=<-fail:t.Fatal(e)
 case <-time.After(2*time.Second):t.Fatal("no local command")
 }
 if tx.sentCommands!=1||tx.sentBytes!=36||m.summary.ReadOnly{t.Fatal("TX provenance wrong")}
 if e:=tx.afterReceivedFrame(m,Frame{Type:typeAck,Raw:sourceReply(typeAck)});e!=nil{t.Fatal(e)}
 if tx.ackAfterTX!=1{t.Fatal("temporal ACK not counted")}
 if e:=tx.afterReceivedFrame(m,Frame{Type:typeDenied,Raw:sourceReply(typeDenied)});!errors.Is(e,errTask2SourceDenied){t.Fatal("DENIED must abort source attempt")}
}
func TestSourceTask2NoWriteUnknownOrErrorAndRejectsServices(t *testing.T){
 m:=&Monitor{};m.sourceTask2TX=newSourceLiveTask2TX()
 tx:=m.sourceTask2TX;m.summary.SourceNonemptyParameters=1
 if e:=tx.afterReceivedFrame(m,task2Status0Param(0));e!=nil||tx.sentBytes!=0{t.Fatal("unknown system0 cannot send")}
 if e:=tx.queueRate(309);e==nil{t.Fatal("bad rate")}
 if e:=tx.takeOperatorLine(m,"FLASH 1");e==nil{t.Fatal("Flash request must be refused")}
 m.image.Valid[0x1006]=true;m.image.Valid[0x1007]=true
 binary.LittleEndian.PutUint32(m.image.Data[0x1006*2:],42)
 if e:=tx.afterReceivedFrame(m,task2Status0Param(42));e!=nil{t.Fatal(e)}
 if !tx.systemErrorLatched||tx.sentBytes!=0{t.Fatal("system error must block sends")}
 if e:=tx.queueRate(32768);e==nil{t.Fatal("must reject after Stage3")}
}
func TestApprovedSourceRateQueueAndAllowedMenuRates(t *testing.T){
 m:=&Monitor{sourceTask2TX:newSourceLiveTask2TX()}
 tx:=m.sourceTask2TX
 for _,v:=range []uint32{32768,8192,2048,512}{
  if e:=tx.queueRate(v);e!=nil{t.Fatal(e)}
 }
 if len(tx.pending)!=5{t.Fatal("initial 65536 plus 4 source menu items")}
 if e:=tx.queueRate(512);e!=nil||len(tx.pending)!=5{t.Fatal("redundant source click")}
}

func TestSourceTask2OptInActualDuplexLocalhostStream(t *testing.T) {
 listener,e:=net.Listen("tcp4","127.0.0.1:0")
 if e!=nil{t.Fatal(e)}
 defer listener.Close()
 capture:=make(chan []byte,1);serverErr:=make(chan error,1)
 go func() {
  c,e:=listener.Accept();if e!=nil{serverErr<-e;return}
  defer c.Close()
  if _,e=c.Write(task2Status0Param(0).Raw);e!=nil{serverErr<-e;return}
  _=c.SetReadDeadline(time.Now().Add(2*time.Second))
  buf:=make([]byte,36)
  if _,e=io.ReadFull(c,buf);e!=nil{serverErr<-e;return}
  capture<-buf
  _,_=c.Write(sourceReply(typeAck))
 }()
 m,e:=NewMonitor(filepath.Join(t.TempDir(),"task2_live"),"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 defer m.CloseFiles()
 m.sourceTask2TX=newSourceLiveTask2TX()
 reason,e:=liveCaptureAddress(context.Background(),m,listener.Addr().String(),2,4*1024*1024)
 if e!=nil{t.Fatalf("source Task2 live fake server: %s: %v",reason,e)}
 if reason!="REMOTE_DISCONNECTED" && reason!="DURATION_REACHED"{t.Fatal(reason)}
 select{
 case got:=<-capture:
  want,_:=sourceSetRateWireBytes(65536)
  if !bytes.Equal(got,want){t.Fatal("actual local socket TX not original PCAP")}
 case e:=<-serverErr:t.Fatal(e)
 case <-time.After(time.Second):t.Fatal("fake device did not receive SetRate")
 }
 if m.summary.SourceNonemptyParameters!=1||m.sourceTask2TX.sentCommands!=1||
    m.sourceTask2TX.sentBytes!=36||m.summary.ReadOnly {
  t.Fatal("approved hardware source TX provenance not recorded")
 }
 if m.sourceTask2TX.ackAfterTX!=1 {t.Fatal("source ACK must remain unpaired")}
}


func TestSourceTask2TwoApprovedSocketsResetOriginalStageAndRate(t *testing.T) {
    // Exact source regression: first socket completes a SetRate and closes.
    // The next socket MUST start Stage0 with a NEW PARAM and queue SetRate
    // again, rather than inheriting Stage1 from the disconnected device.
    ln,e:=net.Listen("tcp4","127.0.0.1:0")
    if e!=nil {t.Fatal(e)}
    defer ln.Close()
    ctx,cancel:=context.WithTimeout(context.Background(),5*time.Second)
    defer cancel()
    got:=make(chan []byte,2)
    serverErrors:=make(chan error,1)
    go func(){
        for i:=0;i<2;i++{
            c,err:=ln.Accept()
            if err!=nil {serverErrors<-err;return}
            _=c.SetDeadline(time.Now().Add(2*time.Second))
            _,err=c.Write(task2Status0Param(0).Raw)
            if err!=nil{_ = c.Close();serverErrors<-err;return}
            buf:=make([]byte,sourceSetRateWriteLen)
            _,err=io.ReadFull(c,buf)
            if err!=nil{_ = c.Close();serverErrors<-err;return}
            got<-buf
            _=c.Close()
        }
        cancel()
        serverErrors<-nil
    }()
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"source_reconnect"),"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceAfterRAWReconnect=true
    reason,err:=sourceTask2CaptureAddressRetry(ctx,m,ln.Addr().String(),0,4*1024*1024,nil)
    if err!=nil {t.Fatalf("original Task2 reconnect %s: %v",reason,err)}
    if reason!="STOPPED_BY_USER" {t.Fatalf("source stop reason: %s",reason)}
    select{
    case err:=<-serverErrors: if err!=nil{t.Fatal(err)}
    case <-time.After(time.Second):t.Fatal("local source server timed out")
    }
    want,_:=sourceSetRateWireBytes(65536)
    for i:=0;i<2;i++ {
        select{
        case sent:=<-got:
            if !bytes.Equal(sent,want) {t.Fatalf("socket %d: wrong original SetRate",i+1)}
        default:t.Fatalf("missing original command on source socket %d",i+1)
        }
    }
    if m.sourceTask2TX.sentCommands!=2 || m.sourceTask2TX.sentBytes!=72 ||
       m.sourceOriginalTask2Stage.attempts!=2 ||
       m.summary.SourceNonemptyParameters!=2 {
        t.Fatalf("Task2 source reconnect did not reset/requeue: tx=%+v stage=%+v params=%d",
            m.sourceTask2TX,m.sourceOriginalTask2Stage,m.summary.SourceNonemptyParameters)
    }
}
