package main

import (
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestNativeLiveStatusAtomicOptIn(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "TEST_fake")
    m, err := NewMonitor(dir, "OFFLINE_REPLAY", "10.13.42.84")
    if err != nil { t.Fatal(err) }
    defer m.CloseFiles()
    m.publishLiveStatus("RECORDING", true, "")
    if _, err := os.Stat(filepath.Join(dir, liveStatusName)); !os.IsNotExist(err) {
        t.Fatal("live sidecar must be opt-in; ordinary R6.1 behavior must stay unchanged")
    }
    m.liveProgressEnabled = true
    m.liveTargetSeconds = 30
    m.summary.SelectedLocalIPv4 = "10.13.42.22"
    m.summary.SocketRemoteAddr = "10.13.42.84:10230"
    m.summary.RawBytes = 1052
    m.summary.TotalFrames = 1
    m.summary.Channels[3].Samples = 256
    m.summary.Channels[3].Frames = 1
    m.summary.Channels[3].rates[65536] = true
    m.summary.Channels[6].Samples = 256
    m.liveDSPSeen[6] = true
    m.liveDSPStatus[6] = 0x00000400
    m.liveLastPacket = time.Now()
    m.liveLastAUXUTC = time.Now().UTC().Format(time.RFC3339Nano)
    m.publishLiveStatus("RECORDING", true, "")
    f := filepath.Join(dir, liveStatusName)
    assert := func(expected string) {
        t.Helper()
        data, err := os.ReadFile(f)
        if err != nil { t.Fatal(err) }
        var report LiveStatus
        if err := json.Unmarshal(data, &report); err != nil { t.Fatal(err) }
        if report.Schema != liveStatusSchema || report.Phase != expected ||
            report.SessionID != "TEST_fake" || report.RawBytes != 1052 ||
            len(report.Channels) != 10 || !report.ReadOnly {
            t.Fatalf("wrong live status: %+v", report)
        }
        if report.Channels[6].DSPStatusHex == nil ||
            *report.Channels[6].DSPStatusHex != "0x00000400" {
            t.Fatal("real AUX-based status must survive exactly; no fabricated healthy label")
        }
        if report.Channels[0].DSPStatusHex != nil || report.Channels[8].Type != "TACH" ||
            report.Channels[3].SampleRatesHz[0] != 65536 {
            t.Fatal("unknown ADC must remain unknown; 8 ADC + 2 TACH order")
        }
    }
    assert("RECORDING")
    m.publishLiveStatus("VERIFYING", true, "")
    assert("VERIFYING")
    m.publishLiveStatus("COMPLETED", true, "EXPORTED")
    assert("COMPLETED")
    if x, _ := filepath.Glob(filepath.Join(dir, ".mvk_live_status_pending_*")); len(x) != 0 {
        t.Fatal("atomic sidecar must not leave temporary JSON")
    }
}

func TestLiveStatusJSONWriteFailureDoesNotInterruptCapture(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "TEST_fail")
    m, err := NewMonitor(dir, "OFFLINE_REPLAY", "")
    if err != nil { t.Fatal(err) }
    defer m.CloseFiles()
    m.liveProgressEnabled = true
    // A local read-only UI sidecar failure must not terminate the original
    // capture; no device commands or data-path changes are permitted.
    if err := os.Mkdir(filepath.Join(dir, liveStatusName), 0700); err != nil { t.Fatal(err) }
    m.publishLiveStatus("RECORDING", true, "")
    if m.liveProgressEnabled || m.summary.WarningCount != 1 {
        t.Fatal("telemetry error must be logged and disabled, not hidden")
    }
}
