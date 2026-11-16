package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func markFixture(t *testing.T) (*Monitor,*frameMarkController) {
    t.Helper()
    root:=t.TempDir()
    dir:=filepath.Join(root,"TEST_2026-11-16_10-01-00.000")
    mon,err:=NewMonitor(dir,"OFFLINE_REPLAY","192.0.2.84")
    if err!=nil {t.Fatal(err)}
    control,err:=newFrameMarkController(root,dir)
    if err!=nil {t.Fatal(err)}
    mon.frameMarks=control
    return mon,control
}

func queueMark(t *testing.T,c *frameMarkController,sequence int,kind string) {
    t.Helper()
    ch:=make([]bool,10);for i:=0;i<10;i++ {ch[i]=true}
    spec:=make([]bool,43);for i:=0;i<43;i++ {spec[i]=true}
    values:=make([]bool,73);for i:=0;i<67;i++ {values[i]=true}
    req:=frameMarkRequest{
        Schema:frameMarkRequestSchema,Sequence:sequence,
        SessionID:filepath.Base(filepath.Dir(c.inbox)),
        Event:kind,RequestedUTC:"2026-11-16T08:00:00Z",
        Channels:ch,Spec:spec,Values:values,
    }
    // c.inbox is <root>/.mvk_frame_marks_inbox, NOT run dir.
    // caller supplies exact validated run identity in the test.
    req.SessionID="TEST_2026-11-16_10-01-00.000"
    data,err:=json.Marshal(req);if err!=nil {t.Fatal(err)}
    file:=filepath.Join(c.inbox,
        fmtSeq(sequence))
    if err=os.WriteFile(file,data,0600);err!=nil {t.Fatal(err)}
}

func fmtSeq(sequence int) string {
    if sequence<10 { return "000"+string(rune('0'+sequence))+".json" }
    return "0010.json"
}

func TestSourceFrameMarksExecuteOnlyAtActualNextDecodedFrame(t *testing.T) {
    m,c:=markFixture(t)
    now:=time.Date(2026,11,16,8,30,0,0,time.UTC)
    frame:=syntheticFrame(0,0,1.25)
    if err:=m.ProcessChunk(frame.Raw,now);err!=nil {t.Fatal(err)}
    if m.summary.Channels[0].Samples!=256 {t.Fatal("seed frame missing")}
    queueMark(t,c,1,"data_begin")
    // No complete frame => no authoritative local mark.
    if err:=m.ProcessChunk([]byte{},now.Add(time.Millisecond));err!=nil {t.Fatal(err)}
    if len(c.records)!=0 {t.Fatal("operator click was assigned to cached status")}
    if err:=m.ProcessChunk(syntheticFrame(0,256,2).Raw,now.Add(2*time.Millisecond));err!=nil {
        t.Fatal(err)
    }
    if len(c.records)!=1 || !c.records[0].Applied ||
       c.records[0].FramesDecoded!=1 || c.records[0].ChannelSamples[0]!=256 {
        t.Fatalf("not boundary of NEXT complete frame: %+v",c.records)
    }
    queueMark(t,c,2,"data_end")
    if err:=m.ProcessChunk(syntheticFrame(8,0,3).Raw,now.Add(3*time.Millisecond));err!=nil {
        t.Fatal(err)
    }
    if len(c.records)!=2 || !c.records[1].Applied ||
       c.records[1].ChannelSamples[0]!=512 ||
       c.records[1].ChannelSamples[8]!=0 {
        t.Fatalf("second boundary was not before next TACH packet: %+v",
            c.records)
    }
    report,_,err:=m.Finalize("STOPPED_BY_USER")
    if err!=nil {t.Fatal(err)}
    if report.FrameMarksSHA256=="" || report.FrameMarkCount!=2 ||
       !report.ReadOnly {t.Fatalf("lost frame mark SHA/status %+v",report)}
    data,err:=os.ReadFile(filepath.Join(m.dir,frameMarkAuditName))
    if err!=nil {t.Fatal(err)}
    h:=sha256.Sum256(data)
    if report.FrameMarksSHA256!=hex.EncodeToString(h[:]) {
        t.Fatal("source mark record digest not linked to captured RAW")
    }
    var audit frameMarkAudit
    if err=json.Unmarshal(data,&audit);err!=nil {t.Fatal(err)}
    if audit.DeviceCommandsSent || audit.OriginalDelphiFileParityVerified ||
       !audit.SourceFrameBoundary || audit.SourceRawSHA256!=report.RawSHA256 ||
       len(audit.Requests)!=2 || audit.Requests[1].Event!="data_end" ||
       audit.EndChannelSamples[8]!=64 {
        t.Fatalf("source hardware parity falsely asserted: %+v",audit)
    }
}

func TestMalformedOrMissingFrameMarkFailsClosedWithoutRawLoss(t *testing.T) {
    m,c:=markFixture(t)
    now:=time.Now()
    if err:=m.ProcessChunk(syntheticFrame(0,0,1).Raw,now);err!=nil {
        t.Fatal(err)
    }
    if err:=os.WriteFile(c.pendingName(),[]byte("{invalid!"),0600);err!=nil {
        t.Fatal(err)
    }
    if err:=m.ProcessChunk(syntheticFrame(0,256,1).Raw,now);err!=nil {
        t.Fatal(err)
    }
    if len(c.records)!=1 || c.records[0].Applied ||
       m.summary.Channels[0].Samples!=512 {
        t.Fatalf("rejected local mark corrupted read-only RAW: %+v",c.records)
    }
    queueMark(t,c,2,"data_begin")
    report,_,err:=m.Finalize("STOPPED_BY_USER")
    if err!=nil {t.Fatal(err)}
    if report.RawBytes==0 || report.FrameMarkCount!=2 {
        t.Fatal("missing pending rejection audit")
    }
    data,_:=os.ReadFile(filepath.Join(m.dir,frameMarkAuditName))
    var audit frameMarkAudit
    if err=json.Unmarshal(data,&audit);err!=nil {t.Fatal(err)}
    if audit.Requests[1].Applied || audit.Requests[1].Boundary!="NO_FRAME_NO_MARK" ||
       audit.DeviceCommandsSent {t.Fatal("invented final frame boundary")}
}

func TestNoRequestsPreserveHistoricalNativeCaptureLayout(t *testing.T) {
    m,_:=markFixture(t)
    now:=time.Now()
    if err:=m.ProcessChunk(syntheticFrame(0,0,1).Raw,now);err!=nil {
        t.Fatal(err)
    }
    report,_,err:=m.Finalize("STOPPED_BY_USER");if err!=nil {t.Fatal(err)}
    if report.FrameMarksSHA256!="" || report.FrameMarkCount!=0 {
        t.Fatal("empty source sidecar must not alter old run summary")
    }
    if _,err:=os.Stat(filepath.Join(m.dir,frameMarkAuditName));!os.IsNotExist(err) {
        t.Fatal("empty mark audit file fabricated")
    }
}
