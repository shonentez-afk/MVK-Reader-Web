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
 status0SocketMask uint8 // two words observed in current TCP socket
 systemErrorLatched bool
 pending []uint32
 lastQueuedRate uint32
 lastSentRate uint32
 sentCommands uint64
 sentBytes uint64
 sentInSocket uint64 // do not attach a new socket ACK to the prior socket's TX
 paramCounterBase uint64
 ackAfterTX uint64
 deniedAfterTX uint64
 writeFault string
}
func newSourceLiveTask2TX() *sourceLiveTask2TX {
 return &sourceLiveTask2TX{enabled:true,pending:[]uint32{65536},lastQueuedRate:65536}
}
func (s *sourceLiveTask2TX) resetForNewSourceSocket(m *Monitor){
 s.stage=0;s.status0Seen=false;s.status0=0;s.status0SocketMask=0
 s.systemErrorLatched=false
 s.sentInSocket=0
 s.paramCounterBase=m.summary.SourceNonemptyParameters
 s.conn=nil
 // A new socket may require the operator-approved original source rate.
 // It is sent on original Stage1 (positive Status0 latches Stage3).
 if len(s.pending)==0 && s.lastQueuedRate!=0 {s.pending=[]uint32{s.lastQueuedRate}}
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
  if m.summary.SourceNonemptyParameters>s.paramCounterBase && s.stage==0 {s.stage=1}
  // The RegisterImage persists across socket reconnects; do NOT
  // attribute its old Status0 to the new socket's first partial PARAM.
  // FreezeUpdate skips original StatusCells updates.
  if m.sourceOriginalRXGate==nil || !m.sourceOriginalRXGate.frozen {
   s.status0SocketMask|=sourceTask2Status0WordMask(f)
   if s.status0SocketMask==3 {
    if status0,e:=m.image.Uint32(0x1006);e==nil {
     s.status0Seen=true;s.status0=status0
     if status0>0 {s.stage=3;s.systemErrorLatched=true}
    }
   }
  }
 case typeAck:
  if s.sentInSocket>0{s.ackAfterTX++} // SAME socket, temporal only; no transaction ID
 case typeDenied:
  if s.sentInSocket>0{s.deniedAfterTX++}
  // Original source throws errOperationDenied; fail closed and finalize RAW.
  return errTask2SourceDenied
 }
 // Delphi 00807E8F..00807F6A: dispatch is BEFORE the next network
 // read, not during a response callback. The sole Go read loop owns TX.
 return nil
}
func (s *sourceLiveTask2TX) sendNext(m *Monitor) error {
 // _Unit125:00807E8F checks Stage1 and nonempty FIFO. It does not
 // add a second Status0==0 condition. A positive observed Status0
 // already advances Stage3 and inhibits this dispatch.
 // Physical TX still requires the operator-approved source-rate flag.
 if !s.enabled || s.stage!=1 ||
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
 s.sentInSocket++
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
 // Delphi TMVKThread.SetRate sets MvkSampleRate BEFORE writing the
 // 36-byte queued command, independently of its eventual ACK.
 if m.sourceOriginalRXGate!=nil {
    if e=m.sourceOriginalRXGate.selectRate(uint32(n));e!=nil{return e}
 }
 // SetRate only ENQUEUES here. Original Execute sends at most one
 // FIFO command in each receive iteration, before its next ReadUInt32.
 return nil
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
 if ch==nil{return nil}
 for i:=0;i<16;i++ {
  select{
  case line,ok:=<-ch:
   if !ok{return nil}
   // FREEZE is a LOCAL in-memory command; it does not touch the
   // instrument TCP socket or require permission for device SetRate.
   // The original _Unit128:0084DEA4 toggles +400CD.
   if line=="FREEZE 1" || line=="FREEZE 0" {
     if m.sourceOriginalRXGate!=nil {
       m.sourceOriginalRXGate.setFreeze(line=="FREEZE 1")
     }
     continue
   }
   if m.sourceTask2TX==nil {
      m.warn("Native command refused without source SetRate approval")
      continue
   }
   if e:=m.sourceTask2TX.takeOperatorLine(m,line);e!=nil {
    m.warn("Original Task2 operator rate rejected: "+e.Error())
    if errors.Is(e,errTask2SourceWrite){return e}
   }
  default:return nil
  }
 }
 return nil
}
