package main

// Mode2 original WriteValues LIVE trigger capture. Private triple source:
// _Unit125:008085A5..008085BD writes a row ONLY on PARAM address 0x3100,
// _Unit125:008066F0 formats text, _Unit125:00809414/00809814 owns file
// open/close; _Unit128:0084E988 copies selected result flags.
// Since TMvkCellList.GetValueText may select vendor-specific advanced
// titles, this file preserves the EXACT source register payload at RX
// time, not a fabricated original Delphi textual CSV.
// No command is sent to the instrument by these functions.
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

const sourceLiveValuesSchema="MVK_SOURCE_LIVE_VALUES_3100_EVENTS_V1"
const sourceLiveValuesAuditName="SOURCE_LIVE_VALUES_NATIVE_AUDIT.json"

type sourceLiveValuesEvent struct {
    FrameIndex uint64 `json:"frame_index"`
    TickIndex uint64 `json:"source_values_tick_index"`
    ReceivedUTC string `json:"received_utc"`
    Address string `json:"param_address"`
    Words uint16 `json:"register_words"`
    PayloadLEHex string `json:"param_payload_le_hex"`
    PayloadSHA256 string `json:"param_payload_sha256"`
    RawTickEvidence *sourceValuesRawTick `json:"source_ordered_raw_tick,omitempty"`
}
type sourceLiveValuesWindow struct {
    Window int `json:"window"`
    BeginOperatorSequence int `json:"begin_operator_sequence"`
    EndOperatorSequence int `json:"end_operator_sequence,omitempty"`
    BeginTick uint64 `json:"begin_source_values_tick"`
    EndTick uint64 `json:"end_source_values_tick"`
    StartBeforeFrame uint64 `json:"begin_before_frame"`
    EndAfterFrame uint64 `json:"end_after_frame"`
    Channels [10]bool `json:"channels"`
    Spec [43]bool `json:"spec"`
    Values [73]bool `json:"values"`
    Name string `json:"name"`
    Events uint64 `json:"events"`
    Bytes uint64 `json:"bytes"`
    SHA256 string `json:"sha256"`
    SourceRawLayoutName string `json:"source_raw_layout_name"`
    SourceRawLayoutRows uint64 `json:"source_raw_layout_rows"`
    SourceRawLayoutBytes uint64 `json:"source_raw_layout_bytes"`
    SourceRawLayoutSHA256 string `json:"source_raw_layout_sha256"`
    SourceTextCandidateName string `json:"source_text_candidate_name"`
    SourceTextCandidateRows uint64 `json:"source_text_candidate_rows"`
    SourceTextCandidateBytes uint64 `json:"source_text_candidate_bytes"`
    SourceTextCandidateSHA256 string `json:"source_text_candidate_sha256"`
    SourceRUProfileCandidateName string `json:"source_ru_profile_candidate_name"`
    SourceRUProfileCandidateRows uint64 `json:"source_ru_profile_candidate_rows"`
    SourceRUProfileCandidateBytes uint64 `json:"source_ru_profile_candidate_bytes"`
    SourceRUProfileCandidateSHA256 string `json:"source_ru_profile_candidate_sha256"`
    OriginalRUProfileCSVByteParityVerified bool `json:"original_ru_profile_csv_byte_parity_verified"`
    OriginalDelphiCSVParityVerified bool `json:"original_delphi_values_csv_byte_parity_verified"`
    layoutFile *os.File
    layoutDigest hash.Hash
    textFile *os.File
    textDigest hash.Hash
    ruProfileFile *os.File
    ruProfileDigest hash.Hash
    Outcome string `json:"outcome"`
    file *os.File
    digest hash.Hash
}
type sourceLiveValuesAudit struct {
    Schema string `json:"schema"`
    SessionID string `json:"session_id"`
    SourceRawSHA256 string `json:"source_raw_sha256"`
    EndReason string `json:"end_reason"`
    EndFrames uint64 `json:"end_frames_decoded"`
    EndTicks uint64 `json:"end_source_values_ticks_address_3100"`
    EndAUX uint64 `json:"end_aux4700_updates"`
    Windows []*sourceLiveValuesWindow `json:"windows"`
    OriginalDelphiGetValueTextParity bool `json:"original_delphi_get_value_text_parity_verified"`
    OriginalDelphiTimeParity bool `json:"original_win32_time_parity_verified"`
}
type sourceLiveValuesWriter struct {
    dir string
    active *sourceLiveValuesWindow
    windows []*sourceLiveValuesWindow
    nextMark int
    closed bool
    events uint64
}
func newSourceLiveValuesWriter(dir string)*sourceLiveValuesWriter{
    return &sourceLiveValuesWriter{dir:dir}
}
func(w *sourceLiveValuesWriter)applyFrameMarks(m *Monitor)error{
    if w==nil || w.closed || m.frameMarks==nil{return nil}
    for w.nextMark<len(m.frameMarks.records){
        mark:=m.frameMarks.records[w.nextMark]
        w.nextMark++
        if !mark.Applied{continue}
        switch mark.Event{
        case "values_begin":
            if w.active!=nil || len(w.windows)>=8{
                return errors.New("source live WriteValues duplicate begin/window overflow")
            }
            if !anySourceValuesSelected(mark) {
                return errors.New("source live WriteValues without selected source result")
            }
            n:=len(w.windows)+1
            name:=fmt.Sprintf("SOURCE_W%02d_VALUES_3100_RECEIVED.jsonl",n)
            f,e:=os.OpenFile(filepath.Join(w.dir,name),
                os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
            if e!=nil{return e}
            rawLayoutName:=fmt.Sprintf("SOURCE_W%02d_VALUES_3100_RAW_LAYOUT.csv",n)
            layout,e:=os.OpenFile(filepath.Join(w.dir,rawLayoutName),
                os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
            if e!=nil{
                _=f.Close()
                _=os.Remove(filepath.Join(w.dir,name))
                return e
            }
            textName:=fmt.Sprintf("SOURCE_W%02d_VALUES_3100_TEXT_CANDIDATE.csv",n)
            textFile,e:=os.OpenFile(filepath.Join(w.dir,textName),
                os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
            if e!=nil{
                _=layout.Close()
                _=f.Close()
                _=os.Remove(filepath.Join(w.dir,rawLayoutName))
                _=os.Remove(filepath.Join(w.dir,name))
                return e
            }
            profileName:=fmt.Sprintf("SOURCE_W%02d_VALUES_3100_RU_PROFILE_CANDIDATE.csv",n)
            profileHeader,e:=sourceRUValuesCandidateHeader(&sourceLiveValuesWindow{
                Channels:mark.Channels,Spec:mark.Spec,Values:mark.Values,
            })
            if e!=nil{
                _=textFile.Close();_=layout.Close();_=f.Close()
                _=os.Remove(filepath.Join(w.dir,textName))
                _=os.Remove(filepath.Join(w.dir,rawLayoutName))
                _=os.Remove(filepath.Join(w.dir,name))
                return e
            }
            ruProfile,e:=os.OpenFile(filepath.Join(w.dir,profileName),
                os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
            if e!=nil{
                _=textFile.Close();_=layout.Close();_=f.Close()
                _=os.Remove(filepath.Join(w.dir,textName))
                _=os.Remove(filepath.Join(w.dir,rawLayoutName))
                _=os.Remove(filepath.Join(w.dir,name))
                return e
            }
            headerWritten,e:=ruProfile.Write(profileHeader)
            if e!=nil || headerWritten!=len(profileHeader){
                _=ruProfile.Close()
                _=textFile.Close();_=layout.Close();_=f.Close()
                _=os.Remove(filepath.Join(w.dir,profileName))
                _=os.Remove(filepath.Join(w.dir,textName))
                _=os.Remove(filepath.Join(w.dir,rawLayoutName))
                _=os.Remove(filepath.Join(w.dir,name))
                return errors.New("source RU-profile candidate short original header write")
            }
            ruDigest:=sha256.New()
            _,_=ruDigest.Write(profileHeader)
            current:=&sourceLiveValuesWindow{
                Window:n,BeginOperatorSequence:mark.Sequence,
                BeginTick:m.summary.ValuesTicks,
                StartBeforeFrame:m.summary.TotalFrames,
                Channels:mark.Channels,Spec:mark.Spec,Values:mark.Values,
                Name:name,file:f,digest:sha256.New(),Outcome:"ACTIVE",
                SourceRawLayoutName:rawLayoutName,
                layoutFile:layout,layoutDigest:sha256.New(),
                SourceTextCandidateName:textName,
                textFile:textFile,textDigest:sha256.New(),
                SourceRUProfileCandidateName:profileName,
                SourceRUProfileCandidateBytes:uint64(len(profileHeader)),
                ruProfileFile:ruProfile,ruProfileDigest:ruDigest,
            }
            w.windows=append(w.windows,current)
            w.active=current
            m.filenames=append(m.filenames,name,rawLayoutName,textName,profileName)
            m.summary.Files[name]=name
            m.summary.Files[rawLayoutName]=rawLayoutName
            m.summary.Files[textName]=textName
            m.summary.Files[profileName]=profileName
        case "values_end":
            if w.active==nil{return errors.New("source live WriteValues end without begin")}
            w.active.EndOperatorSequence=mark.Sequence
            if e:=w.closeWindow(m,"CLOSED_BY_OPERATOR");e!=nil{return e}
        case "data_begin","data_end":
            // Independent original WriteData stage machine owns these.
        default:
            return errors.New("unrecognized source WriteValues action")
        }
    }
    return nil
}
func anySourceValuesSelected(m frameMarkReceipt)bool{
    adcSelected,tachSelected:=false,false
    for i,b:=range m.Channels{
        if i<8 && b{adcSelected=true}
        if i>=8 && b{tachSelected=true}
    }
    if adcSelected{
        for _,b:=range m.Spec{if b{return true}}
        for _,b:=range m.Values[:30]{if b{return true}}
    }
    if tachSelected{
        for _,b:=range m.Values[30:36]{if b{return true}}
    }
    // Never arm for historical non-original bits 36..72.
    return false
}
func(w *sourceLiveValuesWriter)onParam(m *Monitor,blocks []RegBlock,at time.Time,triggerImage *RegisterImage)error{
    if w==nil || w.closed || w.active==nil{return nil}
    triggerIndex:=-1
    for i:=range blocks{
        if blocks[i].Addr!=0x3100{continue}
        if triggerIndex>=0{return errors.New("source duplicate 0x3100 in PARAM")}
        triggerIndex=i
    }
    if triggerIndex<0{return nil}
    trigger:=&blocks[triggerIndex]
    if uint64(trigger.Words)*2!=uint64(len(trigger.Payload)) ||
       m.summary.ValuesTicks==0{
        return errors.New("source 0x3100 malformed writer payload/tick")
    }
    if triggerImage==nil{
        return errors.New("source 0x3100 missing trigger-prefix register image")
    }
    // Restrict both data and per-tick freshness to the inclusive prefix.
    // Suffix descriptors still update the main image for future frames.
    snapshot,rawLayout,e:=sourceValuesOrderedRawTickFromImage(
        triggerImage,w.active,blocks[:triggerIndex+1],at)
    if e!=nil{return e}
    textCandidate,e:=sourceValuesTextCandidateRow(snapshot)
    if e!=nil{return e}
    textDigest:=sha256.Sum256(textCandidate)
    snapshot.TextCandidateRowSHA256=hex.EncodeToString(textDigest[:])
    snapshot.TextCandidateFormatterVersion=sourceValuesTextCandidateFormatterVersion
    ruProfileCandidate,e:=sourceRUValuesCandidateRow(snapshot)
    if e!=nil{return e}
    profileRowDigest:=sha256.Sum256(ruProfileCandidate)
    snapshot.RUProfileCandidateRowSHA256=hex.EncodeToString(profileRowDigest[:])
    snapshot.RUProfileCandidateFormatterVersion=sourceValuesRUCSVProfileVersion
    digest:=sha256.Sum256(trigger.Payload)
    value:=sourceLiveValuesEvent{
        FrameIndex:m.summary.TotalFrames,TickIndex:m.summary.ValuesTicks-1,
        ReceivedUTC:at.UTC().Format(time.RFC3339Nano),
        Address:"0x3100",Words:trigger.Words,
        PayloadLEHex:hex.EncodeToString(trigger.Payload),
        PayloadSHA256:hex.EncodeToString(digest[:]),
        RawTickEvidence:&snapshot,
    }
    raw,e:=json.Marshal(value)
    if e!=nil{return e}
    raw=append(raw,'\n')
    n,e:=w.active.file.Write(raw)
    if e!=nil{return e}
    if n!=len(raw){return errors.New("source WriteValues short local record write")}
    _,_=w.active.digest.Write(raw)
    layoutWritten,e:=w.active.layoutFile.Write(rawLayout)
    if e!=nil{return e}
    if layoutWritten!=len(rawLayout){
        return errors.New("source WriteValues short RAW layout record write")
    }
    _,_=w.active.layoutDigest.Write(rawLayout)
    textWritten,e:=w.active.textFile.Write(textCandidate)
    if e!=nil{return e}
    if textWritten!=len(textCandidate){
        return errors.New("source WriteValues short text-candidate record write")
    }
    _,_=w.active.textDigest.Write(textCandidate)
    profileWritten,e:=w.active.ruProfileFile.Write(ruProfileCandidate)
    if e!=nil{return e}
    if profileWritten!=len(ruProfileCandidate){
        return errors.New("source RU-profile candidate short streaming record write")
    }
    _,_=w.active.ruProfileDigest.Write(ruProfileCandidate)
    w.active.SourceRUProfileCandidateRows++
    w.active.SourceRUProfileCandidateBytes+=uint64(profileWritten)
    w.active.SourceTextCandidateRows++
    w.active.SourceTextCandidateBytes+=uint64(textWritten)
    w.active.SourceRawLayoutRows++
    w.active.SourceRawLayoutBytes+=uint64(layoutWritten)
    w.active.Bytes+=uint64(n)
    w.active.Events++
    w.events++
    return nil
}
func(w *sourceLiveValuesWriter)closeWindow(m *Monitor,outcome string)error{
    if w.active==nil{return nil}
    current:=w.active
    current.EndAfterFrame=m.summary.TotalFrames
    current.EndTick=m.summary.ValuesTicks
    current.Outcome=outcome
    if current.file!=nil{
        if e:=current.file.Close();e!=nil{return e}
        current.file=nil
    }
    if current.layoutFile!=nil{
        if e:=current.layoutFile.Close();e!=nil{return e}
        current.layoutFile=nil
    }
    if current.textFile!=nil{
        if e:=current.textFile.Close();e!=nil{return e}
        current.textFile=nil
    }
    if current.ruProfileFile!=nil{
        if e:=current.ruProfileFile.Close();e!=nil{return e}
        current.ruProfileFile=nil
    }
    current.SourceRUProfileCandidateSHA256=hex.EncodeToString(
        current.ruProfileDigest.Sum(nil))
    current.SourceTextCandidateSHA256=hex.EncodeToString(
        current.textDigest.Sum(nil))
    current.SourceRawLayoutSHA256=hex.EncodeToString(
        current.layoutDigest.Sum(nil))
    current.SHA256=hex.EncodeToString(current.digest.Sum(nil))
    w.active=nil
    return nil
}
func(w *sourceLiveValuesWriter)finalize(m *Monitor)error{
    if w==nil||w.closed{return nil}
    w.closed=true
    clean:=(m.summary.EndReason=="STOPPED_BY_USER" ||
        m.summary.EndReason=="DURATION_REACHED" ||
        m.summary.EndReason=="SIZE_LIMIT_REACHED") &&
        !m.captureOnly && !m.summary.SourceTCPMultiSocket
    if w.active!=nil{
        outcome:="INTERRUPTED"
        if clean{outcome="CLOSED_BY_SOURCE_THREAD"}
        if e:=w.closeWindow(m,outcome);e!=nil{return e}
    }
    if len(w.windows)==0{return nil}
    doc:=sourceLiveValuesAudit{
        Schema:sourceLiveValuesSchema,
        SessionID:filepath.Base(m.dir),SourceRawSHA256:m.summary.RawSHA256,
        EndReason:m.summary.EndReason,EndFrames:m.summary.TotalFrames,
        EndTicks:m.summary.ValuesTicks,EndAUX:m.summary.Aux4700,
        Windows:w.windows,OriginalDelphiGetValueTextParity:false,
        OriginalDelphiTimeParity:false,
    }
    encoded,e:=json.MarshalIndent(doc,"","  ")
    if e!=nil{return e}
    encoded=append(encoded,'\n')
    if e=os.WriteFile(filepath.Join(w.dir,sourceLiveValuesAuditName),
        encoded,0600);e!=nil{return e}
    digest:=sha256.Sum256(encoded)
    m.summary.SourceLiveValuesAuditSHA256=hex.EncodeToString(digest[:])
    m.summary.SourceLiveValuesWindows=uint64(len(w.windows))
    m.summary.SourceLiveValuesEventRecords=w.events
    m.filenames=append(m.filenames,sourceLiveValuesAuditName)
    m.summary.Files[sourceLiveValuesAuditName]=sourceLiveValuesAuditName
    return nil
}
func(w *sourceLiveValuesWriter)cleanup(){
    if w==nil{return}
    for _,win:=range w.windows {
        if win.file!=nil{_ = win.file.Close();win.file=nil}
        if win.layoutFile!=nil{_ = win.layoutFile.Close();win.layoutFile=nil}
        if win.textFile!=nil{_ = win.textFile.Close();win.textFile=nil}
        if win.ruProfileFile!=nil{_ = win.ruProfileFile.Close();win.ruProfileFile=nil}
    }
}
