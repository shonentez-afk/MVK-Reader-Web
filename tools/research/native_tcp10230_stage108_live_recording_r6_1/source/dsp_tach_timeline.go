package main

// Stage111Z.28A: lossless VALUES-tick snapshot of existing DSP and two TACH
// register banks. These values were ALREADY decoded from the original RAW
// by addTachAndDSP; this is only provenance metadata inside the existing
// SHA256-audited TIMELINE.json, not a new network command or recalculation.
// Float words are deliberately NOT called RPM/Hz until original field
// semantics are verified against the original MVKView.
import (
    "fmt"
)

const dspTachTimelineSchema = "MVK_NATIVE_R6_DSP_TACH_TICK_V1"

type OriginalTachRegisterWords struct {
    TACH int `json:"tach"`
    RegisterBase string `json:"register_base_word"`
    Float32Words [2]float64 `json:"raw_float32_words_0_2"`
    Uint32Words [3]uint32 `json:"raw_uint32_words_4_6_8"`
}

func originalTickTimeline(s snapshot, i int) map[string]interface{} {
    channels:=make([]OriginalTachRegisterWords,2)
    for ch:=0;ch<2;ch++ {
        channels[ch]=OriginalTachRegisterWords{
            TACH:ch+1,RegisterBase:fmt.Sprintf("0x%04X",0x3000+0x100*ch),
            Float32Words:s.TachF[ch],Uint32Words:s.TachU[ch],
        }
    }
    return map[string]interface{}{
        "update":i+1,
        "aux_frame":s.AuxFrame,
        "tick_frame":s.TickFrame,
        "tick_received_utc":s.TickTimeUTC,
        "dsp_tach_schema":dspTachTimelineSchema,
        "dsp_status_register_word":"0x1020",
        "dsp_status_raw":s.DSPStatus,
        "dsp_status_hex":fmt.Sprintf("0x%08X",s.DSPStatus),
        "tach_channels":channels,
        "source":"READ_ONLY_REGISTER_IMAGE_AT_VALUES_76B_TICK",
        "time_kind":"HOST_RECEIVE_CLOCK_NOT_DSP_SYNCHRONIZED",
        "tach_units_and_rpm_verified":false,
    }
}
