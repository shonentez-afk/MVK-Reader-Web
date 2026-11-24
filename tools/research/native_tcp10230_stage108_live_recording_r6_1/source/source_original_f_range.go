package main

// Source-backed independent original receive factor, never the
// Native reconstructed BIN gain.
//
// PRIVATE triple original proof (never uploaded):
//  Projects.7z: _Unit115.pas 007D0A61 and 007D2398..007D23E1;
//               _Unit125.pas 0080827F..0080828C, cl=1;
//               _Unit128.pas 00846C7A..00846CB2 creates live ADC;
//               _Unit125 00806964, 008085FA..00808682 assigns LIVE range/units.
//               _Unit128 0084655E separately assigns archive factor.
//  mvk_idr(1).sqlite: GetChannelStorage/ProcessBufferChunk call graph;
//  mvkview.idp: TMvkChannelStorage.FRange:Single +4,
//               PAdcFloatData +34, FRxPos +20.
//
// On Win32 x87, flds(single); fmuls(single); fstps(single) computes a
// 48-bit exact finite product (24+24 significand) before Float32
// round-to-nearest-even. Go float64 product is exact for two finite
// binary32 operands, so round back to float32 has the same normal-range
// result (no unjustified float32 intermediate or gain/ratio estimate).
// Subnormal/Inf/NaN and non-default x87 CW parity require separate proof.
import (
    "encoding/binary"
    "errors"
    "math"
)

func sourceApplyOriginalFRange(payload []byte, scale float32)([]byte,error){
    if len(payload)%4!=0 || !finiteF32(scale) || scale<=0 {
        return nil,errors.New("source FRange: invalid Float32 bytes/range")
    }
    if scale==1.0 {
        // In live Task2 the source constructor initializes FRange=1.
        // Avoid another Float32 conversion (especially NaN payload
        // canonicalization). These ARE the original RX payload bits.
        return payload,nil
    }
    out:=make([]byte,len(payload))
    for j:=0;j<len(payload);j+=4 {
        bits:=binary.LittleEndian.Uint32(payload[j:j+4])
        value:=math.Float32frombits(bits)
        result:=float32(float64(value)*float64(scale))
        binary.LittleEndian.PutUint32(out[j:j+4],math.Float32bits(result))
    }
    return out,nil
}


// Source Stage0->1 latch is inside the PARAM descriptor loop.
// A zero config Single maps to 1; missing input is explicitly provisional.
// Negative/nonfinite range cannot authorize compatible calculation.
type sourceOriginalRangeState struct {
    Single float32 `json:"single"`
    Origin string `json:"origin"`
    RegisterWord int `json:"register_word"`
    RegisterRawLE string `json:"register_raw_le"`
    UnitsRawLE string `json:"units_raw_le"`
    LatchedFrame uint64 `json:"latched_frame"`
    SocketAttempt uint64 `json:"socket_attempt"`
    Usable bool `json:"usable"`
}
func sourceIsLiveADC(domain string)bool {
    return domain==sourceStorageOriginalLiveADC||domain==sourceStorageOriginalConfigADC
}
func (c *sourceOriginalChannelRing) liveRange() (float32,string) {
    if c.rangeState==nil {return 1,sourceStorageOriginalLiveADC}
    if !c.rangeState.Usable{return 1,sourceStorageUnscaledADC}
    if c.rangeState.Single==1{return 1,sourceStorageOriginalLiveADC}
    return c.rangeState.Single,sourceStorageOriginalConfigADC
}
func (m *Monitor) latchSourceOriginalRanges(){
    r:=m.sourceOriginalStorage
    if r==nil||m.sourceOriginalRXGate==nil{return}
    attempt:=uint64(1)
    if m.summary.SourceTCPConnectionCount>0 {
        attempt=m.summary.SourceTCPConnectionCount
    } else if m.sourceOriginalTask2Stage!=nil&&m.sourceOriginalTask2Stage.attempts>0 {
        attempt=m.sourceOriginalTask2Stage.attempts
    }
    if r.rangeLatchAttempt==attempt{return}
    r.rangeLatchAttempt=attempt
    for ch:=0;ch<8;ch++ {
        s:=m.sourceOriginalADCConfig.rangeState(ch)
        s.LatchedFrame=m.summary.TotalFrames;s.SocketAttempt=attempt
        c:=&r.channels[ch];c.rangeState=&s
        // Retain pre-latch samples exactly as stored, without rescaling.
        if sourceIsLiveADC(c.domain) {
            _,domain:=c.liveRange()
            c.domain=domain
            if !s.Usable {c.validPos=c.rxPos}
        }
    }
}
