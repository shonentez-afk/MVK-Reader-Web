package main

// Source: private _Unit125.pas:008089A8 on thread unwind invokes
// WriteData/WriteValues with forced-stop.  The local recorder does not
// fabricate an operator click or a TCP frame; it keeps a distinct
// SHA-bound final-counter receipt, not an original Delphi BIN.
import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSourceWriteDataAndValuesForcedCloseOnCleanTask2Stop(t *testing.T) {
    m,marks:=markFixture(t)
    now:=time.Now()
    if e:=m.ProcessChunk(syntheticFrame(0,0,1).Raw,now);e!=nil {
        t.Fatal(e)
    }
    queueMark(t,marks,1,"data_begin")
    queueMark(t,marks,2,"values_begin")
    // Both operator BEGIN flags take effect BEFORE this actual frame.
    tick:=makeParam([]RegBlock{{Addr:0x3100,Words:2,Payload:[]byte{1,0,0,0}}})
    if e:=m.ProcessChunk(tick,now.Add(time.Millisecond));e!=nil {
        t.Fatal(e)
    }
    if len(marks.records)!=2 || marks.records[0].FramesDecoded!=1 ||
        !marks.records[0].Applied || !marks.records[1].Applied ||
        marks.records[1].SourceValuesTicks!=0 || m.summary.ValuesTicks!=1 {
        t.Fatalf("source writer BEGIN not on verified Go frame: %+v",marks.records)
    }
    if e:=m.ProcessChunk(syntheticFrame(0,256,2).Raw,now.Add(2*time.Millisecond));e!=nil {
        t.Fatal(e)
    }
    summary,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil {t.Fatal(e)}
    data,e:=os.ReadFile(filepath.Join(m.dir,frameMarkAuditName))
    if e!=nil {t.Fatal(e)}
    digest:=sha256.Sum256(data)
    if hex.EncodeToString(digest[:])!=summary.FrameMarksSHA256 ||
        summary.FrameMarkCount!=2 || summary.ValuesTicks!=1 || !summary.ReadOnly {
        t.Fatal("forced close changed operator event count or RAW digest")
    }
    var doc frameMarkAudit
    if e=json.Unmarshal(data,&doc);e!=nil {t.Fatal(e)}
    if len(doc.Requests)!=2 || len(doc.AutoClosed)!=2 ||
        doc.AutoClosed[0].Event!="data_end" ||
        doc.AutoClosed[1].Event!="values_end" ||
        doc.AutoClosed[0].SourceValuesTicks!=1 ||
        doc.AutoClosed[1].FramesDecoded!=summary.TotalFrames {
        t.Fatalf("original Task2 forced close evidence not emitted: %+v",doc.AutoClosed)
    }
    for _,closed:=range doc.AutoClosed{
        if !closed.Applied ||
            closed.Boundary!="AT_SOURCE_TASK2_FINALIZE" ||
            closed.Reason!="SOURCE_TMVKTHREAD_FORCED_WRITER_CLOSE" ||
            closed.RequestedUTC!=summary.EndedUTC ||
            closed.ChannelSamples[0]!=512 || closed.SourceReadOnly ||
            !closed.Channels[0] || !closed.Spec[0] || !closed.Values[0] {
            t.Fatalf("source writer close is not final real counter: %+v",closed)
        }
    }
    if summary.RawBytes!=uint64(1052+len(tick)+1052) ||
        doc.SourceRawSHA256!=summary.RawSHA256 {
        t.Fatal("source final-write receipt changed full packet source")
    }
}

func TestSourceWriterForcedCloseCannotInventAbnormalThreadEnd(t *testing.T) {
    m,marks:=markFixture(t)
    queueMark(t,marks,1,"values_begin")
    if e:=m.ProcessChunk(syntheticFrame(0,0,1).Raw,time.Now());e!=nil {
        t.Fatal(e)
    }
    summary,_,e:=m.Finalize("REMOTE_DISCONNECTED")
    if e!=nil {t.Fatal(e)}
    data,e:=os.ReadFile(filepath.Join(m.dir,frameMarkAuditName))
    if e!=nil {t.Fatal(e)}
    var doc frameMarkAudit
    if e=json.Unmarshal(data,&doc);e!=nil {t.Fatal(e)}
    if len(doc.AutoClosed)!=0 || len(doc.Requests)!=1 ||
        summary.FrameMarkCount!=1 ||
        summary.EndReason!="REMOTE_DISCONNECTED" {
        t.Fatal("unverified source disconnect must not pretend a clean CLOSE")
    }
}
