package main

// Source-backed independent original receive factor, never the
// Native reconstructed BIN gain.
//
// PRIVATE triple original proof (never uploaded):
//  Projects.7z: _Unit115.pas 007D0A61 and 007D2398..007D23E1;
//               _Unit125.pas 0080827F..0080828C, cl=1;
//               _Unit128.pas 00846C7A..00846CB2 creates live ADC;
//                            archive-only 0084655E assigns a V/S factor.
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
        // The constructor or a zero-fallback descriptor may give FRange=1.
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
