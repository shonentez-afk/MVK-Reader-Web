package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceRawTestWords(v uint32) []byte {
    b:=make([]byte,4)
    binary.LittleEndian.PutUint32(b,v)
    return b
}

func sourceSelectedMark(t *testing.T,c *frameMarkController,
    m *Monitor,sequence int,event string,
    ch [10]bool,spec [43]bool,values [73]bool,
) {
    t.Helper()
    req:=frameMarkRequest{
        Schema:frameMarkRequestSchema,
        Sequence:sequence,SessionID:filepath.Base(m.dir),
        Event:event,RequestedUTC:"2026-11-19T16:24:00Z",
        Channels:append([]bool(nil),ch[:]...),
        Spec:append([]bool(nil),spec[:]...),
        Values:append([]bool(nil),values[:]...),
    }
    body,e:=json.Marshal(req);if e!=nil{t.Fatal(e)}
    filename:=filepath.Join(c.inbox,fmtSeq(sequence))
    if e=os.WriteFile(filename,body,0600);e!=nil{t.Fatal(e)}
}

func TestOriginalWriteValuesSourceTickThreeGroupOrderAndTachFreshness(t *testing.T){
    m,marks:=markFixture(t)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    var channels [10]bool
    var spec [43]bool
    var values [73]bool
    channels[0]=true;channels[8]=true
    spec[0]=true
    values[0]=true;values[6]=true
    values[30]=true;values[35]=true
    sourceSelectedMark(t,marks,m,1,"values_begin",channels,spec,values)
    loc:=time.FixedZone("ORIGINAL_LOCAL",2*3600)
    at:=time.Date(2026,11,19,16,24,12,123000000,loc)
    seed:=makeParam([]RegBlock{
        {Addr:0x2060,Words:2,Payload:sourceRawTestWords(0x3fc00000)},
        {Addr:0x2120,Words:2,Payload:sourceRawTestWords(0x00000051)},
        {Addr:0x2002,Words:2,Payload:sourceRawTestWords(0x40200000)},
        {Addr:0x3000,Words:2,Payload:sourceRawTestWords(0x40d00000)},
        {Addr:0x30fe,Words:2,Payload:sourceRawTestWords(0x00000666)},
    })
    if e:=m.ProcessChunk(seed,at);e!=nil{t.Fatal(e)}
    if len(m.sourceLiveValuesWriter.windows)!=1 ||
        m.sourceLiveValuesWriter.windows[0].Events!=0 {
        t.Fatal("ordinary PARAM should arm selected list without 3100 row")
    }
    // Source 0x3100 arrives AFTER the latest valid RegisterImage words.
    tick:=makeParam([]RegBlock{{
        Addr:0x3100,Words:2,Payload:sourceRawTestWords(0xAABBCCDD),
    }})
    if e:=m.ProcessChunk(tick,at.Add(50*time.Millisecond));e!=nil{t.Fatal(e)}
    win:=m.sourceLiveValuesWriter.active
    if win==nil || win.Events!=1 || win.SourceRawLayoutRows!=1 {
        t.Fatalf("source 3100 row not written: %+v",win)
    }
    sourceSelectedMark(t,marks,m,2,"values_end",channels,spec,values)
    if e:=m.ProcessChunk(
        syntheticFrame(0,0,0.25).Raw,at.Add(100*time.Millisecond));e!=nil{
        t.Fatal(e)
    }
    report,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    if report.SourceLiveValuesWindows!=1||
        report.SourceLiveValuesEventRecords!=1 ||
        report.SourceLiveValuesAuditSHA256==""{
        t.Fatal("source 3100 raw-layout audit was not SHA-linked")
    }
    csvName:=filepath.Join(m.dir,"SOURCE_W01_VALUES_3100_RAW_LAYOUT.csv")
    text,e:=os.ReadFile(csvName);if e!=nil{t.Fatal(e)}
    expected:="16:24:12.173|RAW_F32_CANDIDATE:00002040"+
        "|RAW_U32_ADVANCED_UNFORMATTED:51000000"+
        "|RAW_F32_CANDIDATE:0000c03f|RAW_F32_CANDIDATE:0000d040|UNKNOWN\r\n"
    if string(text)!=expected{
        t.Fatalf("original selected list order or source time wrong: %q",text)
    }
    file,e:=os.ReadFile(filepath.Join(m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
    if e!=nil{t.Fatal(e)}
    var event sourceLiveValuesEvent
    if e=json.Unmarshal(bytes.TrimSpace(file),&event);e!=nil{t.Fatal(e)}
    ev:=event.RawTickEvidence
    if ev==nil || ev.Schema!=sourceValuesRawLayoutSchema ||
       ev.LocalTime!="16:24:12.173" ||
       len(ev.OrderedFields)!=5 || ev.ValidDWORDs!=4 ||
       ev.UnknownSelected!=1 || ev.OriginalGetValueTextParityVerified ||
       ev.OriginalCSVByteParityVerified || ev.OriginalLocalTimeParityVerified{
        t.Fatalf("false or lost original GetValueText evidence: %+v",ev)
    }
    if ev.OrderedFields[0].Group!="SPEC" || ev.OrderedFields[0].WordAddr==nil ||
       ev.OrderedFields[0].RawLE==nil || ev.OrderedFields[1].Group!="RESULT" ||
       ev.OrderedFields[2].Group!="BAND" ||
       ev.OrderedFields[3].Channel!=9 ||
       ev.OrderedFields[4].CellIndex!=5 ||
       ev.OrderedFields[4].RawLE!=nil {
        t.Fatalf("wrong source mask/group/address map: %+v",ev.OrderedFields)
    }
    candidateName:=filepath.Join(m.dir,"SOURCE_W01_VALUES_3100_TEXT_CANDIDATE.csv")
    candidate,e:=os.ReadFile(candidateName);if e!=nil{t.Fatal(e)}
    wantCandidate:="16:24:12.173|2.5|UNRESOLVED_ADVANCED_ID_1|1.5|6.5|UNKNOWN\r\n"
    if string(candidate)!=wantCandidate{
        t.Fatalf("source text candidate violates original order: %q",candidate)
    }
    candidateSum:=sha256.Sum256(candidate)
    if ev.TextCandidateRowSHA256!=hex.EncodeToString(candidateSum[:]) ||
       win.SourceTextCandidateSHA256!=hex.EncodeToString(candidateSum[:]) ||
       win.SourceTextCandidateRows!=1 ||
       win.SourceTextCandidateBytes!=uint64(len(candidate)) ||
       ev.OrderedFields[1].SourceCellType!=10 ||
       ev.OrderedFields[1].AdvancedSelectedID==nil ||
       *ev.OrderedFields[1].AdvancedSelectedID!=1 ||
       ev.TextCandidateFormatterVersion!=sourceValuesTextCandidateFormatterVersion{
        t.Fatalf("source candidate evidence/bit extraction incorrect: %+v",ev)
    }
    sum:=sha256.Sum256(text)
    if ev.RawRowSHA256!=hex.EncodeToString(sum[:]) ||
       win.SourceRawLayoutSHA256!=hex.EncodeToString(sum[:]) ||
       win.SourceRawLayoutBytes!=uint64(len(text)) ||
       win.SourceRawLayoutRows!=1{
        t.Fatal("source raw row SHA or full window count does not match file bytes")
    }
}

func TestOriginalWriteValuesStaleTachPulseOnlyFromCurrentParam(t *testing.T){
    m,_:=markFixture(t)
    // The test reads the register image without calling Finalize.
    // Close opened aux4700.jsonl, incoming.raw and event handles BEFORE
    // Windows t.TempDir RemoveAll (otherwise the EXE packaging job fails).
    t.Cleanup(func(){ if e:=m.CloseFiles();e!=nil{t.Errorf("close source test files: %v",e)} })
    var channels [10]bool;channels[8]=true
    var values [73]bool;values[35]=true
    w:=&sourceLiveValuesWindow{
        Channels:channels,Values:values,
    }
    at:=time.Date(2026,11,19,16,24,0,0,time.UTC)
    original:=sourceRawTestWords(0x55551234)
    m.image.Put(RegBlock{Addr:0x30fe,Words:2,Payload:original})
    old,raw,e:=m.sourceValuesOrderedRawTick(w,nil,at)
    if e!=nil{t.Fatal(e)}
    if old.UnknownSelected!=1 || old.ValidDWORDs!=0 ||
       old.OrderedFields[0].RawLE!=nil ||
       string(raw)!="16:24:00.000|UNKNOWN\r\n"{
        t.Fatalf("stale TACH +FE incorrectly interpreted as current: %+v",old)
    }
    fresh,raw,e:=m.sourceValuesOrderedRawTick(
        w,[]RegBlock{{Addr:0x30fe,Words:2,Payload:original}},at)
    if e!=nil{t.Fatal(e)}
    if fresh.ValidDWORDs!=1 || fresh.UnknownSelected!=0 ||
       fresh.OrderedFields[0].RawLE==nil ||
       string(raw)!="16:24:00.000|RAW_U32_CANDIDATE:34125555\r\n" {
        t.Fatalf("real current TACH impulse dropped: %+v",fresh)
    }
}

func TestOriginalWriteValuesFreezeDoesNotCreateRawTextRow(t *testing.T){
    m,c:=markFixture(t)
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    var channels [10]bool;channels[0]=true
    var values [73]bool;values[0]=true
    var spec [43]bool
    sourceSelectedMark(t,c,m,1,"values_begin",channels,spec,values)
    at:=time.Date(2026,11,19,16,24,0,0,time.UTC)
    m.sourceOriginalRXGate.frozen=true
    tick:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
        Payload:sourceRawTestWords(0x11111111)}})
    if e:=m.ProcessChunk(tick,at);e!=nil{t.Fatal(e)}
    if len(m.sourceLiveValuesWriter.windows)!=1 ||
       m.sourceLiveValuesWriter.windows[0].SourceRawLayoutRows!=0 ||
       m.summary.SourceFrozenValuesTicks!=1 {
       t.Fatal("FreezeUpdate must skip source original 3100 WriteValues")
    }
    m.sourceOriginalRXGate.frozen=false
    if e:=m.ProcessChunk(tick,at.Add(time.Second));e!=nil{t.Fatal(e)}
    if m.sourceLiveValuesWriter.windows[0].SourceRawLayoutRows!=1{
        t.Fatal("unfreeze must admit the next genuine trigger, not cached row")
    }
    if _,_,e:=m.Finalize("STOPPED_BY_USER");e!=nil{t.Fatal(e)}
    text,e:=os.ReadFile(filepath.Join(m.dir,
        "SOURCE_W01_VALUES_3100_RAW_LAYOUT.csv"));if e!=nil{t.Fatal(e)}
    if !bytes.Equal(text,[]byte("16:24:01.000|UNKNOWN\r\n")){
        t.Fatalf("source frozen tick leaked: %q",text)
    }
}
