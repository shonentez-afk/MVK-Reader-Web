package main

// Stage111Z31DA: local operator write boundaries on the NEXT COMPLETE
// original application frame. This is NOT the Delphi TMVKThread
// Cmd/Addr/Data command queue: nothing here writes to TCP or a device.
// Only the existing, single, read-only Go TCP/10230 reader consumes this
// local GUI inbox. Incoming.raw and source 8 ADC + 2 TACH streams are
// ALWAYS recorded in full irrespective of any local checkbox selections.
//
// Atomic command files are read at the start of a ProcessChunk containing
// at least one fully reassembled application frame. This guarantees
// sample/AUX counts at an actual decoded frame boundary, NOT a sample
// guessed from the 750ms Go JSON status snapshot. It does NOT guarantee
// instant click-to-device timing: network/read-loop latency still applies.

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "strings"
    "time"
)

const frameMarkRequestSchema = "MVK_NATIVE_LOCAL_FRAME_MARK_REQUEST_V1"
const frameMarkAuditSchema = "MVK_NATIVE_LOCAL_FRAME_MARK_AUDIT_V1"
const frameMarkInboxName = ".mvk_frame_marks_inbox"
const frameMarkAuditName = "SOURCE_FRAME_MARKS_NATIVE.json"
const frameMarkLimit = 64
const frameMarkMaxRequestBytes = 4096

type frameMarkRequest struct {
    Schema string `json:"schema"`
    Sequence int `json:"sequence"`
    SessionID string `json:"session_id"`
    Event string `json:"event"`
    RequestedUTC string `json:"requested_utc"`
    Channels []bool `json:"channels"`
    Spec []bool `json:"spec"`
    Values []bool `json:"values"`
}
type frameMarkReceipt struct {
    Sequence int `json:"sequence"`
    Event string `json:"event"`
    RequestedUTC string `json:"requested_utc"`
    AppliedUTC string `json:"applied_utc"`
    Applied bool `json:"applied"`
    Reason string `json:"reason,omitempty"`
    FramesDecoded uint64 `json:"frames_decoded"`
    AUX4700Updates uint64 `json:"aux4700_updates"`
    ChannelSamples [10]uint64 `json:"channel_samples"`
    Channels [10]bool `json:"channels"`
    Spec [43]bool `json:"spec"`
    Values [73]bool `json:"values"`
    SourceReadOnly bool `json:"device_commands_sent"`
    Boundary string `json:"boundary"`
}

type frameMarkAudit struct {
    Schema string `json:"schema"`
    SessionID string `json:"session_id"`
    SourceRawSHA256 string `json:"source_raw_sha256"`
    EndFramesDecoded uint64 `json:"end_frames_decoded"`
    EndAUX4700Updates uint64 `json:"end_aux4700_updates"`
    EndChannelSamples [10]uint64 `json:"end_channel_samples"`
    DeviceCommandsSent bool `json:"device_commands_sent"`
    SourceFrameBoundary bool `json:"source_frame_boundary"`
    OriginalDelphiFileParityVerified bool `json:"original_delphi_file_parity_verified"`
    Requests []frameMarkReceipt `json:"requests"`
}

type frameMarkController struct {
    inbox string
    next int
    records []frameMarkReceipt
    failures []string
}

func newFrameMarkController(outRoot, runDir string) (*frameMarkController,error) {
    // Root must be the same root already accepted for the read-only Go
    // recording. Never accept an arbitrary IPC/network path.
    root,err:=filepath.Abs(outRoot)
    if err!=nil {return nil,err}
    run,err:=filepath.Abs(runDir)
    if err!=nil {return nil,err}
    if filepath.Dir(run)!=root {
        return nil,errors.New("source frame mark inbox not parent of this run")
    }
    info,err:=os.Lstat(root)
    if err!=nil || !info.IsDir() || info.Mode()&os.ModeSymlink!=0 {
        return nil,errors.New("unsafe source frame mark directory root")
    }
    inbox:=filepath.Join(root,frameMarkInboxName)
    if err:=os.Mkdir(inbox,0700);err!=nil {
        return nil,fmt.Errorf("source frame mark inbox must be new: %w",err)
    }
    return &frameMarkController{inbox:inbox,next:1},nil
}

func (c *frameMarkController) pendingName() string {
    return filepath.Join(c.inbox,fmt.Sprintf("%04d.json",c.next))
}

func validMarkRequest(r frameMarkRequest,seq int,run string) error {
    if r.Schema!=frameMarkRequestSchema || r.Sequence!=seq ||
       r.SessionID!=run || len(r.Channels)!=10 || len(r.Spec)!=43 ||
       len(r.Values)!=73 {
        return errors.New("request schema, sequence, run or source flags mismatch")
    }
    if r.Event!="data_begin" && r.Event!="data_end" &&
       r.Event!="values_begin" && r.Event!="values_end" {
        return errors.New("unknown original source button action")
    }
    if len(r.RequestedUTC)>80 || r.RequestedUTC=="" {
        return errors.New("missing operator UTC")
    }
    if _,err:=time.Parse(time.RFC3339Nano,r.RequestedUTC);err!=nil {
        return errors.New("invalid operator UTC")
    }
    selected:=0
    for _,v:=range r.Channels {if v {selected++}}
    if selected==0 {
        return errors.New("zero source channels in original write request")
    }
    return nil
}

