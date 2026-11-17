package main
import(
 "bytes"
 "context"
 "encoding/json"
 "fmt"
 "io"
 "net"
 "os"
 "path/filepath"
 "sync/atomic"
 "testing"
 "time"
)
func TestOriginalTask2ExactBackoffSourceRoundPlusOne(t *testing.T){
 ticks:=25.0
 wants:=[]time.Duration{260*time.Millisecond,360*time.Millisecond,
  510*time.Millisecond,720*time.Millisecond}
 for i,want:=range wants{
  if got:=sourceRetryWait(ticks);got!=want{
   t.Fatalf("source PauseValue step %d: got %v want %v",i,got,want)
  }
  ticks*=1.4142135623730951
 }
 if sourceRetryWait(50000)!=8020*time.Millisecond{t.Fatal("source upper pause cap")}
}
func TestSourceTask2TwoSocketsHaveIndependentRAWAndFreshRegisters(t *testing.T){
 dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_01-01-01.001")
 m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 m.sourceTask2TX=newSourceLiveTask2TX()
 m.sourceTCP=&sourceTCPLedger{}
 first:=task2Status0Param(0).Raw
 second:=task2Status0Param(0).Raw
 if e=m.sourceTCP.begin(m);e!=nil{t.Fatal(e)}
 if e=m.ProcessChunk(first,time.Now());e!=nil{t.Fatal(e)}
 if _,e=m.image.Uint32(0x1006);e!=nil{t.Fatal("first socket lost its valid system status")}
 m.sourceTCP.finish(m,"REMOTE_DISCONNECTED")
 if e=m.sourceTCP.begin(m);e!=nil{t.Fatal(e)}
 if _,e=m.image.Uint32(0x1006);e==nil{t.Fatal("old socket STATUS0 leaked into a new socket")}
 if m.sourceTask2TX.stage!=0||m.sourceTask2TX.status0Seen{
  t.Fatal("old Stage1 carried to new connection")
 }
 if e=m.ProcessChunk(second,time.Now());e!=nil{t.Fatal(e)}
 m.sourceTCP.finish(m,"STOPPED_BY_USER")
 rep,_,e:=m.Finalize("STOPPED_BY_USER")
 if e!=nil{t.Fatal(e)}
 if rep.SourceTCPConnectionCount!=2||!rep.SourceTCPMultiSocket||
    !rep.SourceTCPSegmentCopiesVerified||rep.SourceTCPSegmentManifestSHA256==""{
  t.Fatal("two socket verified segment provenance missing")
 }
 joined,e:=os.ReadFile(filepath.Join(dir,"incoming.raw"))
 if e!=nil{t.Fatal(e)}
 if !bytes.Equal(joined,append(append([]byte{},first...),second...)){
  t.Fatal("aggregated RAW is no longer an exact concatenation of wire bytes")
 }
 for i,expected:=range [][]byte{first,second}{
  p:=filepath.Join(dir,fmt.Sprintf("SOURCE_TCP_SEGMENT_%04d.raw",i+1))
  got,e:=os.ReadFile(p)
  if e!=nil||!bytes.Equal(got,expected){t.Fatalf("separate socket %d raw=%v e=%v",i,got,e)}
 }
 raw,e:=os.ReadFile(filepath.Join(dir,sourceTCPSegmentManifestName))
 if e!=nil{t.Fatal(e)}
 var obj struct{SingleRateBINCertifiable bool `json:"single_rate_bin_certifiable"`;Count int `json:"source_tcp_connection_count"`}
 if e=json.Unmarshal(raw,&obj);e!=nil{t.Fatal(e)}
 if obj.SingleRateBINCertifiable||obj.Count!=2{t.Fatal("false single-rate certified export")}
 if isSafeCaptureForExport(rep)==nil{t.Fatal("must reject concatenated TCP sessions as a single BIN")}
}
func TestSourceTask2ActualReconnectAfterRAWOnLocalFakeInstrument(t *testing.T){
 listener,e:=net.Listen("tcp4","127.0.0.1:0")
 if e!=nil{t.Fatal(e)}
 defer listener.Close()
 ctx,cancel:=context.WithCancel(context.Background())
 defer cancel()
 var accepted atomic.Int32
 got:=make(chan []byte,2)
 errorsCh:=make(chan error,2)
 go func(){
  for i:=0;i<2;i++{
   conn,e:=listener.Accept()
   if e!=nil{errorsCh<-e;return}
   accepted.Add(1)
   _=conn.SetDeadline(time.Now().Add(3*time.Second))
   if _,e=conn.Write(task2Status0Param(0).Raw);e!=nil{errorsCh<-e;_ =conn.Close();return}
   raw:=make([]byte,36)
   if _,e=io.ReadFull(conn,raw);e!=nil{errorsCh<-e;_ =conn.Close();return}
   got<-raw
   _=conn.Close()
  }
  // Cancel after two physical TCP sockets, not after the first RAW packet.
  cancel()
 }()
 dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_01-01-01.002")
 m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 m.sourceTask2TX=newSourceLiveTask2TX()
 m.sourceTCP=&sourceTCPLedger{}
 m.sourceAfterRAWReconnect=true
 reason,e:=sourceTask2CaptureAddressRetry(ctx,m,listener.Addr().String(),6,4*1024*1024,nil)
 if e!=nil{t.Fatalf("source retry ended %s: %v",reason,e)}
 report,_,e:=m.Finalize("STOPPED_BY_USER")
 if e!=nil{t.Fatal(e)}
 if accepted.Load()!=2 || report.SourceTCPConnectionCount!=2 ||
    report.SourceTCPReconnectAfterRAW==0 ||
    report.SourceSetRateCount!=2 || report.SourceSetRateBytes!=72 {
  t.Fatalf("source physical TCP pair missing: accepted %d sessions %d retries %d commands %d bytes %d",
   accepted.Load(),report.SourceTCPConnectionCount,report.SourceTCPReconnectAfterRAW,
   report.SourceSetRateCount,report.SourceSetRateBytes)
 }
 for i:=0;i<2;i++{
  select{
  case raw:=<-got:
   expected,_:=sourceSetRateWireBytes(65536)
   if !bytes.Equal(raw,expected){t.Fatal("new socket did not send source 36 bytes")}
  case e:=<-errorsCh:t.Fatal(e)
  default:t.Fatal("missing physical write on one of the two sockets")
  }
 }
 if isSafeCaptureForExport(report)==nil{t.Fatal("two TCP recordings cannot be one certified BIN")}
}
