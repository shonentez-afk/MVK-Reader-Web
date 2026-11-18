package main

// Stage111Z31FS. Original _Unit125.pas TMVKThread.Execute:
//  00807F6A calls WriteData stage handler BEFORE every ReadUInt32;
//  0080822F..0080824B gates received samples by MvkSampleRate and
//  FreezeUpdate; 00808291..008082A3 changes Stage0->1 ONLY on accepted
//  ADC1; 008082AA..008082DE writes selected TmpStream.FMemory bytes.
// This module DOES write those accepted wire bytes at receive time. It
// is local disk I/O and NEVER generates a device command or socket.
//
// Provenance: original mvkview.idp + Projects.7z/_Unit125.pas,
// _Unit128.pas + mvk_idr(1).sqlite. The GUI mark is still applied at
// the next complete Go application frame, not the exact Win32 click tick.
// Do not label output as byte-identical original Delphi filenames/TSXML.
import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "hash"
    "os"
    "path/filepath"
    "time"
)

const sourceLiveWriterSchema="MVK_SOURCE_TMVKTHREAD_LIVE_WRITEDATA_V1"
const sourceLiveWriterAudit="SOURCE_LIVE_WRITEDATA_NATIVE_AUDIT.json"
const sourceLiveWriterPackets="SOURCE_LIVE_WRITEDATA_PACKET_GATE.jsonl"

type sourceLiveDataFile struct {
    Channel int `json:"channel"`
    Name string `json:"name"`
    Bytes uint64 `json:"bytes"`
    Packets uint64 `json:"packets"`
    SHA256 string `json:"sha256"`
    file *os.File
    digest hash.Hash
}
type sourceLiveDataWindow struct {
    Window int `json:"window"`
    BeginOperatorSequence int `json:"begin_operator_sequence"`
    EndOperatorSequence int `json:"end_operator_sequence,omitempty"`
    BeginBeforeFrame uint64 `json:"begin_before_frame"`
    EndAfterFrame uint64 `json:"end_after_frame"`
    FirstAcceptedADC1Frame uint64 `json:"first_accepted_adc1_frame,omitempty"`
    StageAtEnd int `json:"stage_at_end"`
    Outcome string `json:"outcome"`
    Channels [10]bool `json:"channels"`
    WrittenPackets uint64 `json:"written_packets"`
    SkippedRate uint64 `json:"skipped_rate_packets"`
    SkippedFrozen uint64 `json:"skipped_frozen_packets"`
    SkippedBeforeADC1 uint64 `json:"skipped_before_adc1_packets"`
    Files []*sourceLiveDataFile `json:"files"`
    stage int
}
type sourceLiveDataPacket struct {
    Frame uint64 `json:"frame_index"`
    Window int `json:"window"`
    Channel int `json:"channel"`
    SampleWords int `json:"sample_words"`
    RXBefore uint64 `json:"rx_sample_before"`
    RXAfter uint64 `json:"rx_sample_after"`
    SourceRate uint32 `json:"source_selected_rate_hz"`
    PacketRate uint32 `json:"received_rate_hz"`
    Freeze bool `json:"freeze_update"`
    SourceGate bool `json:"source_ring_store_allowed"`
    StageBefore int `json:"write_data_stage_before"`
    StageAfter int `json:"write_data_stage_after"`
    ChannelSelected bool `json:"channel_selected"`
    Wrote bool `json:"wrote_source_bytes"`
    PayloadSHA256 string `json:"rx_payload_sha256"`
}
type sourceLiveDataAudit struct {
    Schema string `json:"schema"`
    Session string `json:"session_id"`
    SourceRawSHA256 string `json:"source_raw_sha256"`
    EndFrames uint64 `json:"end_frames_decoded"`
    EndChannels [10]uint64 `json:"end_channel_samples"`
    EndReason string `json:"end_reason"`
    PacketGateFile string `json:"packet_gate_file"`
    PacketGateSHA256 string `json:"packet_gate_sha256"`
    PacketGateRecords uint64 `json:"packet_gate_records"`
    Windows []*sourceLiveDataWindow `json:"windows"`
    OriginalDelphiByteParityVerified bool `json:"original_delphi_file_parity_verified"`
    LiveRateAndFreezeObserved bool `json:"live_source_rate_freeze_recorded"`
    OperatorClickTimingParityVerified bool `json:"original_win32_click_timing_verified"`
}

