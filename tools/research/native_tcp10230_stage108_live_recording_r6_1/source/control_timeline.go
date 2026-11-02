package main

// Stage111Z.28B2A: Optional original control/alarm evidence, extracted ONLY
// from already received register update frames in the existing Native R6
// offline RAW replay. NO new socket, packet, configuration write or decoder.
// Initial full 0x4000-word snapshot NEVER counts as "current" alarm status.
// For each VALUES tick, only a full 8-word status record updated AFTER the
// previous VALUES tick is admissible. Physical zone/event meanings and live
// config parameter identity are intentionally NOT inferred.
import (
    "fmt"
)

const controlTickSchema = "MVK_NATIVE_R6_CONTROL_TICK_RAW_EVIDENCE_V1"
const controlTickSource = "POST_INITIAL_FULL_REGISTER_UPDATE_BEFORE_VALUES_TICK"

type ControlRawSlot struct {
    ADC int `json:"adc"`
    Slot int `json:"slot"`
    StatusBaseWord string `json:"status_base_word"`
    SourceFrame uint64 `json:"source_frame_index"`
    RawValueFloat32 float64 `json:"raw_value_float32"`
    RawStatusU32 uint32 `json:"raw_status_u32"`
    RawStatusHex string `json:"raw_status_hex"`
    RawLastTransitionFloat32 float64 `json:"raw_last_transition_float32"`
    RawReservedU32 uint32 `json:"raw_reserved_u32"`
}

type ControlTickAudit struct {
    Schema string `json:"schema"`
    Source string `json:"source"`
    StatusFrameFreshForTick bool `json:"status_frame_fresh_for_tick"`
    ZoneAndAlertTextVerified bool `json:"zone_and_alert_text_verified"`
    ConfigParameterSelectionVerified bool `json:"config_parameter_selection_verified"`
    NoInitialSnapshotAsLiveStatus bool `json:"no_initial_snapshot_as_live_status"`
    RawSlots []ControlRawSlot `json:"raw_slots"`
}

type controlUpdateTracker struct {
    lastFrame [8][8]uint64
    prevValuesFrame uint64
}

// Only dedicated post-initial source blocks; a full register snapshot is
// baseline data, not proof of a current alarm transition.
func (t *controlUpdateTracker) observe(blocks []RegBlock, frame uint64, postInitial bool) {
    if !postInitial || frame == 0 { return }
    for _,b := range blocks {
        if b.Words >= 0x4000 { continue }
        beg,end:=uint32(b.Addr),uint32(b.Addr)+uint32(b.Words)
        for adc:=0;adc<8;adc++ {
            base:=uint32(0x2000+0x200*adc)
            for slot:=0;slot<8;slot++ {
                at:=base+0x130+uint32(8*slot)
                // Require a complete original 8-word (16-byte) control
                // record in one observed register block, not fragment joins.
                if beg <= at && end >= at+8 {
                    t.lastFrame[adc][slot]=frame
                }
            }
        }
    }
}

func (t *controlUpdateTracker) atTick(image *RegisterImage, frame uint64) ControlTickAudit {
    out:=ControlTickAudit{
        Schema:controlTickSchema,Source:controlTickSource,
        StatusFrameFreshForTick:true,ZoneAndAlertTextVerified:false,
        ConfigParameterSelectionVerified:false,NoInitialSnapshotAsLiveStatus:true,
        RawSlots:make([]ControlRawSlot,0),
    }
    for adc:=0;adc<8;adc++ {
        base:=0x2000+0x200*adc
        for slot:=0;slot<8;slot++ {
            source:=t.lastFrame[adc][slot]
            if source==0 || source<=t.prevValuesFrame || source>=frame { continue }
            at:=base+0x130+8*slot
            value,e1:=readF32(image,at)
            state,e2:=image.Uint32(at+2)
            transition,e3:=readF32(image,at+4)
            reserved,e4:=image.Uint32(at+6)
            // Nonfinite or incomplete ALARM metadata cannot spoil the
            // already accepted 8 ADC RAW/BIN export: omit optional evidence.
            if e1!=nil || e2!=nil || e3!=nil || e4!=nil { continue }
            out.RawSlots=append(out.RawSlots,ControlRawSlot{
                ADC:adc+1,Slot:slot+1,
                StatusBaseWord:fmt.Sprintf("0x%04X",at),
                SourceFrame:source,RawValueFloat32:value,
                RawStatusU32:state,
                RawStatusHex:fmt.Sprintf("0x%08X",state),
                RawLastTransitionFloat32:transition,
                RawReservedU32:reserved,
            })
        }
    }
    t.prevValuesFrame=frame
    return out
}
