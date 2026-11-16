package main

import (
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "math"
    "os"
    "path/filepath"
    "testing"
)

func readTachAudit(t *testing.T,dir string) TachRawEvidence {
    t.Helper()
    data,err:=os.ReadFile(filepath.Join(dir,tachEvidenceName))
    if err!=nil {t.Fatal(err)}
    var audit TachRawEvidence
    if err=json.Unmarshal(data,&audit);err!=nil {t.Fatal(err)}
    if audit.Schema!=tachEvidenceSchema || audit.NoDeviceCommands ||
       audit.OriginalBINParity || audit.InputDomain!="DEVICE_TACH_INPUT_FLOAT32_UNSCALED" {
       t.Fatalf("bad source-only provenance: %+v",audit)
    }
    return audit
}

func TestTachBothOriginalTCPChannelsPreserveExactInputF32(t *testing.T) {
    frames:=makeFixture()
    frames=append(frames,syntheticFrame(8,0,1.25))
    frames=append(frames,syntheticFrame(9,0,2.25))
    frames=append(frames,syntheticFrame(8,64,1.5))
    frames=append(frames,syntheticFrame(9,64,2.5))
    raw,csvFile,summary:=writeFixture(t,frames)
    out:=filepath.Join(t.TempDir(),"export")
    report,err:=export(raw,csvFile,summary,out,0)
    if err!=nil {t.Fatal(err)}
    audit:=readTachAudit(t,out)
    if audit.SourceRawSHA256!=report.SourceRawSHA {t.Fatal("TACH from foreign RAW")}
    for i:=0;i<2;i++ {
        row:=audit.Channels[i]
        if row.Channel!=9+i || !row.Present || !row.Contiguous ||
           row.Frames!=2 || row.Samples!=128 || row.Bytes!=512 ||
           row.FirstSampleIndex!=0 || row.LastFrameIndex!=64 ||
           row.SampleRateHz!=65536 || row.Calibrated ||
           row.SequenceGaps!=0 || row.RateChanges!=0 {
            t.Fatalf("bad channel %d audit: %+v",i+1,row)
        }
        if row.Filename!="TACH"+string(rune('1'+i))+"_NATIVE_UNCALIBRATED.f32" {
            t.Fatalf("bad file name: %s",row.Filename)
        }
        payload,err:=os.ReadFile(filepath.Join(out,row.Filename))
        if err!=nil {t.Fatal(err)}
        h:=sha256.Sum256(payload)
        if hex.EncodeToString(h[:])!=row.SHA256 ||
           row.SHA256!=report.GeneratedFiles[row.Filename] ||
           len(payload)!=512 {
            t.Fatal("TACH payload bytes/hash changed")
        }
        first:=math.Float32frombits(binary.LittleEndian.Uint32(payload[:4]))
        expected:=float32(1.25+float64(i))
        if first!=expected {t.Fatalf("TACH%d input Float32 altered: %g",i+1,first)}
    }
    if report.GeneratedFiles[tachEvidenceName]=="" {t.Fatal("missing sidecar hash")}
    for i:=0;i<8;i++ { // original eight calibrated ADC outputs unchanged
        if report.Channels[i].Samples!=512 {t.Fatalf("ADC%d disturbed",i+1)}
    }
}

func TestTachAbsentExplicitAndNeverInventRaw(t *testing.T) {
    raw,csvFile,summary:=writeFixture(t,makeFixture())
    out:=filepath.Join(t.TempDir(),"export")
    report,err:=export(raw,csvFile,summary,out,0)
    if err!=nil {t.Fatal(err)}
    audit:=readTachAudit(t,out)
    for _,row:=range audit.Channels {
        if row.Present || row.Frames!=0 || row.Filename!="" || row.Samples!=0 {
            t.Fatalf("fabricated missing TACH: %+v",row)
        }
    }
    if len(report.GeneratedFiles)!=20 {t.Fatalf("unexpected source archive count %d",len(report.GeneratedFiles))}
}

func TestTachGapIsAuditedNotFakeContinuousWaveform(t *testing.T) {
    frames:=makeFixture()
    frames=append(frames,syntheticFrame(8,0,1))
    frames=append(frames,syntheticFrame(8,128,1))
    raw,csvFile,summary:=writeFixture(t,frames)
    out:=filepath.Join(t.TempDir(),"export")
    _,err:=export(raw,csvFile,summary,out,0)
    if err!=nil {t.Fatal(err)}
    row:=readTachAudit(t,out).Channels[0]
    if !row.Present || row.SequenceGaps!=1 || row.Contiguous {
        t.Fatalf("TACH gap was incorrectly treated as continuous: %+v",row)
    }
}

func TestNonFiniteTachRejectsExportAndPreservesRaw(t *testing.T) {
    frames:=append(makeFixture(),syntheticFrame(9,0,float32(math.NaN())))
    raw,csvFile,summary:=writeFixture(t,frames)
    out:=filepath.Join(t.TempDir(),"export")
    if _,err:=export(raw,csvFile,summary,out,0);err==nil {
        t.Fatal("non-finite tachometer data accepted")
    }
    if _,err:=os.Stat(raw);err!=nil {t.Fatal("original RAW must remain untouched")}
    if _,err:=os.Stat(out);!os.IsNotExist(err) {
        t.Fatal("failed TACH export published as completed")
    }
}
