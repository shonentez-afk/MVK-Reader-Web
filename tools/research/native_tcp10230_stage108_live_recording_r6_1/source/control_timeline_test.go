package main

import (
    "encoding/json"
    "math"
    "os"
    "path/filepath"
    "testing"
)

func controlFixtureFrame(adc int, status uint32, corrupted bool) Frame {
    b:=make([]byte,64*2) // all 8 control slots, 8 register words each
    leFloat(b,0,13.5)
    le32(b,4,status)
    leFloat(b,8,1.25)
    le32(b,12,0xBADC0FFE)
    if corrupted {le32(b,0,math.Float32bits(float32(math.NaN())))}
    return syntheticParam(160,[]RegBlock{{
        Addr:uint16(0x2000+adc*0x200+0x130),Words:64,Payload:b,
    }})
}

func originalTimelineFromFrames(t *testing.T, frames []Frame) []map[string]json.RawMessage {
    t.Helper()
    raw,csv,sum:=writeFixture(t,frames)
    dest:=filepath.Join(t.TempDir(),"out")
    report,err:=export(raw,csv,sum,dest,0)
    if err!=nil {t.Fatal(err)}
    if len(report.GeneratedFiles)!=19 {t.Fatalf("changed original 19-file contract: %d",len(report.GeneratedFiles))}
    data,err:=os.ReadFile(filepath.Join(dest,"TIMELINE.json"))
    if err!=nil {t.Fatal(err)}
    var rows []map[string]json.RawMessage
    if err:=json.Unmarshal(data,&rows);err!=nil {t.Fatal(err)}
    return rows
}

func decodedControl(t *testing.T, row map[string]json.RawMessage) ControlTickAudit {
    t.Helper()
    payload,ok:=row["control_status"]
    if !ok {t.Fatal("missing optional control status provenance")}
    var c ControlTickAudit
    if err:=json.Unmarshal(payload,&c);err!=nil {t.Fatal(err)}
    if c.Schema!=controlTickSchema || c.Source!=controlTickSource ||
       c.ZoneAndAlertTextVerified || c.ConfigParameterSelectionVerified ||
       !c.NoInitialSnapshotAsLiveStatus {
       t.Fatalf("source flags inaccurate: %+v",c)
    }
    return c
}

func TestStage111Z28B2NoFreshAlarmFromInitialFullSnapshot(t *testing.T) {
    frames:=makeFixture()
    // Force a plausible, but potentially stale alarm word into the initial
    // full 0x4000-word snapshot. It must NEVER be exposed as live status.
    offset:=32+(0x2000+0x130)*2
    leFloat(frames[1].Raw,offset,23.5)
    le32(frames[1].Raw,offset+4,0x00001001)
    rows:=originalTimelineFromFrames(t,frames)
    if len(rows)!=1 {t.Fatal("unexpected ticks")}
    control:=decodedControl(t,rows[0])
    if len(control.RawSlots)!=0 {t.Fatal("initial snapshot falsely emitted current alarm")}
}

func TestStage111Z28B2OnlyFullDedicatedUpdateGetsRawEvidence(t *testing.T) {
    frames:=makeFixture()
    // The last frame is the original 76B VALUES tick; inject real source
    // record between preceding AUX and this tick, NO new network command.
    at:=len(frames)-1
    frames=append(frames[:at],append([]Frame{controlFixtureFrame(2,0xA5A50004,false)},frames[at:]...)...)
    rows:=originalTimelineFromFrames(t,frames)
    control:=decodedControl(t,rows[0])
    if !control.StatusFrameFreshForTick || len(control.RawSlots)!=8 {
        t.Fatalf("expected 8 raw status records from dedicated 64-word frame: %+v",control)
    }
    c:=control.RawSlots[0]
    if c.ADC!=3 || c.Slot!=1 || c.StatusBaseWord!="0x2530" ||
       c.SourceFrame==0 || c.RawValueFloat32!=13.5 ||
       c.RawStatusU32!=0xA5A50004 || c.RawStatusHex!="0xA5A50004" ||
       c.RawLastTransitionFloat32!=1.25 || c.RawReservedU32!=0xBADC0FFE {
       t.Fatalf("incorrect source bit mapping: %+v",c)
    }
}

func TestStage111Z28B2PreviousTickControlWordNeverCarriedForward(t *testing.T) {
    frames:=makeFixture()
    oldAux:=frames[len(frames)-2]
    oldTick:=frames[len(frames)-1]
    at:=len(frames)-1
    frames=append(frames[:at],append([]Frame{controlFixtureFrame(0,0x00000002,false)},frames[at:]...)...)
    frames=append(frames,oldAux,oldTick)
    rows:=originalTimelineFromFrames(t,frames)
    if len(rows)!=2 {t.Fatalf("expected two ticks got %d",len(rows))}
    if len(decodedControl(t,rows[0]).RawSlots)!=8 {t.Fatal("first tick lost fresh control source")}
    if len(decodedControl(t,rows[1]).RawSlots)!=0 {
        t.Fatal("stale previous-tick status presented as current")
    }
}

func TestStage111Z28B2FragmentOrBadFloatNeverBreaksPreviousRawExport(t *testing.T) {
    tests:=[]struct{name string;block Frame}{
        {"short_status_fragment",syntheticParam(40,[]RegBlock{{
            Addr:0x2130,Words:4,Payload:make([]byte,8)}})},
        {"nonfinite_optional_status",controlFixtureFrame(0,0x20,true)},
    }
    for _,tc:=range tests {
        t.Run(tc.name,func(t *testing.T){
            frames:=makeFixture()
            at:=len(frames)-1
            frames=append(frames[:at],append([]Frame{tc.block},frames[at:]...)...)
            rows:=originalTimelineFromFrames(t,frames)
            control:=decodedControl(t,rows[0])
            if len(control.RawSlots)!=0 && tc.name=="short_status_fragment" {
                t.Fatal("partial status copied as a full original alarm")
            }
            if tc.name=="nonfinite_optional_status" {
                for _,item:=range control.RawSlots {
                    if item.Slot==1 && item.ADC==1 {
                        t.Fatal("nonfinite optional control value must be suppressed")
                    }
                }
            }
        })
    }
}
