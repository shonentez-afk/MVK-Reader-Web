package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "hash"
    "os"
    "path/filepath"
)

// The original TCP protocol has ten channels, including TACH channels 8/9
// (zero based). TACH is NOT an ADC, so Float32 samples MUST NOT receive ADC
// calibration or be passed off as original MVKView BIN/TSXML recordings.
// Here the EXACT 256 payload bytes from each verified 284-byte TACH frame
// are copied to a separately named, SHA-checked Native evidence file.
// The instrument is never contacted or commanded by this module.
const tachEvidenceSchema = "MVK_NATIVE_R6_TACH_RAW_INPUT_V1"
const tachEvidenceName = "TACH_RAW_SOURCE_AUDIT.json"

type TachChannelEvidence struct {
    Channel           int    `json:"channel"`
    Present           bool   `json:"present"`
    Filename          string `json:"filename,omitempty"`
    Frames            uint64 `json:"frames"`
    Samples           uint64 `json:"samples"`
    Bytes             uint64 `json:"bytes"`
    FirstSampleIndex  uint32 `json:"first_sample_index"`
    LastFrameIndex    uint32 `json:"last_frame_first_sample_index"`
    SampleRateHz      uint32 `json:"first_sample_rate_hz"`
    SequenceGaps      uint64 `json:"sequence_discontinuities"`
    RateChanges       uint64 `json:"sample_rate_changes"`
    SHA256            string `json:"sha256,omitempty"`
    Contiguous        bool   `json:"contiguous_constant_rate"`
    Calibrated        bool   `json:"physical_calibration_verified"`
}

type TachRawEvidence struct {
    Schema               string                `json:"schema"`
    SourceRawSHA256      string                `json:"source_raw_sha256"`
    InputDomain          string                `json:"input_domain"`
    NoDeviceCommands     bool                  `json:"device_commands_sent"`
    OriginalBINParity    bool                  `json:"original_tach_bin_parity_verified"`
    Channels             [2]TachChannelEvidence `json:"channels"`
}

type tachRawDumper struct {
    files        [2]*os.File
    hashes       [2]hash.Hash
    records      [2]TachChannelEvidence
    next         [2]uint32
    rate         [2]uint32
}

func newTachRawDumper() *tachRawDumper {
    t := &tachRawDumper{}
    t.records[0].Channel = 9  // Native index 8, source TACH1
    t.records[1].Channel = 10 // Native index 9, source TACH2
    return t
}

func (t *tachRawDumper) closeFiles() error {
    var first error
    for i, f := range t.files {
        if f != nil {
            if err := f.Sync(); err != nil && first == nil { first = err }
            if err := f.Close(); err != nil && first == nil { first = err }
            t.files[i] = nil
        }
    }
    return first
}

func (t *tachRawDumper) add(stage string, f Frame, h SampleHeader) error {
    if f.Type != typeTach || len(f.Raw) != 284 ||
        h.Channel < 8 || h.Channel > 9 ||
        h.Samples != 64 || h.NonFinite != 0 || !acceptedRates[h.Rate] {
        return errors.New("untrusted TACH frame cannot be exported")
    }
    idx := h.Channel-8
    record := &t.records[idx]
    if !record.Present {
        filename := fmt.Sprintf("TACH%d_NATIVE_UNCALIBRATED.f32", idx+1)
        file, err := os.OpenFile(filepath.Join(stage, filename),
            os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
        if err != nil { return err }
        t.files[idx] = file
        t.hashes[idx] = sha256.New()
        t.rate[idx] = h.Rate
        record.Present = true
        record.Filename = filename
        record.FirstSampleIndex = h.Index
        record.SampleRateHz = h.Rate
    } else {
        // The real tachometer may change rate or jump sample indices;
        // faithfully retain every raw byte, but mark that the series is NOT
        // a contiguous periodic waveform. No interpolation is attempted.
        if h.Index != t.next[idx] { record.SequenceGaps++ }
        if h.Rate != t.rate[idx] { record.RateChanges++ }
    }
    payload := f.Raw[28:284]
    n, err := t.files[idx].Write(payload)
    if err != nil { return err }
    if n != len(payload) { return errors.New("short TACH payload write") }
    if _, err := t.hashes[idx].Write(payload); err != nil { return err }
    record.Frames++
    record.Samples += 64
    record.Bytes += uint64(len(payload))
    record.LastFrameIndex = h.Index
    t.next[idx] = h.Index+64
    return nil
}

func (t *tachRawDumper) finish(stage, rawSHA string) (map[string]string,error) {
    if err := t.closeFiles(); err != nil { return nil,err }
    if len(rawSHA) != 64 { return nil,errors.New("untrusted RAW SHA256 for TACH evidence") }
    // A capture with NO TACH frames must preserve the existing verified
    // 19-file Native export contract byte-for-byte. New TACH evidence and
    // its audit sidecar exist only when an actual original TCP TACH packet
    // was present. Never synthesize a "missing" TACH output file.
    if !t.records[0].Present && !t.records[1].Present {
        return map[string]string{},nil
    }
    evidence := TachRawEvidence{
        Schema: tachEvidenceSchema,
        SourceRawSHA256: rawSHA,
        InputDomain: "DEVICE_TACH_INPUT_FLOAT32_UNSCALED",
        NoDeviceCommands: false,
        OriginalBINParity: false,
    }
    hashes := make(map[string]string)
    for i := 0; i < 2; i++ {
        rec := t.records[i]
        if rec.Present {
            if t.hashes[i] == nil || rec.Bytes != rec.Samples*4 {
                return nil,errors.New("TACH source payload count mismatch")
            }
            rec.SHA256 = hex.EncodeToString(t.hashes[i].Sum(nil))
            rec.Contiguous = rec.SequenceGaps == 0 && rec.RateChanges == 0
            hashes[rec.Filename] = rec.SHA256
        }
        evidence.Channels[i] = rec
    }
    data,err := json.MarshalIndent(evidence,"","  ")
    if err != nil { return nil,err }
    data = append(data, byte(10))
    if err=os.WriteFile(filepath.Join(stage,tachEvidenceName),data,0600); err != nil {
        return nil,err
    }
    digest:=sha256.Sum256(data)
    hashes[tachEvidenceName]=hex.EncodeToString(digest[:])
    return hashes,nil
}
