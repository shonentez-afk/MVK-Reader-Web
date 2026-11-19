package main

// Original _Unit125:008066F0, source-ordered WriteValues ROW at EXACT
// accepted PARAM 0x3100. This does not attempt proprietary vendor
// GetValueText. Every selected cell is linked to the original register
// address when proven from _Unit125:00804DEC/00805040/008053B8, or is
// explicitly UNMAPPED (never filled using unrelated band or ADC data).
//
// The two TACH source cells at +0xFE may contain an older snapshot.
// They are admitted ONLY when both words are in the CURRENT PARAM.
// No second TCP, no device TX, no recovery of unsupported private text.

import (
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "fmt"
    "strings"
    "time"
)

const sourceValuesRawLayoutSchema="MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V1"
const sourceValuesMaxRowBytes=65536

type sourceSelectedRawValue struct {
    Channel int `json:"channel"`
    Group string `json:"source_list_group"`
    CellIndex int `json:"source_cell_index"`
    WordAddr *int `json:"source_word_address,omitempty"`
    RawLE *string `json:"raw_dword_le_hex"`
    ValueKind string `json:"type_candidate"`
    SourceWordValid bool `json:"source_two_words_valid"`
}
type sourceValuesRawTick struct {
    Schema string `json:"schema"`
    LocalTime string `json:"local_source_capture_hh_nn_ss_zzz"`
    OrderedFields []sourceSelectedRawValue `json:"original_selected_cell_order"`
    RawRowSHA256 string `json:"source_raw_layout_line_sha256"`
    ValidDWORDs int `json:"source_known_full_register_dwords"`
    UnknownSelected int `json:"unknown_or_unmapped_selected_cells"`
    OriginalGetValueTextParityVerified bool `json:"original_get_value_text_parity_verified"`
    OriginalLocalTimeParityVerified bool `json:"original_delphi_local_time_parity_verified"`
    OriginalCSVByteParityVerified bool `json:"original_delphi_values_csv_byte_parity_verified"`
}

func sourceRawWordsIncludedInCurrentParam(blocks []RegBlock, addr int) bool {
    // Do not grant original "ResultTachoImpulse" +FE freshness based
    // on a previous packet's full register image. Both words must
    // actually arrive in THIS accepted PARAM.
    first,second:=false,false
    for _,b:=range blocks{
        start:=int(b.Addr)
        end:=start+int(b.Words)
        if addr>=start && addr<end {first=true}
        if addr+1>=start && addr+1<end {second=true}
    }
    return first&&second
}

func(m *Monitor) sourceValuesOrderedRawTick(
    w *sourceLiveValuesWindow, blocks []RegBlock, at time.Time,
)(sourceValuesRawTick,[]byte,error){
    if w==nil || m==nil || at.IsZero(){
        return sourceValuesRawTick{},nil,errors.New("source WriteValues tick requires live time and selected window")
    }
    tick:=sourceValuesRawTick{
        Schema:sourceValuesRawLayoutSchema,
        LocalTime:at.Format("15:04:05.000"),
        OrderedFields:make([]sourceSelectedRawValue,0,892),
    }
    var line strings.Builder
    line.WriteString(tick.LocalTime)
    appendField:=func(channel int,group string,index int,addr int,kind string,fresh bool){
        field:=sourceSelectedRawValue{
            Channel:channel,Group:group,CellIndex:index,
            ValueKind:kind,
        }
        var raw *string
        if addr>=0{
            location:=addr
            field.WordAddr=&location
            if fresh{raw=m.sourceLiveRawDWORD(addr)}
        }
        field.RawLE=raw
        field.SourceWordValid=raw!=nil
        if raw==nil{
            tick.UnknownSelected++
            line.WriteString("|UNKNOWN")
        }else{
            tick.ValidDWORDs++
            line.WriteString("|RAW_")
            line.WriteString(kind)
            line.WriteByte(':')
            line.WriteString(*raw)
        }
        tick.OrderedFields=append(tick.OrderedFields,field)
    }
    for ch:=0;ch<8;ch++ {
        if !w.Channels[ch]{continue}
        base:=0x2000+ch*0x200
        // 00806768..0080680B: EXACT original three group order,
        // then selected mask bits by index. Original SpecCellList
        // address is NOT proven: never mislabel 43 BAND cells as SPEC.
        for i:=0;i<43;i++{
            if w.Spec[i]{appendField(ch+1,"SPEC",i,-1,"UNMAPPED",false)}
        }
        for i:=0;i<24;i++{
            if w.Values[i]{
                appendField(ch+1,"RESULT",i,base+0x60+2*i,
                    "F32_CANDIDATE",true)
            }
        }
        for i:=0;i<43;i++{
            if w.Values[24+i]{
                appendField(ch+1,"BAND",i,base+2+2*i,
                    "F32_CANDIDATE",true)
            }
        }
    }
    for tach:=0;tach<2;tach++ {
        if !w.Channels[8+tach]{continue}
        base:=0x3000+tach*0x100
        for i,offset:=range [...]int{0,2,4,6,8,0xFE} {
            if !w.Values[67+i]{continue}
            addr:=base+offset
            fresh:=i<5 || sourceRawWordsIncludedInCurrentParam(blocks,addr)
            kind:="U32_CANDIDATE"
            if i<2 {kind="F32_CANDIDATE"}
            appendField(9+tach,"TACH",i,addr,kind,fresh)
        }
    }
    line.WriteString("\r\n")
    raw:=[]byte(line.String())
    if len(raw)>sourceValuesMaxRowBytes {
        return sourceValuesRawTick{},nil,errors.New("source WriteValues selected row too large")
    }
    h:=sha256.Sum256(raw)
    tick.RawRowSHA256=hex.EncodeToString(h[:])
    // Source original calls Now(), Unicode->ANSI, then its private
    // TFileStream, which may round/format differently. This is an
    // explicitly non-Delphi, source-indexed, ASCII diagnostic line.
    return tick,raw,nil
}
