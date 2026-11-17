package main
import (
 "bytes"
 "encoding/binary"
 "errors"
 "io"
 "net"
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
