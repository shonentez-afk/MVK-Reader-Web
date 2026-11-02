package main

// Stage111Z.26B: local bounded calibrated *preview*, NOT an accepted BIN export.
//
// The sole original TCP/10230 reader already writes each calibrated float32
// byte string into the unmodified Stage108 temporary BIN. Only when explicitly
// enabled for the Qt GUI do we COPY those very bytes to an in-memory ring.
// A small, self-contained ZIP is atomically replaced; UI never touches partial
// BIN, opens a socket, applies gain or mutates original RAW/exports.
import (
    "archive/zip"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "os"
    "path/filepath"
    "time"
)

const livePreviewFile = "MVK_NATIVE_LIVE_PREVIEW.zip"
const livePreviewSchema = "MVK_NATIVE_R6_CALIBRATED_PREVIEW_V1"
const livePreviewDomain = "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
const livePreviewSamples = 8192 // 0.125 s @ 65536 Hz, 8 channels = 256 KiB

type LivePreviewBuffer struct {
    bytes [8][]byte
    samples [8]uint64
    next [8]uint32
    rate [8]uint32
}

type LivePreviewChannel struct {
    ADC int `json:"adc"`
    Entry string `json:"entry"`
    Samples int `json:"samples"`
    SampleRateHz uint32 `json:"sample_rate_hz"`
    FirstSampleIndex uint32 `json:"first_sample_index"`
    NextSampleIndex uint32 `json:"next_sample_index"`
    SHA256 string `json:"sha256"`
}

type LivePreviewManifest struct {
    Schema string `json:"schema"`
    SessionID string `json:"session_id"`
    Phase string `json:"phase"`
    UpdatedUTC string `json:"updated_utc"`
    InputDomain string `json:"input_domain"`
    CalibrationAlreadyApplied bool `json:"calibration_already_applied"`
    ReadOnly bool `json:"read_only_no_app_payload_sent"`
    Provisional bool `json:"provisional_not_audited"`
    RawBytes uint64 `json:"raw_bytes"`
    FramesDecoded uint64 `json:"frames_decoded"`
    Channels []LivePreviewChannel `json:"channels"`
}

func newLivePreviewBuffer() *LivePreviewBuffer { return &LivePreviewBuffer{} }

// Called ONLY after a successful original spool.Write(bytesOut), and ONLY on
// the sole receiver goroutine. No new calibration arithmetic or file I/O.
func (p *LivePreviewBuffer) appendCalibratedADC(h SampleHeader, written []byte) error {
    if p == nil { return nil }
    if h.Channel >= 8 || h.Samples != 256 || len(written) != 1024 || h.Rate == 0 {
        return fmt.Errorf("preview received invalid verified spool block")
    }
    ch := int(h.Channel)
    if p.bytes[ch] == nil {
        p.bytes[ch] = make([]byte, livePreviewSamples*4)
    }
    start := int(p.samples[ch]%livePreviewSamples)*4
    // 8192 is a multiple of 256; each received ADC frame is one contiguous
    // slice. These bits are the actual, already-calibrated native BIN bytes.
    copy(p.bytes[ch][start:start+len(written)], written)
    p.samples[ch] += uint64(h.Samples)
    p.next[ch] = h.Index + 256
    p.rate[ch] = h.Rate
    return nil
}

func (p *LivePreviewBuffer) channelBytes(ch int) ([]byte, int, uint32) {
    n := int(p.samples[ch])
    if n > livePreviewSamples { n = livePreviewSamples }
    if n == 0 { return nil, 0, 0 }
    start := int((p.samples[ch]-uint64(n))%livePreviewSamples)*4
    out := make([]byte, n*4)
    if start+len(out) <= len(p.bytes[ch]) {
        copy(out, p.bytes[ch][start:start+len(out)])
    } else {
        left := len(p.bytes[ch])-start
        copy(out, p.bytes[ch][start:])
        copy(out[left:], p.bytes[ch][:len(out)-left])
    }
    // Frame sequences are enforced by existing LiveBinSpool.adcFrame.
    return out,n,p.next[ch]-uint32(n)
}

func writePreviewAtomic(dir string, p *LivePreviewBuffer, summary Summary, now time.Time) error {
    if p == nil { return nil }
    hasSamples:=false
    for _,samples:=range p.samples { if samples>0 { hasSamples=true; break } }
    if !hasSamples { return nil } // Never publish an invented empty ADC window.
    tmp, err := os.CreateTemp(dir, ".mvk_live_preview_pending_")
    if err != nil { return err }
    tempName := tmp.Name()
    defer os.Remove(tempName)
    if err := tmp.Chmod(0600); err != nil { tmp.Close(); return err }
    z := zip.NewWriter(tmp)
    manifest := LivePreviewManifest{
        Schema: livePreviewSchema, SessionID: filepath.Base(dir),
        Phase: "RECORDING", UpdatedUTC: now.UTC().Format(time.RFC3339Nano),
        InputDomain: livePreviewDomain, CalibrationAlreadyApplied: true,
        ReadOnly: summary.ReadOnly, Provisional: true,
        RawBytes: summary.RawBytes, FramesDecoded: summary.TotalFrames,
        Channels: []LivePreviewChannel{},
    }
    for ch:=0; ch<8; ch++ {
        raw,n,first:=p.channelBytes(ch)
        if n==0 { continue }
        name:=fmt.Sprintf("ADC%d.f32",ch+1)
        w,e:=z.Create(name)
        if e!=nil { z.Close(); tmp.Close(); return e }
        if _,e=w.Write(raw); e!=nil { z.Close(); tmp.Close(); return e }
        digest:=sha256.Sum256(raw)
        manifest.Channels=append(manifest.Channels,LivePreviewChannel{
            ADC:ch+1,Entry:name,Samples:n,SampleRateHz:p.rate[ch],
            FirstSampleIndex:first,NextSampleIndex:p.next[ch],
            SHA256:hex.EncodeToString(digest[:]),
        })
    }
    meta,err:=json.Marshal(manifest)
    if err!=nil { z.Close(); tmp.Close(); return err }
    w,err:=z.Create("MANIFEST.json")
    if err!=nil { z.Close(); tmp.Close(); return err }
    if _,err=w.Write(meta); err!=nil { z.Close(); tmp.Close(); return err }
    if err=z.Close(); err!=nil { tmp.Close(); return err }
    if err=tmp.Sync(); err!=nil { tmp.Close(); return err }
    if err=tmp.Close(); err!=nil { return err }
    return os.Rename(tempName,filepath.Join(dir,livePreviewFile))
}
