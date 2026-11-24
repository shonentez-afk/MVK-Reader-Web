package main

import (
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func exerciseSourceLocalTach(t *testing.T,m *Monitor,c *frameMarkController){
    t.Helper()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    j,err:=newSourceOriginalParamGateJournal(m.dir)
    if err!=nil{t.Fatal(err)}
    m.sourceParamGate=j
    var channels [10]bool
    channels[8]=true;channels[9]=true
    var spec [43]bool
    var vals [73]bool;vals[35]=true
    sourceSelectedMark(t,c,m,1,"values_begin",channels,spec,vals)
    now:=time.Date(2026,11,24,5,0,0,0,time.UTC)
    push:=func(b []byte){
        t.Helper()
        if e:=m.ProcessChunk(b,now);e!=nil{t.Fatal(e)}
        if m.captureOnly{t.Fatal("unexpected parser failure")}
        now=now.Add(time.Millisecond)
    }
    check:=func(ch int,want string,mask uint8){
        t.Helper()
        row:=m.snapshotSourceLivePageStatusBanks().TACH[ch]
        if row.LocalTachWordMask!=mask || row.Fields[5]==nil || *row.Fields[5]!=want {
            t.Fatalf("TACH%d %+v want %s mask %d",ch+1,row,want,mask)
        }
    }
    push(makeParam([]RegBlock{prefixTestBlock(0x30fe,0x11223344),
        prefixTestBlock(0x31fe,0x55667788)}))
    // Each BYTE is compared to prior last, not interpreted as Float32.
    push(sourceLiveWriterSample(typeTach,8,65536,0,0x01010101))
    push(sourceLiveWriterSample(typeTach,9,65536,0,0x02000202))
    check(0,"01000000",3);check(1,"01000000",3)
    if wire:=m.sourceLiveRawDWORD(0x30fe);wire==nil||*wire!="44332211"{
        t.Fatal("local TACH mutated wire register image")
    }
    trigger:=makeParam([]RegBlock{prefixTestBlock(0x3100,0x12345678)})
    push(trigger)
    check(0,"00000000",3);check(1,"00000000",3)
    // Identical final byte, no new pulse. Freeze/wrong Fs must not set it.
    push(sourceLiveWriterSample(typeTach,8,65536,1,0x01010101))
    m.sourceOriginalRXGate.setFreeze(true)
    push(sourceLiveWriterSample(typeTach,9,65536,1,0x03030303))
    push(trigger)
    check(1,"00000000",3)
    m.sourceOriginalRXGate.setFreeze(false)
    push(sourceLiveWriterSample(typeTach,9,8192,2,0x04040404))
    push(sourceLiveWriterSample(typeTach,9,65536,3,0x02020202))
    check(0,"00000000",3);check(1,"00000000",3)
    push(trigger)
    sourceSelectedMark(t,c,m,2,"values_end",channels,spec,vals)
    // No writer after this frame: trigger must still clear both DWORDs.
    push(sourceLiveWriterSample(typeTach,8,65536,2,0x05050505))
    check(0,"01000000",3)
    push(trigger)
    check(0,"00000000",3)
    if m.sourceTach.state.last[0]!=5{t.Fatal("tick reset erased last byte")}
    summary,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    if summary.SourceLiveValuesEventRecords!=2 || summary.ValuesTicks!=3 ||
       summary.SourceLocalTachGateRecords!=7 ||
       len(summary.SourceLocalTachGateSHA256)!=64 {
        t.Fatalf("TACH timeline counters %+v",summary)
    }
    raw:=prefixTestRead(t,m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl")
    var rows []sourceLiveValuesEvent
    for _,line:=range splitSourceTachTestLines(raw){
        var event sourceLiveValuesEvent
        if e=json.Unmarshal(line,&event);e!=nil{t.Fatal(e)}
        rows=append(rows,event)
    }
    if len(rows)!=2{t.Fatal("TACH rows")}
    for i,event:=range rows{
        want:="01000000";if i==1{want="00000000"}
        cells:=event.RawTickEvidence.OrderedFields
        if len(cells)!=2{t.Fatal("TACH selected cells")}
        for _,cell:=range cells{
            if cell.RawLE==nil||*cell.RawLE!=want{t.Fatalf("pre-reset TACH mismatch %+v",cell)}
        }
    }
}
func splitSourceTachTestLines(data []byte)[][]byte{
    var rows [][]byte
    start:=0
    for i,b:=range data{if b==10{if i>start{rows=append(rows,data[start:i])};start=i+1}}
    return rows
}
func TestSourceLocalTachLatchReceiveToValuesAndStatus(t *testing.T){
    m,c:=markFixture(t);defer m.CloseFiles()
    exerciseSourceLocalTach(t,m,c)
}
func TestSourceLocalTachCoreFixture(t *testing.T){
    root:=os.Getenv("MVK_PREFIX_FIXTURE_DIR")
    if root==""{t.Skip("cross-language fixture not requested")}
    root=filepath.Join(root,"tach")
    if e:=os.MkdirAll(root,0700);e!=nil{t.Fatal(e)}
    run:=filepath.Join(root,"TEST_2026-11-24_05-00-00.000")
    m,e:=NewMonitor(run,"OFFLINE_REPLAY","192.0.2.84");if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    c,e:=newFrameMarkController(root,run);if e!=nil{t.Fatal(e)}
    m.frameMarks=c
    exerciseSourceLocalTach(t,m,c)
}
func TestSourceLocalTachProjectionPartialWireOverwrite(t *testing.T){
    var s sourceLocalTachState
    var image RegisterImage
    s.observe(0,[]byte{1,0,1,3})
    s.resetTick()
    s.observe(0,[]byte{3,3})
    if s.value[0]!=0{t.Fatal("unchanged byte set pulse")}
    b:=prefixTestBlock(0x30ff,0x12345678)
    image.Put(b);s.onBlock(b)
    if s.mask[0]!=1 {t.Fatal("partial overwrite failed")}
    got:=s.projected(&image,0)
    if got==nil||*got!="00007856"{t.Fatalf("wrong projected word %v",got)}
    s.observe(0,[]byte{3,1})
    got=s.projected(&image,0)
    if got==nil||*got!="01000000"{t.Fatal("local edge did not overwrite DWORD")}
}
