package main

// One read-only, bounded, on-demand local selection of the
// original 2^21 Float32 source ring for BOTH GetSignal HTag and
// GetSpectrum's exact bSpecLines. Both share a single local IPC file. This is an IPC file handled by the SAME
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
    "reflect"
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
    SampleWidth int `json:"sample_width_bytes,omitempty"`
    EnvelopeCode int `json:"envelope_code,omitempty"`
    OriginalBSpecLines uint32 `json:"original_bspec_lines,omitempty"`
    OriginalHTag int `json:"original_h_tag,omitempty"`
    SourceRangeState *sourceOriginalRangeState `json:"source_range_state,omitempty"`
    SourceEpoch *sourceDisplayEpoch `json:"source_epoch,omitempty"`
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
    SampleWidth int `json:"sample_width_bytes,omitempty"`
    DeviceEndWordIndex *uint32 `json:"device_end_word_index,omitempty"`
    InputDomain string `json:"input_domain"`
    CalibrationAlreadyApplied bool `json:"calibration_already_applied"`
    Provisional bool `json:"provisional_not_audited"`
    RawBytes uint64 `json:"raw_bytes"`
    FramesDecoded uint64 `json:"frames_decoded"`
    SHA256 string `json:"sha256"`
    EnvelopeCode int `json:"envelope_code,omitempty"`
    OriginalBSpecLines uint32 `json:"original_bspec_lines,omitempty"`
    OriginalHTag int `json:"original_h_tag,omitempty"`
    SourceRangeState *sourceOriginalRangeState `json:"source_range_state,omitempty"`
    SourceEpoch *sourceDisplayEpoch `json:"source_epoch,omitempty"`
}

func sourceLongWindowLength(rate uint32,tag int) (uint32,error) {
    if !acceptedRates[rate] || tag<0 || tag>=len(sourceLongWindowHScaleMS) {
        return 0,errors.New("invalid source bAdcHScale/rate")
    }
    n:=uint64(rate)*uint64(sourceLongWindowHScaleMS[tag])/1000
    // Short H scales MUST come from the original rate/Freeze-gated ring
    // too: ordinary Native preview can include frozen/wrong-Fs samples.
    // Fractional one-millisecond windows at Fs=512 yield zero samples
    // and cannot be represented as real GetSignal data.
    if n==0 || n>sourceOriginalStorageSamples {
        return 0,errors.New("original source H-scale exceeds 2M ring or has no samples")
    }
    return uint32(n),nil
}

// Original _Unit128.pas bSpecLines passes one of the source menu lengths
// to TMvkChannelStorage.GetSpectrum at 00848200; source _Unit115:007D1404
// hard-limits its FFT input to 0x40000 samples. HTag=-1 is a local-only
// IPC discriminator; Delphi never receives this value or any command.
func sourceFFTWindowLength(n uint32)(uint32,error){
    switch n {
    case 1024,4096,8192,16384,32768,65536,131072,262144:
        return n,nil
    default:
        return 0,errors.New("unsupported original bSpecLines FFT length")
    }
}

// PRIVATE _Unit115.pas:007D1158 source GetAdjustedEnvelopeLength.
// The original user-facing bSpecLines N is PRE-FIR; filter stages mutate
// Params.Count before 007D1FE8 FFT. Only source-controlled arithmetic is
// embedded, NOT proprietary FIR coefficients or original Pascal/IDP.
var sourceFIREnvelopeRates=[32]uint32{
    1,65536,65536,65536,65536,32768,32768,32768,
    16384,16384,16384,8192,8192,8192,4096,4096,
    4096,2048,2048,2048,65536,32768,16384,8192,
    4096,2048,65536,32768,16384,8192,4096,2048,
}
var sourceFIREnvelopeStages=[32]int{
    0,1,2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,
    5,5,5,5,5,5,6,6,6,6,6,6,
}
var sourceFIRTaps=[11]uint32{0,97,129,161,193,51,49,45,89,177,353}
var sourceFIRDecim=[11]uint32{0,4,4,4,8,2,1,2,4,8,16}

