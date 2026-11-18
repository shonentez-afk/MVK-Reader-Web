package main

// _Unit125.pas 008089A3..00808B15 creates a NEW TCP client after
// EIdConnClosedGracefully / EIdReadTimeout / EIdConnectTimeout.
// Its PauseValue starts at Single(25.0), each sleep uses
// (Round(PauseValue)+1)*10ms, then PauseValue *= sqrt(2) while <801.
// After actual RAW bytes, retry is a distinct user-authorized feature:
// each socket gets independent SHA256 RAW and fresh protocol state.
import (
 "context"
 "errors"
 "fmt"
 "math"
 "net"
 "os"
 "strconv"
 "time"
)
// 00808AAF..00808AD8: Delphi @ROUND (ties-to-even) + INC,
// then Terminated-gated Sleep(10) repeated that many times.
// 00808ADD..00808B0E grows while PauseValue<801; the last
// multiplication from 800 intentionally OVERSHOOTS to ~1131.37.
const sourceFinalPauseFloat32 = 1131.370849609375
func sourceRetryWait(ticks float64)time.Duration{
 if ticks<25{ticks=25}
 if ticks>sourceFinalPauseFloat32{ticks=sourceFinalPauseFloat32}
 return time.Duration(math.RoundToEven(ticks)+1)*10*time.Millisecond
}
func sourceRetryNextTicks(ticks float64)float64{
 if ticks>=801{return ticks}
 return float64(float32(ticks*math.Sqrt2)) // Win32 Single field +58
}
func sourceTask2CaptureInitialRetry(ctx context.Context,m *Monitor,ip string,
 seconds int,maxBytes uint64,nic *LocalNIC)(string,error){
 addr:=net.JoinHostPort(ip,strconv.Itoa(instrumentPort))
 return sourceTask2CaptureAddressRetry(ctx,m,addr,seconds,maxBytes,nic)
}
// Explicit test-only address injection lets CI exercise TWO real loopback
// TCP sockets without contacting an instrument or changing port 10230 live.
func sourceTask2CaptureAddressRetry(ctx context.Context,m *Monitor,addr string,
 seconds int,maxBytes uint64,nic *LocalNIC)(string,error){
 // Original Task2 TCP retry does not itself require SetRate writes.
 if m.sourceTask2TX==nil && !m.sourceAfterRAWReconnect{
  return "",errors.New("source Task2 TCP retry not approved")
 }
 // Original Task2 retry is bounded by thread termination, not a
 // mandatory wall clock. Unbounded GUI sessions pass seconds==0.
 var deadline time.Time
 if seconds>0 {deadline=time.Now().Add(time.Duration(seconds)*time.Second)}
 ticks:=25.0
 if m.sourceTask2TX!=nil && m.sourceOperatorRateChan==nil{
  ch:=make(chan string,16)
  m.sourceOperatorRateChan=ch
  go sourceOperatorRateLines(os.Stdin,ch)
 }
 for{
  if ctx.Err()!=nil{return "STOPPED_BY_USER",nil}
  remaining:=0
  if !deadline.IsZero(){
   remaining=int(math.Ceil(time.Until(deadline).Seconds()))
   if remaining<1{return "SOURCE_RETRY_TIMEOUT",errors.New("source Task2 connection deadline exceeded")}
  }
  // _Unit125 00807CD9 resets PauseValue after each real TCP
  // connection. A new socket is tracked by independent RAW ledger.
  socketsBefore:=m.summary.SourceTCPConnectionCount
  reason,err:=liveCaptureAddressOnNIC(ctx,m,addr,remaining,maxBytes,nic)
  if m.summary.SourceTCPConnectionCount>socketsBefore {ticks=25}
  if ctx.Err()!=nil{return "STOPPED_BY_USER",nil}
  if m.captureOnly || (m.sourceTask2TX!=nil && m.sourceTask2TX.writeFault!=""){return reason,err}
  // Original _Unit125:008080C5 DENIED raises errOperationDenied,
  // the generic exception handler 0080896D unwinds the socket, then
  // Task2 008089A3..00808B15 enters its ordinary reconnect loop.
  // Our physical reconnect-after-RAW still requires an explicit grant:
  // without it the denial remains terminal and its RAW is retained.
  if reason!="CONNECT_FAILED" && reason!="REMOTE_DISCONNECTED" &&
    reason!="SOURCE_READ_TIMEOUT" && reason!="SOCKET_READ_FAILED" &&
    reason!="SOURCE_OPERATION_DENIED" {
   return reason,err
  }
  if m.summary.RawBytes>0 && !m.sourceAfterRAWReconnect{
   return reason,err // no approval: preserve RAW, no additional sockets
  }
  wait:=sourceRetryWait(ticks)
  if !deadline.IsZero() && time.Until(deadline)<wait{return reason,err}
  m.summary.SourceInitialRetryAttempts++
  if m.summary.RawBytes>0{m.summary.SourceTCPReconnectAfterRAW++}
  // Source-aligned retry status belongs to this receiver; the
  // current TCP link is NOT healthy while in this waiting state.
  m.sourceLastRetryReason=reason
  m.sourceLastRetryWaitMS=int64(wait/time.Millisecond)
  m.note(fmt.Sprintf("Task2 new socket attempt %d after %v; retained RAW=%d bytes; source TX=%d",
   m.summary.SourceInitialRetryAttempts,wait,m.summary.RawBytes,m.sourceSentBytes()))
  m.publishLiveStatus("CONNECTING",true,"")
  timer:=time.NewTimer(wait)
  select{
  case <-timer.C:
  case <-ctx.Done():
   if !timer.Stop(){select{case <-timer.C:default:}}
   return "STOPPED_BY_USER",nil
  }
  ticks=sourceRetryNextTicks(ticks)
 }
}
