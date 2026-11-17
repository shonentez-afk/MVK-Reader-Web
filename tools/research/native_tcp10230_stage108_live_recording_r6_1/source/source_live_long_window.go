package main

// Stage111Z31FJ: one read-only, bounded, on-demand local selection of the
// original 2^21 Float32 source ring. This is an IPC file handled by the SAME
// Go TCP reader goroutine, NOT a second socket or a device command.
//
// _Unit115/GetSignal 007D0C30 + CheckDataAvailability 007D1998:
// a selected bAdcHScale window must be real, contiguous and still resident.
// Qt requests precisely one original H scale and source-end cursor.
// Source data remains provisional, not audited original x87/Delphi parity.
import (
    "archive/zip"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "os"
    "path/filepath"
    "regexp"
    "time"
)

const (
    sourceLongWindowRequestName="MVK_SOURCE_WINDOW_REQUEST.json"
    sourceLongWindowResultName="MVK_SOURCE_WINDOW_RESULT.zip"
    sourceLongWindowRequestSchema="MVK_SOURCE_LIVE_WINDOW_REQUEST_V1"
    sourceLongWindowResultSchema="MVK_SOURCE_LIVE_WINDOW_RESULT_V1"
    sourceLongWindowRequestMax=1024
)
var sourceLongWindowID=regexp.MustCompile("^[0-9a-f]{32}$")
var sourceLongWindowHScaleMS=[14]uint32{
    20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1,
}
type sourceLongWindowRequest struct {
    Schema string `json:"schema"`
    SessionID string `json:"session_id"`
    RequestID string `json:"request_id"`
    ADC int `json:"adc"`
    HTag int `json:"source_h_tag"`
    Samples uint32 `json:"samples"`
    CaptureEnd uint64 `json:"capture_end"`
    SampleRateHz uint32 `json:"sample_rate_hz"`
    DeviceEnd uint32 `json:"device_end_index"`
}
type sourceLongWindowResult struct {
    Schema string `json:"schema"`
    SessionID string `json:"session_id"`
    RequestID string `json:"request_id"`
    Phase string `json:"phase"`
    UpdatedUTC string `json:"updated_utc"`
    ADC int `json:"adc"`
    HTag int `json:"source_h_tag"`
    Entry string `json:"entry"`
    Samples uint32 `json:"samples"`
    CaptureEnd uint64 `json:"capture_end"`
    SampleRateHz uint32 `json:"sample_rate_hz"`
    FirstIndex uint32 `json:"first_sample_index"`
    NextIndex uint32 `json:"next_sample_index"`
    InputDomain string `json:"input_domain"`
    CalibrationAlreadyApplied bool `json:"calibration_already_applied"`
    Provisional bool `json:"provisional_not_audited"`
    RawBytes uint64 `json:"raw_bytes"`
    FramesDecoded uint64 `json:"frames_decoded"`
    SHA256 string `json:"sha256"`
}

func sourceLongWindowLength(rate uint32,tag int) (uint32,error) {
    if !acceptedRates[rate] || tag<0 || tag>=len(sourceLongWindowHScaleMS) {
        return 0,errors.New("invalid source bAdcHScale/rate")
    }
    n:=uint64(rate)*uint64(sourceLongWindowHScaleMS[tag])/1000
    if n<=livePreviewSamples || n>sourceOriginalStorageSamples {
        return 0,errors.New("not a source long-window selection")
    }
    return uint32(n),nil
}

