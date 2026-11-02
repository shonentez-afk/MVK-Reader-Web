package main

// Stage111Z.26: opt-in read-only LOCAL status sidecar for the Qt supervisor.
// One original TCP/10230 receiver, no extra device socket/commands.
// Does not read or rewrite RAW/BIN, and is never part of the source export.

import (
    "encoding/json"
    "fmt"
    "os"
    "path/filepath"
    "time"
)

const liveStatusName = "MVK_NATIVE_LIVE_STATUS.json"
const liveStatusSchema = "MVK_NATIVE_R6_LIVE_STATUS_V1"

type LiveChannelStatus struct {
    Channel                 int      `json:"channel"`
    Type                    string   `json:"type"`
    Frames                  uint64   `json:"frames"`
    Samples                 uint64   `json:"samples"`
    SampleRatesHz           []uint32 `json:"sample_rates_hz"`
    SequenceDiscontinuities uint64   `json:"sequence_discontinuities"`
    NonFiniteSamples        uint64   `json:"nonfinite_samples"`
    DSPStatusHex            *string  `json:"dsp_sensor_status_hex"`
}

type LiveStatus struct {
    Schema                 string              `json:"schema"`
    Phase                  string              `json:"phase"`
    SessionID              string              `json:"session_id"`
    UpdatedUTC             string              `json:"updated_utc"`
    ElapsedSeconds         float64             `json:"elapsed_seconds"`
    TargetSeconds          int                 `json:"target_seconds"`
    InstrumentIP           string              `json:"instrument_ipv4"`
    SelectedLocalIPv4      string              `json:"selected_local_ipv4"`
    SocketRemote           string              `json:"socket_remote"`
    ReadOnly               bool                `json:"read_only_no_app_payload_sent"`
    RawBytes               uint64              `json:"raw_bytes"`
    TotalFrames            uint64              `json:"frames_decoded"`
    InvalidFrames          uint64              `json:"invalid_frames"`
    CaptureOnly            bool                `json:"capture_only"`
    AUXUpdates             uint64              `json:"aux4700_updates"`
    FullSnapshots          uint64              `json:"full_register_snapshots"`
    WarningCount           uint64              `json:"warning_count"`
    SecondsSinceLastPacket *float64            `json:"seconds_since_last_packet"`
    LastAUXUTC             *string             `json:"last_aux_received_utc"`
    Channels               []LiveChannelStatus `json:"channels"`
    EndReason              string              `json:"end_reason,omitempty"`
    ExportStatus           string              `json:"export_status,omitempty"`
    ProgressError          string              `json:"progress_error,omitempty"`
}

// This function is called by the SAME goroutine as ProcessChunk. There is
// deliberately no concurrent reading of Monitor maps/ring buffers.
func (m *Monitor) snapshotLiveStatus(phase string, now time.Time) LiveStatus {
    report := m.Snapshot()
    channels := make([]LiveChannelStatus, 0, 10)
    for i, c := range report.Channels {
        typ := "ADC"
        if i >= 8 { typ = "TACH" }
        item := LiveChannelStatus{
            Channel: c.Channel, Type: typ, Frames: c.Frames, Samples: c.Samples,
            SampleRatesHz: c.Rates, SequenceDiscontinuities: c.SequenceDiscontinuities,
            NonFiniteSamples: c.NonFiniteSamples,
        }
        if i < 8 && m.liveDSPSeen[i] {
            status := fmt.Sprintf("0x%08X", m.liveDSPStatus[i])
            item.DSPStatusHex = &status
        }
        channels = append(channels, item)
    }
    var lastAUX *string
    if m.liveLastAUXUTC != "" {
        x := m.liveLastAUXUTC
        lastAUX = &x
    }
    var since *float64
    if !m.liveLastPacket.IsZero() {
        t := now.Sub(m.liveLastPacket).Seconds()
        if t < 0 { t = 0 }
        since = &t
    }
    elapsed := now.Sub(m.start).Seconds()
    if elapsed < 0 { elapsed = 0 }
    return LiveStatus{
        Schema: liveStatusSchema, Phase: phase, SessionID: filepath.Base(m.dir),
        UpdatedUTC: now.UTC().Format(time.RFC3339Nano),
        ElapsedSeconds: elapsed, TargetSeconds: m.liveTargetSeconds,
        InstrumentIP: report.IP, SelectedLocalIPv4: report.SelectedLocalIPv4,
        SocketRemote: report.SocketRemoteAddr, ReadOnly: report.ReadOnly,
        RawBytes: report.RawBytes, TotalFrames: report.TotalFrames,
        InvalidFrames: report.InvalidFrames, CaptureOnly: report.CaptureOnly,
        AUXUpdates: report.Aux4700, FullSnapshots: report.FullSnapshots,
        WarningCount: report.WarningCount, LastAUXUTC: lastAUX,
        SecondsSinceLastPacket: since, Channels: channels,
        EndReason: report.EndReason,
    }
}

// Atomic JSON replacement: Qt sees either the complete previous snapshot or
// complete new one; no extra I/O on RAW/BIN. Disabled by default.
func (m *Monitor) publishLiveStatus(phase string, force bool, exportStatus string) {
    if !m.liveProgressEnabled { return }
    now := time.Now()
    if !force && !m.liveProgressAt.IsZero() && now.Sub(m.liveProgressAt) < 750*time.Millisecond {
        return
    }
    state := m.snapshotLiveStatus(phase, now)
    state.ExportStatus = exportStatus
    if err := writeLiveStatusAtomic(m.dir, state); err != nil {
        m.liveProgressEnabled = false
        // Only optional UI telemetry failed: continue recording the original
        // RAW, but make the failure visible in the ordinary log/audit.
        m.warn("Live Qt status sidecar disabled; recording continues: " + err.Error())
        fmt.Println("WARNING: live status sidecar failed; original RAW capture continues:", err)
        return
    }
    m.liveProgressAt = now
}

func writeLiveStatusAtomic(dir string, report LiveStatus) error {
    data, err := json.Marshal(report)
    if err != nil { return err }
    data = append(data, '\n')
    file, err := os.CreateTemp(dir, ".mvk_live_status_pending_")
    if err != nil { return err }
    tmp := file.Name()
    defer os.Remove(tmp)
    if err = file.Chmod(0600); err != nil { file.Close(); return err }
    if _, err = file.Write(data); err != nil { file.Close(); return err }
    if err = file.Sync(); err != nil { file.Close(); return err }
    if err = file.Close(); err != nil { return err }
    return os.Rename(tmp, filepath.Join(dir, liveStatusName))
}
