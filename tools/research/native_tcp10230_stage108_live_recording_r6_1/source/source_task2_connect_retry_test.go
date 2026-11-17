package main
import("testing";"time")
func TestOriginalSourceInitialRetryWaits(t *testing.T){
 ticks:=25.0
 want:=[]time.Duration{260*time.Millisecond,360*time.Millisecond,
     510*time.Millisecond,720*time.Millisecond}
 for i,expected:=range want{
  got:=sourceRetryWait(ticks)
  if got!=expected {t.Fatalf("step %d: %v wanted %v",i,got,expected)}
  ticks=sourceRetryNextTicks(ticks)
 }
 if sourceRetryWait(50000)!=11320*time.Millisecond {t.Fatal("source retry cap")}
 if sourceRetryWait(0)!=260*time.Millisecond {t.Fatal("source retry start")}
}

func TestSourceOriginalFloat32OvershootAndBankersRound(t *testing.T){
 ticks:=25.0
 expected:=[]time.Duration{
  260*time.Millisecond,360*time.Millisecond,510*time.Millisecond,
  720*time.Millisecond,1010*time.Millisecond,1420*time.Millisecond,
  2010*time.Millisecond,2840*time.Millisecond,4010*time.Millisecond,
  5670*time.Millisecond,8010*time.Millisecond,11320*time.Millisecond,
  11320*time.Millisecond,
 }
 for i,want:=range expected{
  if got:=sourceRetryWait(ticks);got!=want{
   t.Fatalf("Delphi pause step %d ticks %v got %v want %v",i+1,ticks,got,want)
  }
  ticks=sourceRetryNextTicks(ticks)
 }
 if ticks!=sourceFinalPauseFloat32{t.Fatalf("final Win32 Single: %v",ticks)}
 if got:=sourceRetryWait(26.5);got!=270*time.Millisecond{
  t.Fatalf("Delphi @ROUND must use ties-to-even, got %v",got)
 }
}
