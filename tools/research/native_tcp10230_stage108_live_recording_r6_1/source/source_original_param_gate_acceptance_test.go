package main

// One real source receive/Stop acceptance over synthetic frames:
// an empty PARAM does not abort a recording or advance Task2 Stage0;
// Freeze drains PARAM, AUX and 0x3100 without updating Delphi registers;
// immutable RAW, calibrated ring, source Values and SHA journal stay aligned.
// No industrial socket and no device control/SetRate.
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

func TestOriginalMode2EmptyPARAMAndFrozenRegisterGateToStop(t *testing.T) {
    m,marks:=markFixture(t)
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalTask2Stage.onConnected(0)
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    journal,e:=newSourceOriginalParamGateJournal(m.dir)
    if e!=nil{t.Fatal(e)}
    m.sourceParamGate=journal
    raw:=make([]byte,0,20000)
    now:=time.Date(2026,11,18,13,30,0,0,time.UTC)
    push:=func(frame []byte) {
        t.Helper()
        raw=append(raw,frame...)
        if e:=m.ProcessChunk(frame,now);e!=nil{t.Fatal(e)}
        now=now.Add(10*time.Millisecond)
    }

    empty:=makeParam(nil)
    if len(empty)!=28{t.Fatal("source zero-record PARAM header must be 28 bytes")}
    push(empty)
    if m.summary.InvalidFrames!=0 || m.captureOnly ||
        m.summary.SourceEmptyParamFrames!=1 ||
        m.sourceOriginalTask2Stage.stage!=0 ||
        m.summary.RegisterUpdates!=0 {
        t.Fatal("empty source PARAM corrupted receive Stage0")
    }

    status0:=task2Status0Param(0).Raw
    push(status0)
    if m.sourceOriginalTask2Stage.stage!=1{t.Fatal("source nonempty PARAM Stage1")}
    status,e:=m.image.Uint32(0x1006)
    if e!=nil || status!=0{t.Fatal("baseline observed healthy Status0 missing")}

    queueMark(t,marks,1,"values_begin")
    m.sourceOriginalRXGate.setFreeze(true)
    push(task2Status0Param(42).Raw)
    push(makeAux())
    values:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
        Payload:[]byte{0xDE,0xAD,0xBE,0xEF}}})
    push(values)
    push(sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000))
    status,e=m.image.Uint32(0x1006)
    if e!=nil || status!=0 ||
        m.sourceOriginalTask2Stage.stage!=1 ||
        m.sourceOriginalTask2Stage.systemErrorLatched ||
        m.summary.ValuesTicks!=0 || m.summary.Aux4700!=0 ||
        m.summary.RegisterUpdates!=1 ||
        m.sourceLiveValuesWriter.events!=0 ||
        m.sourceOriginalStorage.receipt().Channels[0].RxPos!=0 {
        t.Fatalf("FreezeUpdate applied source PARAM/ADC/VALUES: status=%d, err=%v, summary=%+v",
            status,e,m.summary)
    }
    m.sourceOriginalRXGate.setFreeze(false)
    push(task2Status0Param(0).Raw)
    push(makeAux())
    accepted:=makeParam([]RegBlock{{Addr:0x3100,Words:2,
        Payload:[]byte{0x9A,0xBC,0xCD,0xEF}}})
    push(accepted)
    push(sourceLiveWriterSample(typeADC,0,65536,1,0x40000000))
    push(sourceLiveWriterSample(typeTach,8,65536,0,0x01020304,0x05060708))
    queueMark(t,marks,2,"values_end")
    push(makeIdentity())
    m.sourceOriginalTask2Stage.onDisconnected("STOPPED_BY_USER")
    summary,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    complete,e:=os.ReadFile(filepath.Join(m.dir,"incoming.raw"))
    if e!=nil || !bytes.Equal(complete,raw){t.Fatalf("RAW freeze preservation failed: %v",e)}
    checksum:=sha256.Sum256(raw)
    if summary.RawSHA256!=hex.EncodeToString(checksum[:]) {
        t.Fatal("source Freeze changed RAW digest")
    }
    if summary.SourceEmptyParamFrames!=1 ||
        summary.SourceFrozenParamFrames!=3 ||
        summary.SourceFrozenParamBlocks!=10 ||
        summary.SourceFrozenAux4700!=1 ||
        summary.SourceFrozenValuesTicks!=1 ||
        summary.SourceNonemptyParameters!=7 ||
        summary.RegisterUpdates!=4 || summary.Aux4700!=1 ||
        summary.ValuesTicks!=1 ||
        summary.SourceLiveValuesEventRecords!=1 ||
        summary.FrameMarkCount!=2 ||
        summary.ReadOnly!=true || summary.CaptureOnly ||
        summary.InvalidFrames!=0 || summary.TailBytes!=0 {
        t.Fatalf("original source PARAM lifetime mismatch: %+v",summary)
    }
    if m.sourceOriginalStorage.receipt().Channels[0].RxPos!=1 ||
       m.sourceOriginalStorage.receipt().Channels[8].RxPos!=8 ||
       m.sourceOriginalRXGate.receipt().Channels[0].FrozenSkippedElements!=1 {
        t.Fatal("source actual Float32 / Byte ring did not honor Freeze")
    }
    proof:=m.sourceOriginalTask2Stage.receipt()
    if proof.Stage!=0 || proof.LastLiveStage!=1 || !proof.Disconnected {
        t.Fatalf("original Task2 Stop state mismatch: %+v",proof)
    }
    journalBytes,e:=os.ReadFile(filepath.Join(m.dir,sourceOriginalParamGateName))
    if e!=nil{t.Fatal(e)}
    journalSum:=sha256.Sum256(journalBytes)
    if summary.SourceOriginalParamGateSHA256!=hex.EncodeToString(journalSum[:]) ||
       summary.SourceOriginalParamGateRecords!=8 {
        t.Fatal("source PARAM SHA ledger incomplete or unmatched")
    }
    for _,line:=range bytes.Split(bytes.TrimSpace(journalBytes),[]byte{10}){
        var row sourceOriginalParamGateRecord
        if e:=json.Unmarshal(line,&row);e!=nil{t.Fatal(e)}
        if row.Schema!=sourceOriginalParamGateSchema || row.FrameIndex==0 {
            t.Fatal("source PARAM ledger fields missing")
        }
    }
    valuesBytes,e:=os.ReadFile(filepath.Join(m.dir,
        "SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
    if e!=nil{t.Fatal(e)}
    var row sourceLiveValuesEvent
    if e=json.Unmarshal(bytes.TrimSpace(valuesBytes),&row);e!=nil{t.Fatal(e)}
    if row.TickIndex!=0 || row.PayloadLEHex!="9abccdef" ||
       row.FrameIndex==0 {
        t.Fatal("original frozen 0x3100 was incorrectly written")
    }
}

func TestOriginalMode2ZeroRecordPARAMNoSyntheticStageOrValue(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"source_empty_param"),"LIVE_READ_ONLY","192.0.2.84")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalTask2Stage.onConnected(0)
    raw:=makeParam(nil)
    for i:=0;i<len(raw);i++{
        if e:=m.ProcessChunk(raw[i:i+1],time.Now());e!=nil{t.Fatal(e)}
    }
    if m.sourceOriginalTask2Stage.stage!=0 ||
       m.summary.SourceNonemptyParameters!=0 ||
       m.summary.SourceEmptyParamFrames!=1 ||
       m.summary.RegisterUpdates!=0 || m.summary.InvalidFrames!=0 {
        t.Fatal("fragmented empty PARAM incorrectly advanced Task2")
    }
    m.sourceOriginalTask2Stage.onDisconnected("STOPPED_BY_USER")
    result,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    if result.CaptureOnly || result.TotalFrames!=1 ||
       result.RawBytes!=uint64(len(raw)) || result.ValuesTicks!=0 {
        t.Fatal("valid empty PARAM incorrectly marked malformed")
    }
}