func (c *frameMarkController) poll(m *Monitor,at time.Time) {
    if c==nil || c.next>frameMarkLimit || m.captureOnly {return}
    // A request is only accepted when there is a real, complete next
    // MVK application frame. No frames means no fictitious boundary.
    for c.next<=frameMarkLimit {
        path:=c.pendingName()
        info,err:=os.Lstat(path)
        if errors.Is(err,os.ErrNotExist) {break}
        if err!=nil {
            c.failures=append(c.failures,"inbox unreadable: "+err.Error())
            break
        }
        receipt:=frameMarkReceipt{
            Sequence:c.next,AppliedUTC:at.UTC().Format(time.RFC3339Nano),
            SourceReadOnly:m.sourceTask2TX!=nil && m.sourceTask2TX.sentBytes>0,
            Boundary:"BEFORE_NEXT_REASSEMBLED_APPLICATION_FRAME",
        }
        receipt.FramesDecoded=m.summary.TotalFrames
        receipt.AUX4700Updates=m.summary.Aux4700
        for i:=0;i<10;i++ {receipt.ChannelSamples[i]=m.summary.Channels[i].Samples}
        if !info.Mode().IsRegular() || info.Size()>frameMarkMaxRequestBytes {
            receipt.Reason="nonregular or oversized local request"
        } else {
            bytes,e:=os.ReadFile(path)
            if e!=nil {
                receipt.Reason="unreadable local request"
            } else {
                var request frameMarkRequest
                if e=json.Unmarshal(bytes,&request);e!=nil {
                    receipt.Reason="invalid JSON command"
                } else if e=validMarkRequest(request,c.next,filepath.Base(m.dir));e!=nil {
                    receipt.Reason=e.Error()
                } else {
                    receipt.Event=request.Event
                    receipt.RequestedUTC=request.RequestedUTC
                    copy(receipt.Channels[:],request.Channels)
                    copy(receipt.Spec[:],request.Spec)
                    copy(receipt.Values[:],request.Values)
                    receipt.Applied=true
                }
            }
        }
        if !receipt.Applied {
            c.failures=append(c.failures,fmt.Sprintf("operator request %d rejected: %s",
                c.next,receipt.Reason))
        }
        c.records=append(c.records,receipt)
        c.next++
        // Never remove a request that may be required for forensic
        // post-capture QA; Qt's local inbox belongs to this run only.
        // Multiple already-queued clicks share the same NEXT frame boundary,
        // and are ordered by increasing sequence.
    }
}

func (c *frameMarkController) finalize(m *Monitor) error {
    if c==nil {return nil}
    if len(c.records)==0 && c.next==1 {
        // A command may have arrived after the FINAL complete packet.
        // It still deserves an explicit rejected receipt, not a missing
        // audit that the operator could mistake for an empty session.
        _,err:=os.Lstat(c.pendingName())
        if errors.Is(err,os.ErrNotExist) {return nil}
        if err!=nil {return err}
    }
    // The final event cannot silently use the previous 900ms status
    // count. Pending requests without an incoming complete frame are
    // explicitly REJECTED (they cannot be exported as selected windows).
    for c.next<=frameMarkLimit {
        path:=c.pendingName()
        _,err:=os.Lstat(path)
        if errors.Is(err,os.ErrNotExist) {break}
        if err!=nil {return err}
        c.records=append(c.records,frameMarkReceipt{
            Sequence:c.next,Applied:false,Reason:"no next complete frame before capture end",
            AppliedUTC:time.Now().UTC().Format(time.RFC3339Nano),
            Boundary:"NO_FRAME_NO_MARK",SourceReadOnly:false})
        c.next++
    }
    if len(c.records)==0 {return nil}
    doc:=frameMarkAudit{
        Schema:frameMarkAuditSchema,
        SessionID:filepath.Base(m.dir),
        SourceRawSHA256:m.summary.RawSHA256,
        EndFramesDecoded:m.summary.TotalFrames,
        EndAUX4700Updates:m.summary.Aux4700,
        DeviceCommandsSent:m.sourceTask2TX!=nil && m.sourceTask2TX.sentBytes>0,
        SourceFrameBoundary:true,
        OriginalDelphiFileParityVerified:false,
        Requests:c.records,
    }
    for i:=0;i<10;i++ {doc.EndChannelSamples[i]=m.summary.Channels[i].Samples}
    data,err:=json.MarshalIndent(doc,"","  ")
    if err!=nil {return err}
    data=append(data,byte(10))
    if err=os.WriteFile(filepath.Join(m.dir,frameMarkAuditName),data,0600);err!=nil {
        return err
    }
    hash:=sha256.Sum256(data)
    m.summary.FrameMarksSHA256=hex.EncodeToString(hash[:])
    m.summary.FrameMarkCount=uint64(len(c.records))
    m.filenames=append(m.filenames,frameMarkAuditName)
    for _,r:=range c.records {
        if !r.Applied {m.warn(fmt.Sprintf(
            "Operator source frame mark %d rejected; local selection cannot be exported: %s",
            r.Sequence,strings.TrimSpace(r.Reason)))}
    }
    return nil
}