type sourceLiveDataWriter struct {
    dir string
    nextMark int
    nextWindow int
    active *sourceLiveDataWindow
    windows []*sourceLiveDataWindow
    packetFile *os.File
    packetSum hash.Hash
    packetCount uint64
    closed bool
}
func newSourceLiveDataWriter(dir string)*sourceLiveDataWriter {
    return &sourceLiveDataWriter{dir:dir,packetSum:sha256.New()}
}
func (w *sourceLiveDataWriter) applyFrameMarks(m *Monitor)error {
    if w==nil || m.frameMarks==nil || w.closed {return nil}
    for w.nextMark<len(m.frameMarks.records) {
        mark:=m.frameMarks.records[w.nextMark]
        w.nextMark++
        if !mark.Applied {continue}
        switch mark.Event {
        case "data_begin":
            if w.active!=nil || w.nextWindow>=8 {
                return errors.New("original source WriteData duplicate start/too many windows")
            }
            if m.sourceOriginalRXGate==nil {
                return errors.New("original source WriteData needs live rate/freeze gate")
            }
            w.nextWindow++
            entry:=&sourceLiveDataWindow{
                Window:w.nextWindow,BeginOperatorSequence:mark.Sequence,
                BeginBeforeFrame:m.summary.TotalFrames,Channels:mark.Channels,
                stage:0,Outcome:"ACTIVE",
            }
            selected:=0
            for channel,chosen:=range mark.Channels {
                if !chosen {continue}
                selected++
                kind,index:="ADC",channel+1
                if channel>=8 {kind,index="TACH",channel-7}
                name:=fmt.Sprintf("SOURCE_W%02d_%s%d_LIVE_RX_UNSCALED.bin",
                    entry.Window,kind,index)
                f,e:=os.OpenFile(filepath.Join(w.dir,name),
                    os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
                if e!=nil {return e}
                entry.Files=append(entry.Files,&sourceLiveDataFile{
                    Channel:channel+1,Name:name,file:f,digest:sha256.New()})
                m.filenames=append(m.filenames,name)
                m.summary.Files[name]=name
            }
            if selected==0 {return errors.New("original WriteData has no selected channels")}
            if w.packetFile==nil {
                f,e:=os.OpenFile(filepath.Join(w.dir,sourceLiveWriterPackets),
                    os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
                if e!=nil{return e}
                w.packetFile=f
                m.filenames=append(m.filenames,sourceLiveWriterPackets)
                m.summary.Files[sourceLiveWriterPackets]=sourceLiveWriterPackets
            }
            w.active=entry
            w.windows=append(w.windows,entry)
        case "data_end":
            if w.active==nil {
                return errors.New("source WriteData end without an active begin")
            }
            w.active.EndOperatorSequence=mark.Sequence
            if e:=w.closeWindow(m,"CLOSED_BY_OPERATOR");e!=nil{return e}
        case "values_begin","values_end":
            // Source WriteValues is a separate original stage machine.
        default:
            return errors.New("unknown source frame-mark action in WriteData")
        }
    }
    return nil
}
func (w *sourceLiveDataWriter) onSample(m *Monitor,
    sample SampleHeader,payload []byte,gateAllowed bool) error {
    if w==nil || w.active==nil || w.closed || sample.Samples==0 {return nil}
    if len(payload)!=sample.Samples*4 || m.sourceOriginalRXGate==nil {
        return errors.New("source WriteData sample body/gate unavailable")
    }
    state:=w.active
    g:=m.sourceOriginalRXGate
    expected:=!g.frozen && sample.Rate==g.rate
    if expected!=gateAllowed {
        return errors.New("original WriteData gate differs from live channel storage")
    }
    before:=state.stage
    written:=false
    if !gateAllowed {
        if g.frozen {state.SkippedFrozen++} else {state.SkippedRate++}
    } else {
        // Do not start on ADC2..ADC8 or TACH; only ADC1 (channel 0)
        // advances Stage0 -> Stage1, and the same packet is written.
        if state.stage==0 && sample.Channel==0 {
            state.stage=1
            state.FirstAcceptedADC1Frame=m.summary.TotalFrames
        }
        if state.stage==0 {state.SkippedBeforeADC1++}
        if state.stage==1 && state.Channels[sample.Channel] {
            for _,file:=range state.Files {
                if file.Channel!=sample.Channel+1 {continue}
                n,e:=file.file.Write(payload)
                if e!=nil{return e}
                if n!=len(payload){return errors.New("source WriteData short file write")}
                _,_=file.digest.Write(payload)
                file.Bytes+=uint64(n);file.Packets++
                written=true
                state.WrittenPackets++
                break
            }
            if !written{return errors.New("original selected channel file missing")}
        }
    }
    rxAfter:=m.summary.Channels[sample.Channel].Samples
    if rxAfter<uint64(sample.Samples) {
        return errors.New("source WriteData received sample counter underflow")
    }
    dataDigest:=sha256.Sum256(payload)
    record:=sourceLiveDataPacket{
        Frame:m.summary.TotalFrames,Window:state.Window,
        Channel:sample.Channel+1,SampleWords:sample.Samples,
        RXBefore:rxAfter-uint64(sample.Samples),RXAfter:rxAfter,
        SourceRate:g.rate,PacketRate:sample.Rate,
        Freeze:g.frozen,SourceGate:gateAllowed,
        StageBefore:before,StageAfter:state.stage,
        ChannelSelected:state.Channels[sample.Channel],
        Wrote:written,PayloadSHA256:hex.EncodeToString(dataDigest[:]),
    }
    bytes,e:=json.Marshal(record)
    if e!=nil{return e}
    bytes=append(bytes,'\n')
    n,e:=w.packetFile.Write(bytes)
    if e!=nil{return e}
    if n!=len(bytes){return errors.New("source WriteData packet audit short write")}
    _,_=w.packetSum.Write(bytes)
    w.packetCount++
    return nil
}
func (w *sourceLiveDataWriter) closeWindow(m *Monitor,outcome string)error {
    if w.active==nil{return nil}
    window:=w.active
    window.EndAfterFrame=m.summary.TotalFrames
    window.StageAtEnd=window.stage
    window.Outcome=outcome
    var first error
    for _,f:=range window.Files {
        if f.file!=nil {
            if e:=f.file.Close();e!=nil && first==nil{first=e}
            f.file=nil
        }
        f.SHA256=hex.EncodeToString(f.digest.Sum(nil))
    }
    w.active=nil
    return first
}
func(w *sourceLiveDataWriter) finalize(m *Monitor)error {
    if w==nil || w.closed{return nil}
    w.closed=true
    clean:=(m.summary.EndReason=="STOPPED_BY_USER" ||
        m.summary.EndReason=="DURATION_REACHED" ||
        m.summary.EndReason=="SIZE_LIMIT_REACHED") && !m.captureOnly &&
        !m.summary.SourceTCPMultiSocket
    if w.active!=nil {
        outcome:="INTERRUPTED"
        if clean {outcome="CLOSED_BY_SOURCE_THREAD"}
        if e:=w.closeWindow(m,outcome);e!=nil{return e}
    }
    if w.packetFile!=nil {
        if e:=w.packetFile.Close();e!=nil{return e}
        w.packetFile=nil
    }
    if len(w.windows)==0{return nil}
    doc:=sourceLiveDataAudit{
        Schema:sourceLiveWriterSchema,
        Session:filepath.Base(m.dir),
        SourceRawSHA256:m.summary.RawSHA256,
        EndFrames:m.summary.TotalFrames,
        EndReason:m.summary.EndReason,
        PacketGateFile:sourceLiveWriterPackets,
        PacketGateSHA256:hex.EncodeToString(w.packetSum.Sum(nil)),
        PacketGateRecords:w.packetCount,
        Windows:w.windows,LiveRateAndFreezeObserved:true,
        OriginalDelphiByteParityVerified:false,
        OperatorClickTimingParityVerified:false,
    }
    for i:=0;i<10;i++{doc.EndChannels[i]=m.summary.Channels[i].Samples}
    encoded,e:=json.MarshalIndent(doc,"","  ")
    if e!=nil{return e}
    encoded=append(encoded,'\n')
    if e=os.WriteFile(filepath.Join(w.dir,sourceLiveWriterAudit),
        encoded,0600);e!=nil{return e}
    digest:=sha256.Sum256(encoded)
    m.summary.SourceLiveWriteDataAuditSHA256=hex.EncodeToString(digest[:])
    m.summary.SourceLiveWriteDataWindows=uint64(len(w.windows))
    m.summary.SourceLiveWriteDataPacketRecords=w.packetCount
    m.filenames=append(m.filenames,sourceLiveWriterAudit)
    m.summary.Files[sourceLiveWriterAudit]=sourceLiveWriterAudit
    return nil
}

// cleanup closes locally opened output handles on a nonfinalized error.
// It never writes network bytes or deletes the forensic incoming.raw.
func(w *sourceLiveDataWriter) cleanup(){
    if w==nil{return}
    for _,win:=range w.windows {
        for _,f:=range win.Files {
            if f.file!=nil{_ = f.file.Close();f.file=nil}
        }
    }
    if w.packetFile!=nil {_ = w.packetFile.Close();w.packetFile=nil}
}
var _ = time.Time{} // no wall-clock reconstruction of Delphi click time
