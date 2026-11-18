package main

// Source TMVKThread 0080822F..0080828C does not classify early
// ADC payload as a malformed application packet merely because the
// independent forensic BIN gain snapshot is not available yet.
// Original TMvkChannelStorage.Create initializes FRange to 1.0.
// Original calibration/X87 parity remains unverified.
import (
    "bytes"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalSourceADCBeforeFullPARAMRetainsRXWithoutFalseFramingError(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_original_pre_param"),
        "LIVE_READ_ONLY","")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    if e:=m.EnableLiveBinSpool();e!=nil {t.Fatal(e)}
    if m.liveBin.begun {t.Fatal("gain image invented before real full PARAM")}
    adc:=makeSample(typeADC,0,65536,0xFFFFFF00)
    if e:=m.ProcessChunk(adc,time.Now());e!=nil {t.Fatal(e)}
    if m.captureOnly || m.summary.CaptureOnly || m.summary.InvalidFrames!=0 ||
       m.summary.Channels[0].Samples!=256 || m.liveBin.begun {
        t.Fatal("real source ADC incorrectly stopped by optional forensic BIN")
    }
    if m.summary.RawBytes!=uint64(len(adc)) {
        t.Fatal("original TCP RAW not preserved before gain")
    }
    row:=m.sourceOriginalStorage.receipt().Channels[0]
    if row.RxPos!=256 || row.Available!=256 ||
       row.Domain!=sourceStorageUnscaledADC ||
       row.NextDeviceIndex==nil || *row.NextDeviceIndex!=0 {
        t.Fatalf("original source default FRange storage unavailable: %+v",row)
    }
    source,e:=m.sourceOriginalStorage.window(0,0,256)
    if e!=nil || !bytes.Equal(source,adc[28:]) {
        t.Fatal("real pre-PARAM source ADC Float32 bits lost",e)
    }
    // Forensic calibration cannot invent a 256-sample BIN or identify
    // its source FRange. The original raw file still contains every byte.
    if m.liveBin.samples[0]!=0 || m.liveBin.files[0]!=nil {
        t.Fatal("forensic verified gain invented before initial PARAM")
    }
    raw,e:=os.ReadFile(m.raw.Name())
    if e!=nil || !bytes.Equal(raw,adc) {
        t.Fatal("forensic original RX bytes changed by pre-PARAM gate",e)
    }
}

func TestOriginalSourceWrongRateBeforePARAMStillRemainsOnlyInRAW(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_original_pre_param_rate"),
        "LIVE_READ_ONLY","")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    if e:=m.EnableLiveBinSpool();e!=nil {t.Fatal(e)}
    adc:=makeSample(typeADC,1,8192,123)
    if e:=m.ProcessChunk(adc,time.Now());e!=nil {t.Fatal(e)}
    if m.summary.RawBytes!=uint64(len(adc)) ||
       m.summary.Channels[1].Samples!=256 ||
       m.sourceOriginalStorage.receipt().Channels[1].RxPos!=0 ||
       m.sourceOriginalRXGate.skippedRate[1]!=256 ||
       m.summary.InvalidFrames!=0 || m.captureOnly {
        t.Fatal("wrong-rate early source ADC must be RAW-only, not framing error")
    }
}
