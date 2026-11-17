package main
import (
 "context"
 "encoding/binary"
 "encoding/json"
 "net"
 "os"
 "path/filepath"
 "testing"
 "time"
)
func task0SourceParam()[]byte{
 // Valid original source PARAM frame with config registers 0004..0015.
 raw:=make([]byte,28+4+24)
 binary.LittleEndian.PutUint32(raw[0:4],typeParam)
 binary.LittleEndian.PutUint32(raw[4:8],uint32(len(raw)))
 binary.LittleEndian.PutUint32(raw[24:28],1)
 binary.LittleEndian.PutUint32(raw[28:32],uint32(12)<<16|4)
 // Deliberately synthetic. No site IP or private config data.
 for i:=32;i<len(raw);i++{raw[i]=byte(i-32)}
 return raw
}
func TestOriginalTask0ConfigReadLoopbackNoCommands(t *testing.T){
 ln,e:=net.Listen("tcp4","127.0.0.1:0")
 if e!=nil{t.Fatal(e)}
 defer ln.Close()
 outgoing:=make(chan int,1)
 go func(){
  conn,err:=ln.Accept()
  if err!=nil{return}
  defer conn.Close()
  _,_=conn.Write(task0SourceParam())
  _=conn.SetReadDeadline(time.Now().Add(350*time.Millisecond))
  buf:=make([]byte,36)
  n,_:=conn.Read(buf)
  outgoing<-n
 }()
 dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_04-00-00.001")
 m,e:=NewMonitor(dir,"LIVE_SOURCE_TASK0_CONFIG_READ_ONLY","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 m.sourceTask0ConfigRead=true
 ctx,cancel:=context.WithTimeout(context.Background(),3*time.Second)
 defer cancel()
 reason,e:=liveCaptureAddress(ctx,m,ln.Addr().String(),2,8*1024*1024)
 if e!=nil||reason!="SOURCE_TASK0_CONFIG_READ_COMPLETE"{
  t.Fatalf("original Task0 did not stop after PARAM: %s %v",reason,e)
 }
 rep,_,e:=m.Finalize(reason)
 if e!=nil{t.Fatal(e)}
 if !rep.ReadOnly||rep.SourceNonemptyParameters!=1||rep.SourceSetRateBytes!=0{
  t.Fatal("source Task0 was not fully read-only")
 }
 if e:=writeSourceTask0ConfigSnapshot(m,rep);e!=nil{t.Fatal(e)}
 b,e:=os.ReadFile(filepath.Join(dir,sourceTask0ConfigName))
 if e!=nil{t.Fatal(e)}
 var receipt sourceTask0Receipt
 if e=json.Unmarshal(b,&receipt);e!=nil{t.Fatal(e)}
 if receipt.SourceOriginalTask!=0||!receipt.ReadOnly||
   !receipt.ConfigParamConfirmed||receipt.ConfigFieldsConfirmed<4{
  t.Fatal("Task0 source register proof missing")
 }
 for _,f:=range receipt.Fields{
  if f.Address>=0x50 && f.Address<=0x7f{
   t.Fatal("Task0 leaked vendor Wi-Fi credential registers")
  }
 }
 select{
 case n:=<-outgoing:
  if n!=0{t.Fatalf("original Task0 wrote %d bytes",n)}
 case <-time.After(900*time.Millisecond):
  t.Fatal("loopback command check did not finish")
 }
}
func TestTask0RefusesToPublishWithoutNonemptyParam(t *testing.T){
 dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_04-00-00.002")
 m,e:=NewMonitor(dir,"LIVE_SOURCE_TASK0_CONFIG_READ_ONLY","127.0.0.1")
 if e!=nil{t.Fatal(e)}
 m.sourceTask0ConfigRead=true
 rep,_,e:=m.Finalize("DURATION_REACHED")
 if e!=nil{t.Fatal(e)}
 if e:=writeSourceTask0ConfigSnapshot(m,rep);e==nil{
  t.Fatal("Task0 should not publish a fake config when the device sent nothing")
 }
}
