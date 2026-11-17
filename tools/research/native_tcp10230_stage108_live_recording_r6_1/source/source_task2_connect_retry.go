package main

// Original TMVKThread Task2 initial connection retry in OPT-IN source mode.
// Private _Unit125.pas 00807C12/008089BA-00808B0E:
// connect timeout 1000ms, read timeout 5000ms, wait Round(Pause)*10ms,
// Pause starts at 25 and grows x sqrt(2), stops growing at 801.
// Retries only BEFORE any RAW bytes arrive. After incoming data, a new
// connection would require a new run/RAW segment and fresh register image;
// mixing two TCP sessions into one certified archive is forbidden.
import (
 "context"
 "errors"
 "fmt"
 "math"
 "net"
 "strconv"
 "time"
)

func sourceRetryWait(ticks float64) time.Duration {
 if ticks<25 {ticks=25}
 if ticks>801 {ticks=801}
 return time.Duration(math.Round(ticks))*10*time.Millisecond
}
func sourceTask2CaptureInitialRetry(ctx context.Context,m *Monitor,ip string,
   seconds int,maxBytes uint64,nic *LocalNIC)(string,error){
 end:=time.Now().Add(time.Duration(seconds)*time.Second)
 ticks:=25.0
 addr:=net.JoinHostPort(ip,strconv.Itoa(instrumentPort))
 for {
  if ctx.Err()!=nil{return "STOPPED_BY_USER",nil}
  remaining:=int(math.Ceil(time.Until(end).Seconds()))
  if remaining<1 {return "SOURCE_INITIAL_RETRY_TIMEOUT",errors.New("source Task2 initial connection exceeded capture deadline")}
  reason,err:=liveCaptureAddressOnNIC(ctx,m,addr,remaining,maxBytes,nic)
  // NEVER concatenate two physical TCP stream sessions into ONE RAW!
  // A new attempt is only safe while absolutely no application RX bytes
  // have been written and no source command was sent.
  if m.summary.RawBytes!=0 || m.sourceTask2TX.sentBytes!=0 || ctx.Err()!=nil {
   return reason,err
  }
  if reason!="CONNECT_FAILED" && reason!="SOURCE_READ_TIMEOUT" && reason!="SOCKET_READ_FAILED" {
   return reason,err
  }
  wait:=sourceRetryWait(ticks)
  if time.Until(end)<wait {return reason,err}
  m.summary.SourceInitialRetryAttempts++
  m.note(fmt.Sprintf("Task2 initial reconnect attempt %d after %v; zero RAW bytes, zero TX",
      m.summary.SourceInitialRetryAttempts,wait))
  m.publishLiveStatus("CONNECTING",true,"")
  timer:=time.NewTimer(wait)
  select{
  case <-timer.C:
  case <-ctx.Done():
   if !timer.Stop(){select{case <-timer.C:default:}}
   return "STOPPED_BY_USER",nil
  }
  ticks=math.Min(801,ticks*math.Sqrt2)
 }
}
