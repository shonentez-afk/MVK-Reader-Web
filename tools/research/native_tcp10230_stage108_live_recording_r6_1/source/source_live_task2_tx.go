package main

// The real, opt-in original Task2 FIFO writer, on the SAME approved socket
// as the already-tested Go ADC/TACH/PARAM receiver. No new TCP client,
// Modbus, Flash, reboot, IP discovery or hidden timer. Disabled by default.
// Only source-verified rate changes are accepted: CMD=1, Addr=0x000E.
// Original reference: _Unit125.pas 00807E8F..00807F52/0080937C.
// PCAP A/B independently confirms EXACT SetRate(65536) stream bytes.
import (
 "bufio"
 "errors"
 "fmt"
 "io"
 "net"
 "strconv"
 "strings"
 "time"
)

var errTask2SourceDenied=errors.New("original Task2 device operation denied")
var errTask2SourceWrite=errors.New("original Task2 source write failure")

type sourceLiveTask2TX struct {
 conn net.Conn
 enabled bool
 stage int
 status0Seen bool
 status0 uint32
 systemErrorLatched bool
 pending []uint32
 lastQueuedRate uint32
 lastSentRate uint32
 sentCommands uint64
 sentBytes uint64
 ackAfterTX uint64
 deniedAfterTX uint64
 writeFault string
}
func newSourceLiveTask2TX() *sourceLiveTask2TX {
 return &sourceLiveTask2TX{enabled:true,pending:[]uint32{65536},lastQueuedRate:65536}
}
func (s *sourceLiveTask2TX) queueRate(rate uint32) error {
 if !acceptedRates[rate] {return fmt.Errorf("original rate not supported: %d",rate)}
 if s.systemErrorLatched || s.writeFault!="" {return errors.New("source Task2 rate forbidden after error")}
 if rate==s.lastQueuedRate {return nil} // original SetRate only queues changes
 if len(s.pending)>=16 {return errors.New("source Task2 FIFO overflow")}
 s.pending=append(s.pending,rate)
 s.lastQueuedRate=rate
 return nil
}
func (s *sourceLiveTask2TX) afterReceivedFrame(m *Monitor,f Frame) error {
 switch f.Type {
 case typeParam:
  if m.summary.SourceNonemptyParameters>0 && s.stage==0 {s.stage=1}
  if status0,e:=m.image.Uint32(0x1006);e==nil {
   s.status0Seen=true;s.status0=status0
   if status0>0 {s.stage=3;s.systemErrorLatched=true}
  }
 case typeAck:
  if s.sentCommands>0{s.ackAfterTX++} // temporal ONLY; no transaction ID
 case typeDenied:
  if s.sentCommands>0{s.deniedAfterTX++}
  // Original source throws errOperationDenied; fail closed and finalize RAW.
  return errTask2SourceDenied
 }
 return s.sendNext(m)
}
func (s *sourceLiveTask2TX) sendNext(m *Monitor) error {
 if !s.enabled || s.stage!=1 || !s.status0Seen || s.status0!=0 ||
    s.systemErrorLatched || len(s.pending)==0 {return nil}
 if s.conn==nil{return nil}
 rate:=s.pending[0]
 command,e:=sourceSetRateWireBytes(rate)
 if e!=nil{return e}
 s.pending=s.pending[1:] // original TList.Get(0)/Delete(0) before Write
 if e=s.conn.SetWriteDeadline(time.Now().Add(time.Second));e!=nil {
  s.writeFault=e.Error();return fmt.Errorf("%w: %v",errTask2SourceWrite,e)
 }
 n,e:=s.conn.Write(command)
 if n>0 {
  s.sentBytes+=uint64(n)
  m.summary.ReadOnly=false // do NOT claim passive when any TX byte occurred
 }
 if e!=nil || n!=len(command) {
  if e==nil {e=io.ErrShortWrite}
  s.writeFault=e.Error()
  return fmt.Errorf("%w: wrote %d/36 bytes: %v",errTask2SourceWrite,n,e)
 }
 s.sentCommands++
 s.lastSentRate=rate
 m.note(fmt.Sprintf("SOURCE TASK2 TX authorized: SetRate(%d) on SAME TCP socket; %d bytes",rate,n))
 return nil
}
func (s *sourceLiveTask2TX) takeOperatorLine(m *Monitor,line string) error {
 tokens:=strings.Fields(line)
 if len(tokens)!=2 || tokens[0]!="RATE" {
  return errors.New("only RATE <source Hz> is accepted; no Flash or service commands")
 }
 n,e:=strconv.ParseUint(tokens[1],10,32)
 if e!=nil {return errors.New("invalid original source Hz")}
 if e=s.queueRate(uint32(n));e!=nil{return e}
 return s.sendNext(m)
}
// QProcess stdin is a LOCAL per-process control plane, never a new TCP
// connection. Scanner is bounded; main capture goroutine owns all socket TX.
func sourceOperatorRateLines(in io.Reader,ch chan<- string) {
 sc:=bufio.NewScanner(in)
 sc.Buffer(make([]byte,64),80)
 for sc.Scan(){ch<-sc.Text()}
 close(ch)
}
func (m *Monitor) drainSourceOperatorRates(ch <-chan string) error {
 if m.sourceTask2TX==nil || ch==nil{return nil}
 for i:=0;i<16;i++ {
  select{
  case line,ok:=<-ch:
   if !ok{return nil}
   if e:=m.sourceTask2TX.takeOperatorLine(m,line);e!=nil {
    m.warn("Original Task2 operator rate rejected: "+e.Error())
    if errors.Is(e,errTask2SourceWrite){return e}
    // Bad rate/command names do not terminate otherwise-valid capture.
   }
  default:return nil
  }
 }
 return nil
}
