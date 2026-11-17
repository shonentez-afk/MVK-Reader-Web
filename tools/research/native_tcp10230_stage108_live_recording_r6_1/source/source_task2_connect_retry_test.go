package main
import("testing";"time")
func TestOriginalSourceInitialRetryWaits(t *testing.T){
 ticks:=25.0
 want:=[]time.Duration{250*time.Millisecond,350*time.Millisecond,
     500*time.Millisecond,710*time.Millisecond}
 for i,expected:=range want{
  got:=sourceRetryWait(ticks)
  if got!=expected {t.Fatalf("step %d: %v wanted %v",i,got,expected)}
  ticks*=1.4142135623730951
 }
 if sourceRetryWait(50000)!=8010*time.Millisecond {t.Fatal("source retry cap")}
 if sourceRetryWait(0)!=250*time.Millisecond {t.Fatal("source retry start")}
}