func (m *Monitor) handleSourceLongWindowRequest(now time.Time) error {
    if m==nil || !m.liveProgressEnabled || m.sourceOriginalStorage==nil {
        return nil
    }
    if m.captureOnly || m.summary.SourceTCPMultiSocket ||
       m.sourceRateTransitionDetected || m.liveBin==nil {
        return nil
    }
    path:=filepath.Join(m.dir,sourceLongWindowRequestName)
    info,e:=os.Lstat(path)
    if errors.Is(e,os.ErrNotExist) {return nil}
    if e!=nil {return e}
    if !info.Mode().IsRegular() || info.Size()<=0 ||
       info.Size()>sourceLongWindowRequestMax {
        return errors.New("invalid local source long-window request size/type")
    }
    f,e:=os.Open(path)
    if e!=nil {return e}
    raw,e:=io.ReadAll(io.LimitReader(f,sourceLongWindowRequestMax+1))
    closeErr:=f.Close()
    if e!=nil{return e}
    if closeErr!=nil{return closeErr}
    if len(raw)>sourceLongWindowRequestMax {
        return errors.New("oversized local source long-window request")
    }
    var req sourceLongWindowRequest
    if e=json.Unmarshal(raw,&req);e!=nil {return errors.New("malformed local source long-window request")}
    if !sourceLongWindowID.MatchString(req.RequestID) ||
       req.Schema!=sourceLongWindowRequestSchema ||
       req.SessionID!=filepath.Base(m.dir) ||
       req.ADC<1 || req.ADC>8 {
        return errors.New("untrusted source long-window request identity")
    }
    // A duplicate request never causes the entire 2M window to be
    // re-read/re-written on each 750ms status publication.
    if m.sourceLongWindowLastID==req.RequestID {return nil}
    m.sourceLongWindowLastID=req.RequestID
    n,e:=sourceLongWindowLength(req.SampleRateHz,req.HTag)
    if e!=nil || req.Samples!=n {
        return errors.New("source HTag count mismatches actual Fs")
    }
    idx:=req.ADC-1
    channel:=&m.sourceOriginalStorage.channels[idx]
    summary:=m.summary.Channels[idx]
    if !channel.seen || channel.domain!=sourceStorageCalibratedADC ||
       channel.sampleRate!=req.SampleRateHz ||
       channel.rxPos!=summary.Samples ||
       summary.SequenceDiscontinuities>0 || summary.NonFiniteSamples>0 ||
       len(summary.rates)!=1 {
        return errors.New("source long window not a confirmed contiguous calibrated ADC stream")
    }
    if req.CaptureEnd<uint64(req.Samples) ||
       req.CaptureEnd>channel.rxPos {
        return errors.New("source long window requires real captured samples")
    }
    // Device header.Index wraps uint32 independently of local uint64
    // FRxPos. A late attach to a running MVK01 is allowed, a made-up
    // absolute index is not. The requested snapshot may lag behind Go
    // provided the exact slice has not been overwritten.
    lag:=channel.rxPos-req.CaptureEnd
    if lag>sourceOriginalStorageSamples-uint64(req.Samples) ||
       channel.nextDeviceIndex-uint32(lag)!=req.DeviceEnd {
        return errors.New("source long window stale or device index mismatch")
    }
    first:=req.CaptureEnd-uint64(req.Samples)
    data,e:=m.sourceOriginalStorage.window(idx,first,uint64(req.Samples))
    if e!=nil{return e}
    sum:=sha256.Sum256(data)
    entry:=fmt.Sprintf("ADC%d.f32",req.ADC)
    receipt:=sourceLongWindowResult{
        Schema:sourceLongWindowResultSchema,SessionID:req.SessionID,
        RequestID:req.RequestID,Phase:"RECORDING",
        UpdatedUTC:now.UTC().Format(time.RFC3339Nano),
        ADC:req.ADC,HTag:req.HTag,Entry:entry,
        Samples:req.Samples,CaptureEnd:req.CaptureEnd,
        SampleRateHz:req.SampleRateHz,
        FirstIndex:req.DeviceEnd-req.Samples,NextIndex:req.DeviceEnd,
        InputDomain:sourceStorageCalibratedADC,
        CalibrationAlreadyApplied:true,Provisional:true,
        RawBytes:m.summary.RawBytes,FramesDecoded:m.summary.TotalFrames,
        SHA256:hex.EncodeToString(sum[:]),
    }
    return writeSourceLongWindowAtomic(m.dir,entry,data,receipt)
}

func writeSourceLongWindowAtomic(dir,entry string,data []byte,
                                 receipt sourceLongWindowResult) error {
    // One selected original ADC at a time. Do not export 8*2M or the two
    // TACH byte rings to Qt, and do not change the forensic RAW/BIN spool.
    tmp,e:=os.CreateTemp(dir,".mvk_long_window_pending_")
    if e!=nil{return e}
    defer os.Remove(tmp.Name())
    if e=tmp.Chmod(0600);e!=nil {tmp.Close();return e}
    z:=zip.NewWriter(tmp)
    w,e:=z.CreateHeader(&zip.FileHeader{Name:entry,Method:zip.Store})
    if e!=nil {z.Close();tmp.Close();return e}
    if _,e=w.Write(data);e!=nil {z.Close();tmp.Close();return e}
    meta,e:=json.Marshal(receipt)
    if e!=nil {z.Close();tmp.Close();return e}
    w,e=z.Create("MANIFEST.json")
    if e!=nil {z.Close();tmp.Close();return e}
    if _,e=w.Write(meta);e!=nil {z.Close();tmp.Close();return e}
    if e=z.Close();e!=nil {tmp.Close();return e}
    if e=tmp.Sync();e!=nil {tmp.Close();return e}
    if e=tmp.Close();e!=nil {return e}
    return os.Rename(tmp.Name(),filepath.Join(dir,sourceLongWindowResultName))
}
