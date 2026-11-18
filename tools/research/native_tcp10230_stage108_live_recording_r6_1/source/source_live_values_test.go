package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalWriteValuesOnlyAcceptedParam3100WhileWriterIsOpen(t *testing.T){
    m,marks:=markFixture(t)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    at:=time.Date(2026,11,18,12,25,3,123*1000000,time.UTC)
    param:=func(payload []byte)[]byte{
        return makeParam([]RegBlock{{
            Addr:0x3100,Words:uint16(len(payload)/2),Payload:payload,
        }})
    }
    first:=param([]byte{1,2,3,4})
    if e:=m.ProcessChunk(first,at);e!=nil{t.Fatal(e)}
    if m.summary.ValuesTicks!=1 || len(m.sourceLiveValuesWriter.windows)!=0{
        t.Fatal("original WriteValues must not write before checkbox action")
    }
    queueMark(t,marks,1,"values_begin")
    // Non-0x3100 PARAM is NOT the source WriteValues row trigger.
    other:=makeParam([]RegBlock{{Addr:0x1006,Words:2,
        Payload:[]byte{0,0,0,0}}})
    if e:=m.ProcessChunk(other,at.Add(time.Millisecond));e!=nil{t.Fatal(e)}
    if len(m.sourceLiveValuesWriter.windows)!=1 ||
        m.sourceLiveValuesWriter.windows[0].Events!=0{
        t.Fatal("ordinary PARAM unexpectedly created a VALUES row")
    }
    // The writer state is already Stage1; each genuine 0x3100 creates
    // one precise source event. The latest unrelated AUX is not a row.
    event1:=param([]byte{5,6,7,8})
    event2:=param([]byte{9,10,11,12})
    for i,packet:=range [][]byte{event1,event2}{
        if e:=m.ProcessChunk(packet,at.Add(
            time.Duration(i+2)*time.Millisecond));e!=nil{t.Fatal(e)}
    }
    if m.summary.ValuesTicks!=3 ||
       m.sourceLiveValuesWriter.windows[0].Events!=2 {
        t.Fatal("original source 0x3100 tick lost")
    }
    queueMark(t,marks,2,"values_end")
    // Closing operator mark must apply before the next complete ADC.
    if e:=m.ProcessChunk(syntheticFrame(0,0,1).Raw,
        at.Add(4*time.Millisecond));e!=nil{t.Fatal(e)}
    if m.sourceLiveValuesWriter.active!=nil {t.Fatal("VALUES writer not closed")}
    report,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    if report.SourceLiveValuesWindows!=1 ||
        report.SourceLiveValuesEventRecords!=2 ||
        report.SourceLiveValuesAuditSHA256=="" || !report.ReadOnly{
        t.Fatalf("real VALUES source audit not in summary: %+v",report)
    }
    p:=filepath.Join(m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl")
    data,e:=os.ReadFile(p)
    if e!=nil{t.Fatal(e)}
    lines:=bytes.Split(bytes.TrimSuffix(data,[]byte("\n")),[]byte("\n"))
    if len(lines)!=2 {t.Fatalf("events=%d expected 2",len(lines))}
    for i,line:=range lines{
        var v sourceLiveValuesEvent
        if e=json.Unmarshal(line,&v);e!=nil{t.Fatal(e)}
        if v.FrameIndex!=uint64(i+3) ||
            v.TickIndex!=uint64(i+1) ||
            v.Words!=2 || v.Address!="0x3100"{
            t.Fatalf("wrong original source event: %+v",v)
        }
    }
    auditBytes,e:=os.ReadFile(filepath.Join(m.dir,sourceLiveValuesAuditName))
    if e!=nil{t.Fatal(e)}
    sum:=sha256.Sum256(auditBytes)
    if report.SourceLiveValuesAuditSHA256!=hex.EncodeToString(sum[:]){
        t.Fatal("source VALUES audit SHA not linked to Go summary")
    }
    var doc sourceLiveValuesAudit
    if e=json.Unmarshal(auditBytes,&doc);e!=nil{t.Fatal(e)}
    if doc.SourceRawSHA256!=report.RawSHA256 ||
        doc.OriginalDelphiGetValueTextParity ||
        doc.OriginalDelphiTimeParity ||
        len(doc.Windows)!=1 || doc.Windows[0].Events!=2 ||
        doc.Windows[0].BeginTick!=1 || doc.Windows[0].EndTick!=3 ||
        doc.Windows[0].Outcome!="CLOSED_BY_OPERATOR" ||
        !doc.Windows[0].Channels[0] || !doc.Windows[0].Values[0] {
        t.Fatalf("source VALUES writer falsely attributed provenance %+v",doc)
    }
}

func TestOriginalWriteValuesStopClosesActiveOnlyWhenClean(t *testing.T){
    for _,scenario:=range []struct{reason,want string}{
        {"STOPPED_BY_USER","CLOSED_BY_SOURCE_THREAD"},
        {"REMOTE_DISCONNECTED","INTERRUPTED"},
    }{
        t.Run(scenario.reason,func(t *testing.T){
            m,c:=markFixture(t)
            m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
            queueMark(t,c,1,"values_begin")
            tick:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
                Payload:[]byte{5,4,3,2}}})
            if e:=m.ProcessChunk(tick,time.Now());e!=nil{t.Fatal(e)}
            report,_,e:=m.Finalize(scenario.reason)
            if e!=nil{t.Fatal(e)}
            if report.SourceLiveValuesEventRecords!=1{t.Fatal("lost 3100 tick")}
            buf,e:=os.ReadFile(filepath.Join(m.dir,sourceLiveValuesAuditName))
            if e!=nil{t.Fatal(e)}
            var doc sourceLiveValuesAudit
            if e=json.Unmarshal(buf,&doc);e!=nil{t.Fatal(e)}
            if len(doc.Windows)!=1 || doc.Windows[0].Outcome!=scenario.want ||
                doc.Windows[0].Events!=1 || doc.Windows[0].EndTick!=1{
                t.Fatalf("false original source close: %+v",doc)
            }
        })
    }
}
