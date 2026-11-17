package main

// Three original sources: _Unit125.pas Task2/IDP 00807A98, SQLite
// call graph, and Delphi DFM event. ONLY localhost fake sockets here.
import (
 "bytes"
 "context"
 "fmt"
 "net"
 "os"
 "path/filepath"
 "sync/atomic"
 "testing"
 "time"
)

func TestTask2PassiveReconnectTwoLoopbackSocketsNeverTransmitsSetRate(t *testing.T) {
 ln,e:=net.Listen("tcp4","127.0.0.1:0")
 if e!=nil{t.Fatal(e)}
 defer ln.Close()
 ctx,cancel:=context.WithCancel(context.Background())
 defer cancel()
 var accepted atomic.Int32
 received:=make(chan struct{},1)
 readChecked:=make(chan struct{},1)
 release:=make(chan struct{})
 defer close(release)
 errs:=make(chan error,2)
 first:=task2Status0Param(0).Raw
 second:=task2Status0Param(0).Raw
 go func(){
  for i:=0;i<2;i++{
   conn,err:=ln.Accept()
   if err!=nil{errs<-err;return}
   accepted.Add(1)
   data:=first
   if i==1{data=second}
   if _,err=conn.Write(data);err!=nil{errs<-err;_ =conn.Close();return}
   if i==0{
    _=conn.Close() // original source EIdConnClosedGracefully
    continue
   }
   received<-struct{}{}
   _=conn.SetReadDeadline(time.Now().Add(125*time.Millisecond))
   buf:=make([]byte,36)
   n,readErr:=conn.Read(buf)
   if n!=0||readErr==nil{
    errs<-fmt.Errorf("unexpected outgoing SetRate: n=%d err=%v",n,readErr)
   }else if ne,ok:=readErr.(net.Error);!ok||!ne.Timeout(){
    errs<-fmt.Errorf("unexpected source socket read result: %v",readErr)
   }
   readChecked<-struct{}{}
   <-release
   _=conn.Close()
  }
 }()
 dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_02-01-01.001")
 m,e:=NewMonitor(dir,"LIVE_TASK2_PASSIVE_RECONNECT_APPROVED","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 m.sourceTCP=&sourceTCPLedger{}
 m.sourceAfterRAWReconnect=true
 type result struct{reason string;err error}
 done:=make(chan result,1)
 go func(){
  reason,err:=sourceTask2CaptureAddressRetry(
   ctx,m,ln.Addr().String(),0,4*1024*1024,nil)
  done<-result{reason,err}
 }()
 select{
 case <-received:
 case e:=<-errs:t.Fatal(e)
 case <-time.After(4*time.Second):t.Fatal("source did not reconnect passively")
 }
 select{
 case <-readChecked:
 case e:=<-errs:t.Fatal(e)
 case <-time.After(4*time.Second):t.Fatal("passive socket was not checked")
 }
 time.Sleep(120*time.Millisecond) // let second source PARAM enter Go framer
 cancel()
 select{
 case got:=<-done:
  if got.reason!="STOPPED_BY_USER"||got.err!=nil{t.Fatalf("source stop: %+v",got)}
 case <-time.After(4*time.Second):t.Fatal("source retry missed operator stop")
 }
 rep,_,e:=m.Finalize("STOPPED_BY_USER")
 if e!=nil{t.Fatal(e)}
 if accepted.Load()!=2||rep.SourceTCPConnectionCount!=2||
   !rep.SourceTCPMultiSocket||rep.SourceTCPReconnectAfterRAW!=1||
   rep.SourceSetRateCount!=0||rep.SourceSetRateBytes!=0||!rep.ReadOnly||
   !rep.SourceTCPSegmentCopiesVerified{
  t.Fatalf("source read-only TCP segments lost: count %d rate TX %d bytes %d",
   rep.SourceTCPConnectionCount,rep.SourceSetRateCount,rep.SourceSetRateBytes)
 }
 combined,e:=os.ReadFile(filepath.Join(dir,"incoming.raw"))
 if e!=nil{t.Fatal(e)}
 if !bytes.Equal(combined,append(append([]byte{},first...),second...)){
  t.Fatal("source TCP boundaries merged with corrupted original bytes")
 }
 if isSafeCaptureForExport(rep)==nil{
  t.Fatal("source multi-socket data must not be certified as one continuous BIN")
 }
 select{
 case e:=<-errs:t.Fatal(e)
 default:
 }
}
