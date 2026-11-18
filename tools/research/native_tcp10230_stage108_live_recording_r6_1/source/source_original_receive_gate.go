package main

// Stage111Z31FL: a byte-for-byte source-backed IN-MEMORY receive rule,
// distinct from the Native forensic RAW/BIN capture and device SetRate.
//
// Triple private provenance: mvkview.idp, Projects.7z _Unit125.pas,
// _Unit128.pas and mvk_idr(1).sqlite. Source identifiers:
//   0080618E MvkSampleRate := 777; 00806198 FreezeUpdate := false
//   00846DDF..00846DF7 mRate1Click(Items[0]) -> 65536 -> SetRate
//   00809400 SetRate updates MvkSampleRate before queuing any command
//   0080822F..0080828C: read ALL TCP bytes, but ProcessBufferChunk ONLY
//       if rate == MvkSampleRate && !FreezeUpdate.
// Source semantics do NOT imply the physical SetRate was transmitted.
import (
    "fmt"
)

const (
    sourceOriginalThreadInitialRate uint32=777
    sourceOriginalMenuInitialRate uint32=65536
    sourceOriginalReceiveSchema="MVK_SOURCE_TMVKTHREAD_RECEIVE_GATE_V1"
)

type sourceOriginalReceiveGate struct {
    rate uint32
    frozen bool
    selectionChanges uint64
    freezeChanges uint64
    allowed [10]uint64
    skippedRate [10]uint64
    skippedFrozen [10]uint64
    skippedRateFrames [10]uint64
    skippedFrozenFrames [10]uint64
    lastSkippedNativeSample [10]uint64
}

type sourceOriginalReceiveGateChannel struct {
    Channel int `json:"channel"`
    StoredGateElements uint64 `json:"accepted_elements"`
    RateSkippedElements uint64 `json:"rate_skipped_elements"`
    FrozenSkippedElements uint64 `json:"freeze_skipped_elements"`
    RateSkippedFrames uint64 `json:"rate_skipped_frames"`
    FrozenSkippedFrames uint64 `json:"freeze_skipped_frames"`
    LastSkippedNativeSample uint64 `json:"last_skipped_native_samples"`
}
type sourceOriginalReceiveGateReceipt struct {
    Schema string `json:"schema"`
    InitialThreadRate uint32 `json:"initial_thread_rate_hz"`
    SelectedRate uint32 `json:"selected_rate_hz"`
    OriginalMenuRate uint32 `json:"source_initial_menu_rate_hz"`
    SourceMenuSelectionDone bool `json:"source_menu_selected"`
    PhysicalSetRateNotInferred bool `json:"physical_setrate_not_inferred"`
    Frozen bool `json:"freeze_update"`
    SelectionChanges uint64 `json:"selection_changes"`
    FreezeChanges uint64 `json:"freeze_changes"`
    Channels []sourceOriginalReceiveGateChannel `json:"channels"`
    OriginalDelphiParityVerified bool `json:"original_delphi_parity_verified"`
}

func newSourceOriginalReceiveGate() *sourceOriginalReceiveGate {
    // Reflect the ACTUAL _Unit128 Mode2 constructor/menu order,
    // without silently sending a single hardware byte.
    g:=&sourceOriginalReceiveGate{rate:sourceOriginalThreadInitialRate}
    g.selectRate(sourceOriginalMenuInitialRate)
    return g
}
func(g *sourceOriginalReceiveGate) selectRate(rate uint32)error {
    if g==nil || !acceptedRates[rate] {
        return fmt.Errorf("original TMVKThread invalid sample rate %d",rate)
    }
    if g.rate!=rate {
        g.rate=rate;g.selectionChanges++
    }
    return nil
}
func(g *sourceOriginalReceiveGate) setFreeze(frozen bool) {
    if g==nil {return}
    if g.frozen!=frozen {g.frozen=frozen;g.freezeChanges++}
}
func(g *sourceOriginalReceiveGate) allowedFrame(h SampleHeader,observed uint64) bool {
    if g==nil{return true} // offline/forensic replay has no live thread
    if h.Channel<0 || h.Channel>=10 || h.Samples<0 {return false}
    amount:=uint64(h.Samples)
    if h.Channel>=8 {amount*=4} // BYTE storage type 2
    if g.frozen {
        g.skippedFrozen[h.Channel]+=amount
        g.skippedFrozenFrames[h.Channel]++
        g.lastSkippedNativeSample[h.Channel]=observed
        return false
    }
    if h.Rate!=g.rate {
        g.skippedRate[h.Channel]+=amount
        g.skippedRateFrames[h.Channel]++
        g.lastSkippedNativeSample[h.Channel]=observed
        return false
    }
    g.allowed[h.Channel]+=amount
    return true
}
func(g *sourceOriginalReceiveGate) receipt()sourceOriginalReceiveGateReceipt {
    out:=sourceOriginalReceiveGateReceipt{
        Schema:sourceOriginalReceiveSchema,
        InitialThreadRate:sourceOriginalThreadInitialRate,
        OriginalMenuRate:sourceOriginalMenuInitialRate,
        SelectedRate:g.rate,SourceMenuSelectionDone:true,
        PhysicalSetRateNotInferred:true,
        Frozen:g.frozen,
        SelectionChanges:g.selectionChanges,
        FreezeChanges:g.freezeChanges,
        OriginalDelphiParityVerified:false,
        Channels:make([]sourceOriginalReceiveGateChannel,0,10),
    }
    for i:=0;i<10;i++ {
        out.Channels=append(out.Channels,sourceOriginalReceiveGateChannel{
            Channel:i+1,StoredGateElements:g.allowed[i],
            RateSkippedElements:g.skippedRate[i],
            FrozenSkippedElements:g.skippedFrozen[i],
            RateSkippedFrames:g.skippedRateFrames[i],
            FrozenSkippedFrames:g.skippedFrozenFrames[i],
            LastSkippedNativeSample:g.lastSkippedNativeSample[i],
        })
    }
    return out
}
