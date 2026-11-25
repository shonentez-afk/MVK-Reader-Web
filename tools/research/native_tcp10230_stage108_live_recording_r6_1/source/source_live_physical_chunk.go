package main

import (
    "encoding/binary"
    "math"
)

// Constructor FRange=1 is source-known; an unobserved post-latch range is not.
func sourcePhysicalRangeKnown(state *sourceOriginalRangeState) bool {
    return state==nil || (state.Usable &&
        (state.Origin=="REGISTER_FLOAT32" || state.Origin=="REGISTER_ZERO_FALLBACK_ONE"))
}
func sourcePhysicalFinite(payload []byte) bool {
    if len(payload)%4!=0 {return false}
    for j:=0;j<len(payload);j+=4 {
        if !finiteF32(math.Float32frombits(binary.LittleEndian.Uint32(payload[j:j+4]))) {return false}
    }
    return true
}
