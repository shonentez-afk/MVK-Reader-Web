package main

import (
    "bytes"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSourceTachLatchCoreFixture(t *testing.T){
    root:=os.Getenv("MVK_TACH_LATCH_FIXTURE_DIR")
    if root=="" {root=t.TempDir()}
    run:=filepath.Join(root,"TEST_2026-11-24_09-45-00.000")
    m,e:=NewMonitor(run,"OFFLINE_REPLAY","192.0.2.84")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    marks,e:=newFrameMarkController(root,run);if e!=nil{t.Fatal(e)}
    m.frameMarks=marks
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(run)
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceParamGate,e=newSourceOriginalParamGateJournal(run);if e!=nil{t.Fatal(e)}
    m.sourceTachGate,e=newSourceTachGateJournal(run);if e!=nil{t.Fatal(e)}
    m.sourceContract=newSourceMetadataLatchCandidate()
    m.sourceContract.newSocket()
    now:=time.Date(2026,11,24,9,45,0,0,time.UTC)
    wire:=make([]byte,0)
    push:=func(frame []byte){
        t.Helper()
        wire=append(wire,frame...)
        if e:=m.ProcessChunk(frame,now);e!=nil{t.Fatal(e)}
        if m.captureOnly{t.Fatal("unexpected capture-only")}
        now=now.Add(time.Second)
    }
    trig:=prefixTestBlock(0x3100,0)
    config:=RegBlock{Addr:0x10e,Words:4,Payload:append(sourceRawTestWords(0x40800000),[]byte{'m','/','s',0}...)}
    push(makeParam([]RegBlock{config,prefixTestBlock(0x10e,0x41100000)}))
    if row:=m.sourceContract.channel[0];row.Range!=4 || row.Units!="m/s" || !row.RangeCurrentSocket{
        t.Fatalf("first descriptor metadata %+v",row)
    }
    if raw,e:=m.image.Float32(0x10e);e!=nil || raw!=9{t.Fatal("forensic image changed",raw,e)}
    push(sourceLiveWriterSample(typeTach,8,65536,0,0x01010101))
    // No open writer: trigger still clears both source latches.
    push(makeParam([]RegBlock{trig}))
    for i,a:=range impulseAddresses{
        if v:=m.sourceContract.dword(a);v!=(sourceImpulseValue{0,true}){t.Fatal("unarmed reset",i,v)}
    }
    var channels [10]bool;channels[8]=true;channels[9]=true
    var spec [43]bool
    var values [73]bool;values[35]=true
    sourceSelectedMark(t,marks,m,1,"values_begin",channels,spec,values)
    push(sourceLiveWriterSample(typeTach,8,65536,1,0x02020202))
    m.sourceOriginalRXGate.setFreeze(true)
    push(sourceLiveWriterSample(typeTach,9,65536,0,0x03030303))
    push(makeParam([]RegBlock{trig}))
    m.sourceOriginalRXGate.setFreeze(false)
    push(sourceLiveWriterSample(typeTach,9,32768,1,0x03030303))
    // Row sees [1,0]; the suffix is next row's state, not this one.
    push(makeParam([]RegBlock{trig,prefixTestBlock(0x30fe,42)}))
    push(makeParam([]RegBlock{trig}))
    push(sourceLiveWriterSample(typeTach,8,65536,2,0x02020202))
    push(sourceLiveWriterSample(typeTach,9,65536,2,0x04040404))
    push(makeParam([]RegBlock{trig}))
    report,_,e:=m.Finalize("STOPPED_BY_USER");if e!=nil{t.Fatal(e)}
    if report.CaptureOnly || report.ValuesTicks!=4 || report.SourceLiveValuesEventRecords!=3 ||
        report.SourceFrozenValuesTicks!=1 || report.SourceTachGateRecords!=6 ||
        report.SourceTachGateSchema!=sourceTachGateSchema {
        t.Fatalf("unexpected final source evidence %+v",report)
    }
    raw:=prefixTestRead(t,run,"incoming.raw")
    ledger:=prefixTestRead(t,run,sourceTachGateName)
    if !bytes.Equal(raw,wire) || report.RawSHA256!=prefixTestSHA(wire) ||
        len(ledger)!=6*sourceTachGateRecordSize || report.SourceTachGateSHA256!=prefixTestSHA(ledger){
        t.Fatal("RAW/ledger provenance mismatch")
    }
    lines:=bytes.Split(bytes.TrimSpace(prefixTestRead(t,run,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl")),[]byte{'\n'})
    want:=[][2]string{{"01000000","00000000"},{"2a000000","00000000"},{"00000000","01000000"}}
    if len(lines)!=len(want){t.Fatal("wrong event count")}
    for i,line:=range lines{
        var event sourceLiveValuesEvent
        if e:=json.Unmarshal(line,&event);e!=nil{t.Fatal(e)}
        tick:=event.RawTickEvidence
        if tick==nil || tick.Schema!=sourceValuesLatchLayoutSchema || len(tick.OrderedFields)!=2{t.Fatal("missing V2 source tick")}
        for j,field:=range tick.OrderedFields{
            if field.RawLE==nil || *field.RawLE!=want[i][j] || field.Channel!=9+j || field.CellIndex!=5{
                t.Fatalf("row %d field %d %+v",i,j,field)
            }
        }
    }
    for _,addr:=range impulseAddresses{
        if v:=m.sourceContract.dword(addr);v!=(sourceImpulseValue{0,true}){t.Fatal("armed reset",v)}
    }
    if raw,e:=m.image.Uint32(0x30fe);e!=nil || raw!=42{t.Fatal("derived latch overwrote raw register",raw,e)}
    if report.SourceMetadataObservation==nil || report.SourceMetadataObservation.NumericScalingApplied ||
        report.SourceMetadataObservation.ADC[0].RangeFactor==nil ||
        *report.SourceMetadataObservation.ADC[0].RangeFactor!=4 {t.Fatal("metadata observation falsely applied")}
}

func TestSourceMetadataSocketBoundaryRetainsPreviousByte(t *testing.T){
    s:=newSourceMetadataLatchCandidate()
    s.newSocket()
    if _,e:=s.param(0x10e,sourceRawTestWords(0x40000000),false);e!=nil{t.Fatal(e)}
    if e:=s.tach(0,[]byte{7,7},true);e!=nil{t.Fatal(e)}
    s.newSocket()
    if s.channel[0].Range!=2 || s.channel[0].RangeCurrentSocket || s.last[0]!=7 {t.Fatal("epoch retained false freshness or reset last")}
    if _,e:=s.param(0x3100,sourceRawTestWords(0),false);e!=nil{t.Fatal(e)}
    if e:=s.tach(0,[]byte{7},true);e!=nil{t.Fatal(e)}
    if s.dword(0x30fe)!=(sourceImpulseValue{0,true}){t.Fatal("reconnect invented impulse")}
}