// Original 007D1158/007D1C48/007D1E70 source arithmetic shared by
// spectrum and GetSignal. Time-domain post-FIR N is NOT a radix-2 FFT N.
func sourceFIRWindowCounts(rate uint32,code int,selected uint32)(uint32,uint32,uint32,error){
    if !acceptedRates[rate] || code<1 || code>31 || selected==0 {
        return 0,0,0,errors.New("source FIR invalid ADC rate, code or window")
    }
    target:=sourceFIREnvelopeRates[code]
    if target==0 || rate<target || rate%target!=0 {
        return 0,0,0,errors.New("source FIR target rate not supported by ADC")
    }
    ratio:=rate/target
    // IDR 007D1178/007D1C62 immediate operands are hexadecimal.
    // q=0x10 is 16; q=0x20 is 32, then 64,128,256.
    var pre,second int
    switch ratio {
    case 1:
    case 2:pre=7
    case 4:pre=8
    case 8:pre=9
    case 16:pre=10
    case 32:pre=7;second=10
    case 64:pre=8;second=10
    case 128:pre=9;second=10
    case 256:pre=10;second=10
    default:return 0,0,0,errors.New("original source FIR Invalid sample rate")
    }
    var prefix uint32
    if second!=0 {prefix=sourceFIRTaps[second]}
    if pre!=0 {prefix=prefix*sourceFIRDecim[pre]+sourceFIRTaps[pre]}
    stage:=sourceFIREnvelopeStages[code]
    count:=uint64(selected)+uint64(prefix)+uint64(sourceFIRTaps[stage])*uint64(ratio)
    if count==0 || count>sourceOriginalStorageSamples {
        return 0,0,0,errors.New("source FIR history exceeds original 2M ring")
    }
    n:=uint32(count)
    for _,decimator:=range []int{pre,second} {
        if decimator==0 {continue}
        if n<sourceFIRTaps[decimator]+sourceFIRDecim[decimator] {
            return 0,0,0,errors.New("source FIR pre-decimator lacks history")
        }
        n=(n-sourceFIRTaps[decimator])/sourceFIRDecim[decimator]
    }
    if n<sourceFIRTaps[stage]+sourceFIRDecim[stage] {
        return 0,0,0,errors.New("source FIR I/Q lacks history")
    }
    n=(n-sourceFIRTaps[stage])/sourceFIRDecim[stage]
    fsout:=target/sourceFIRDecim[stage]
    if n==0 || fsout==0 {
        return 0,0,0,errors.New("source FIR produced empty GetSignal")
    }
    return uint32(count),n,fsout,nil
}

func sourceFIREnvelopeWindowLength(rate uint32,code int,selected uint32)(uint32,error){
    if _,err:=sourceFFTWindowLength(selected);err!=nil{return 0,err}
    count,n,fsout,err:=sourceFIRWindowCounts(rate,code,selected)
    if err!=nil{return 0,err}
    if n<2 || (n&(n-1))!=0 || n>262144 ||
       uint64(fsout)*uint64(selected)!=uint64(rate)*uint64(n){
        return 0,errors.New("source FIR Params.Count/FFT frequency grid mismatch")
    }
    return count,nil
}

// bAdcHScale HTag 0..13 -> precise original PRE-FIR GetSignal history.
// -3 is a strictly local IPC selector and NEVER a network command.
func sourceFIRGetSignalWindowLength(rate uint32,code int,hTag int)(uint32,uint32,uint32,error){
    selected,err:=sourceLongWindowLength(rate,hTag)
    if err!=nil{return 0,0,0,err}
    return sourceFIRWindowCounts(rate,code,selected)
}

