package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
)

func TestStage111Z28RealSourceTickRegistersPreservedInExistingTimeline(t *testing.T) {
    frames:=makeFixture()
    // Independent synthetic register words: two TACH banks and global DSP
    // at the offsets used by original register image parsing.
    // Full snapshot data begins after 28-byte envelope + 4-byte block hdr.
    le32(frames[1].Raw, 32+0x1020*2, 0x00000104)
    tick:=frames[len(frames)-1].Raw
    leFloat(tick,32,13.25)
    leFloat(tick,36,22.5)
    le32(tick,40,0xDEADBEEF)
    le32(tick,44,42)
    le32(tick,48,0x80000400)
    leFloat(tick,56,9.75)
    leFloat(tick,60,2.125)
    le32(tick,64,0x01020304)
    le32(tick,68,7)
    le32(tick,72,77)

    raw,manifest,summary:=writeFixture(t,frames)
    dest:=filepath.Join(t.TempDir(),"export")
    report,err:=export(raw,manifest,summary,dest,7*60)
    if err!=nil {t.Fatal(err)}
    if len(report.GeneratedFiles)!=19 {
        t.Fatalf("must retain original nineteen-file audited contract, got %d",len(report.GeneratedFiles))
    }
    body,err:=os.ReadFile(filepath.Join(dest,"TIMELINE.json"))
    if err!=nil {t.Fatal(err)}
    sum:=sha256.Sum256(body)
    if report.GeneratedFiles["TIMELINE.json"]!=hex.EncodeToString(sum[:]) {
        t.Fatal("timeline with DSP/TACH words must be covered by existing SHA manifest")
    }
    var rows []struct {
        Schema string `json:"dsp_tach_schema"`
        DSP uint32 `json:"dsp_status_raw"`
        DSPHex string `json:"dsp_status_hex"`
        DSPRegister string `json:"dsp_status_register_word"`
        Update int `json:"update"`
        AUXFrame uint64 `json:"aux_frame"`
        TickFrame uint64 `json:"tick_frame"`
        Clock string `json:"time_kind"`
        VerifiedRPM bool `json:"tach_units_and_rpm_verified"`
        Tach []OriginalTachRegisterWords `json:"tach_channels"`
    }
    if err:=json.Unmarshal(body,&rows);err!=nil {t.Fatal(err)}
    if len(rows)!=1 || rows[0].Schema!=dspTachTimelineSchema ||
        rows[0].DSP!=0x104 || rows[0].DSPHex!="0x00000104" ||
        rows[0].DSPRegister!="0x1020" || rows[0].Update!=1 ||
        rows[0].AUXFrame==0 || rows[0].TickFrame<=rows[0].AUXFrame ||
        rows[0].Clock!="HOST_RECEIVE_CLOCK_NOT_DSP_SYNCHRONIZED" ||
        rows[0].VerifiedRPM || len(rows[0].Tach)!=2 {
        t.Fatalf("unverified or lost tick evidence %+v",rows)
    }
    first:=rows[0].Tach[0]
    second:=rows[0].Tach[1]
    if first.RegisterBase!="0x3000" || first.TACH!=1 ||
        first.Float32Words[0]!=13.25 || first.Float32Words[1]!=22.5 ||
        first.Uint32Words[0]!=0xDEADBEEF || first.Uint32Words[1]!=42 ||
        first.Uint32Words[2]!=0x80000400 {
        t.Fatalf("TACH1 real raw fields were modified: %+v",first)
    }
    if second.RegisterBase!="0x3100" || second.TACH!=2 ||
        second.Float32Words[0]!=9.75 || second.Float32Words[1]!=2.125 ||
        second.Uint32Words[0]!=0x01020304 || second.Uint32Words[1]!=7 ||
        second.Uint32Words[2]!=77 {
        t.Fatalf("TACH2 raw words were incorrectly decoded: %+v",second)
    }
    if report.Channels[6].StatusCounts["0x00000400"]!=1 {
        t.Fatal("old AUX ADC status 0x400 may not be changed")
    }
}

func TestStage111Z28TimelineDefaultCannotInventRpm(t *testing.T) {
    data:=originalTickTimeline(snapshot{},0)
    if data["tach_units_and_rpm_verified"]!=false {t.Fatal("unexpected invented RPM")}
    if data["dsp_status_raw"]!=uint32(0) {t.Fatal("default DSP status should be raw zero")}
}
