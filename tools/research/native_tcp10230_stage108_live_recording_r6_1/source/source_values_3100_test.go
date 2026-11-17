package main

// The exact Delphi TMVKThread VALUES-file row trigger is a received
// PARAM descriptor at 0x3100, _Unit125.pas 008085A5..008085BD.
// A normal 4700-byte AUX DSP update does NOT itself trigger a source
// VALUES row. This is only verified event provenance, not an invented
// TMvkCellList.GetValueText translation or source Delphi CSV writer.
import (
 "encoding/json"
 "os"
 "path/filepath"
 "testing"
 "time"
)

func TestIDRSourceValuesTriggerIs3100NotAUX4700(t *testing.T) {
 dir:=filepath.Join(t.TempDir(),"TEST_IDR_values")
 m,err:=NewMonitor(dir,"OFFLINE_REPLAY","192.168.0.30")
 if err!=nil{t.Fatal(err)}
 defer m.CloseFiles()
 at:=time.Now()
 if err=m.ProcessChunk(makeAux(),at);err!=nil{t.Fatal(err)}
 if m.summary.Aux4700!=1 || m.summary.ValuesTicks!=0 {
  t.Fatalf("AUX4700 must not become an original VALUES row: AUX=%d, 0x3100=%d",
   m.summary.Aux4700,m.summary.ValuesTicks)
 }
 initial:=m.snapshotLiveStatus("RECORDING",at)
 if initial.SourceValuesTicks!=0 || initial.AUXUpdates!=1{
  t.Fatalf("source VALUES live evidence attributed AUX incorrectly: %+v",initial)
 }
 raw:=makeParam([]RegBlock{{Addr:0x3100,Words:2,Payload:[]byte{0,0,0,0}}})
 if err=m.ProcessChunk(raw,at.Add(time.Millisecond));err!=nil{t.Fatal(err)}
 after:=m.snapshotLiveStatus("RECORDING",at.Add(2*time.Millisecond))
 if after.SourceValuesTicks!=1 || after.AUXUpdates!=1 || m.summary.ValuesTicks!=1 {
  t.Fatalf("source Values trigger not driven by PARAM 0x3100: %+v",after)
 }
}

func TestIDRSourceValuesFramemarkTracks3100EventsIndependentlyOfAUX(t *testing.T){
 m,c:=markFixture(t)
 at:=time.Now()
 if err:=m.ProcessChunk(makeAux(),at);err!=nil{t.Fatal(err)}
 queueMark(t,c,1,"values_begin")
 v:=makeParam([]RegBlock{{Addr:0x3100,Words:2,Payload:[]byte{1,0,0,0}}})
 if err:=m.ProcessChunk(v,at.Add(time.Millisecond));err!=nil{t.Fatal(err)}
 if len(c.records)!=1 || !c.records[0].Applied ||
    c.records[0].SourceValuesTicks!=0 || c.records[0].AUX4700Updates!=1{
  t.Fatalf("original values begin mark before 0x3100 incorrectly timestamped: %+v",c.records)
 }
 queueMark(t,c,2,"values_end")
 if err:=m.ProcessChunk(makeAux(),at.Add(2*time.Millisecond));err!=nil{t.Fatal(err)}
 if len(c.records)!=2 || !c.records[1].Applied ||
    c.records[1].SourceValuesTicks!=1 || c.records[1].AUX4700Updates!=1{
  t.Fatalf("values end mark did not capture 0x3100 without AUX substitution: %+v",c.records)
 }
 report,_,err:=m.Finalize("STOPPED_BY_USER")
 if err!=nil{t.Fatal(err)}
 if report.ValuesTicks!=1 || report.Aux4700!=2{
  t.Fatal("original two counters conflated in summary")
 }
 blob,err:=os.ReadFile(filepath.Join(m.dir,frameMarkAuditName))
 if err!=nil{t.Fatal(err)}
 var audit frameMarkAudit
 if err=json.Unmarshal(blob,&audit);err!=nil{t.Fatal(err)}
 if audit.EndSourceValuesTicks!=1 || audit.EndAUX4700Updates!=2 ||
    audit.Requests[0].SourceValuesTicks!=0 ||
    audit.Requests[1].SourceValuesTicks!=1{
  t.Fatalf("native original row-trigger events missing: %+v",audit)
 }
}