func (m *Monitor) handleSourceLongWindowRequest(now time.Time) error {
    if m==nil || !m.liveProgressEnabled || m.sourceOriginalStorage==nil {
        return nil
    }
    // The source ring is not an output of LiveBinSpool: a valid
    // 2^21 original FRange1 ring remains readable without BIN export.
    if m.captureOnly || m.summary.CaptureOnly || m.summary.InvalidFrames!=0 ||
       m.sourceTCP!=nil && m.sourceTCP.Active==0 ||
       m.sourceOriginalTask2Stage!=nil && (!m.sourceOriginalTask2Stage.connected ||
          m.sourceOriginalTask2Stage.systemErrorLatched) {
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
       req.ADC<1 || req.ADC>10 {
        return errors.New("untrusted source long-window request identity")
    }
    isTach:=req.ADC>=9
    if isTach {
        if req.SampleWidth!=1 || req.SourceRangeState!=nil || req.HTag < -1 ||
           req.EnvelopeCode!=0 || req.OriginalBSpecLines!=0 || req.OriginalHTag!=0 {
            return errors.New("TACH source window requires typed Byte with no FIR")
        }
    } else if req.SampleWidth!=0 && req.SampleWidth!=4 {
        return errors.New("ADC source window requires Float32")
    }
    // A duplicate request never causes a 2M/FFT window to be
    // re-read/re-written on each 750ms status publication.
    if m.sourceLongWindowLastID==req.RequestID {return nil}
    m.sourceLongWindowLastID=req.RequestID
    // HTag>=0: original ADC time window. -1: plain bSpecLines FFT.
    // -2: original EnvelopeCode/GetAdjustedEnvelopeLength PRE-FIR window.
    // -3: original filtered time-domain GetSignal HTag + FIR history.
    // The negative selector is LOCAL IPC ONLY and never reaches MVK01.
    var n uint32
    switch req.HTag {
    case -3:
        if req.OriginalBSpecLines!=0 {
            return errors.New("filtered GetSignal cannot carry bSpecLines")
        }
        n,_,_,e=sourceFIRGetSignalWindowLength(
            req.SampleRateHz,req.EnvelopeCode,req.OriginalHTag)
    case -2:
        if req.OriginalHTag!=0{
            return errors.New("spectrum FIR cannot carry ADC HTag")
        }
        n,e=sourceFIREnvelopeWindowLength(
            req.SampleRateHz,req.EnvelopeCode,req.OriginalBSpecLines)
    case -1:
        if req.EnvelopeCode!=0 || req.OriginalBSpecLines!=0 || req.OriginalHTag!=0{
            return errors.New("plain FFT must not contain FIR metadata")
        }
        n,e=sourceFFTWindowLength(req.Samples)
    default:
        if req.EnvelopeCode!=0 || req.OriginalBSpecLines!=0 || req.OriginalHTag!=0{
            return errors.New("plain ADC HTag must not contain FIR metadata")
        }
        n,e=sourceLongWindowLength(req.SampleRateHz,req.HTag)
    }
    if e!=nil || req.Samples!=n || !acceptedRates[req.SampleRateHz] {
        return errors.New("source HTag/FFT/FIR length mismatches actual Fs")
    }
    idx:=req.ADC-1
    channel:=&m.sourceOriginalStorage.channels[idx]
    summary:=m.summary.Channels[idx]
    epoch:=m.sourceOriginalStorage.displayEpoch(idx)
    // Only the old healthy single-epoch fixture/IPC may omit new metadata.
    // A recovered window needs a proof from the currently active generation.
    epochRequired:=m.summary.SourceTCPMultiSocket || m.sourceRateTransitionDetected ||
        channel.rateChanges!=0
    if (epochRequired || req.SourceEpoch!=nil) &&
       (epoch==nil || !reflect.DeepEqual(epoch,req.SourceEpoch) ||
        m.sourceOriginalRXGate==nil) {
        return errors.New("source long window stale or unverified display epoch")
    }
    if epochRequired && m.summary.Denials!=0 {
        return errors.New("source long window refused after device denial")
    }
    if m.summary.SourceTCPMultiSocket {
        stage:=m.sourceOriginalTask2Stage
        if m.sourceTCP==nil || uint64(m.sourceTCP.Active)!=epoch.SocketAttempt ||
           epoch.SocketAttempt!=m.summary.SourceTCPConnectionCount ||
           stage==nil || stage.attempts!=epoch.SocketAttempt || stage.stage!=1 ||
           stage.paramsAfterConnect==0 {
            return errors.New("source long window lacks a fresh active socket with validated PARAM")
        }
    }
    // Original FreezeUpdate/MvkSampleRate deliberately skip TCP frames.
    // After thaw, source FRxPos is smaller than forensic Native.Samples.
    // It must equal the count admitted to ORIGINAL ring by the exact
    // rate/freeze gate, not the count of every packet read from TCP.
    wireFactor:=uint64(1)
    if isTach {wireFactor=4}
    if summary.Samples > ^uint64(0)/wireFactor {return errors.New("source wire count overflow")}
    observedElements:=summary.Samples*wireFactor
    allowedCount:=observedElements
    if m.sourceOriginalRXGate!=nil {
        g:=m.sourceOriginalRXGate
        allowedCount=g.allowed[idx]
        if (g.frozen || g.rate!=req.SampleRateHz ||
                g.allowed[idx]+g.skippedRate[idx]+g.skippedFrozen[idx]!=
                    observedElements) {
            return errors.New("source original gate not ready for long GetSignal")
        }
    }
    validDomain:=sourceIsLiveADC(channel.domain)
    if isTach {validDomain=channel.domain==sourceStorageTachBytes}
    if !channel.seen || !validDomain ||
       channel.sampleRate!=req.SampleRateHz ||
       channel.rejectedNonfinite!=0 ||
       !isTach && summary.NonFiniteSamples!=0 ||
       channel.rxPos!=allowedCount {
        // Historical all-wire Fs/sequence counters are not the scoped
        // window bounds. ADC nonfinite counters nevertheless fail closed.
        // Ring.validPos and ring.window also reject superseded history.

        return errors.New("source long window not confirmed original live typed storage")
    }
    if !reflect.DeepEqual(req.SourceRangeState,channel.rangeState) {
        return errors.New("source long window stale FRange epoch")
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
       lag%wireFactor!=0 || req.CaptureEnd%wireFactor!=0 ||
       channel.nextDeviceIndex-uint32(lag/wireFactor)!=req.DeviceEnd {
        return errors.New("source long window stale or device index mismatch")
    }
    first:=req.CaptureEnd-uint64(req.Samples)
    if first<channel.displayStart {
        return errors.New("source long window crosses a display epoch boundary")
    }
    data,e:=m.sourceOriginalStorage.window(idx,first,uint64(req.Samples))
    if e!=nil{return e}
    if !isTach && !sourcePhysicalFinite(data) {
        return errors.New("source long window contains nonfinite Float32")
    }
    sum:=sha256.Sum256(data)
    entry:=fmt.Sprintf("ADC%d.f32",req.ADC)
    // FRxPos counts bytes; header Index counts words. Separate epochs.
    endIndex:=req.DeviceEnd
    var deviceEndWord *uint32
    width:=0
    if isTach {
        entry=fmt.Sprintf("TACH%d.u8",req.ADC-8)
        endIndex=req.DeviceEnd*4
        deviceEndWord=&req.DeviceEnd
        width=1
    }
    receipt:=sourceLongWindowResult{
        Schema:sourceLongWindowResultSchema,SessionID:req.SessionID,
        RequestID:req.RequestID,Phase:"RECORDING",
        UpdatedUTC:now.UTC().Format(time.RFC3339Nano),
        ADC:req.ADC,HTag:req.HTag,Entry:entry,
        Samples:req.Samples,CaptureEnd:req.CaptureEnd,
        SampleRateHz:req.SampleRateHz,
        FirstIndex:endIndex-req.Samples,NextIndex:endIndex,
        SampleWidth:width,DeviceEndWordIndex:deviceEndWord,
        InputDomain:channel.domain,SourceRangeState:channel.rangeState,
        SourceEpoch:req.SourceEpoch,
        CalibrationAlreadyApplied:!isTach,Provisional:true,
        RawBytes:m.summary.RawBytes,FramesDecoded:m.summary.TotalFrames,
        SHA256:hex.EncodeToString(sum[:]),
        EnvelopeCode:req.EnvelopeCode,
        OriginalBSpecLines:req.OriginalBSpecLines,
        OriginalHTag:req.OriginalHTag,
    }
    return writeSourceLongWindowAtomic(m.dir,entry,data,receipt)
}

func writeSourceLongWindowAtomic(dir,entry string,data []byte,
                                 receipt sourceLongWindowResult) error {
    // One selected original channel at a time, exact Float32 or Byte.
    // Never change the forensic RAW/BIN spool.
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
