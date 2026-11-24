package main

// Source _Unit128:008443CF..0084441A proves the original list owners:
// 1064=Spec43 via _Unit125:00805040 (0x2002+2*i)
// 1044=Result6 via _Unit125:00804A30
// 10C0=Band24 via _Unit125:00804DEC, first of three band types
// 10AC=TACH6 via _Unit125:008053B8.
//
// _Unit128:0084E9BA..0084EA88 copies 43 SPEC, 6 RESULT, 24 BAND,
// 6 TACH flags; original cbFileValues has THIRTY-SIX, not 73.
// The compatible archive UI currently retains 73 historical flags;
// bits [36..72] are explicitly counted but never treated as original
// WriteValues fields, pending the LIVE checkbox UI migration.
//
// The original byte stream and PARAM 0x3100 JSONL event remain unchanged.
// This local RAW-order line is NOT a Delphi GetValueText/ANSI CSV oracle.
import (
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "strings"
    "time"
)

const sourceValuesRawLayoutSchema="MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V1"
const sourceValuesLatchLayoutSchema="MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V2_TACH_LATCH"
const sourceValuesMaxRowBytes=65536

type sourceSelectedRawValue struct {
    Channel int `json:"channel"`
    Group string `json:"source_list_group"`
    CellIndex int `json:"source_cell_index"`
    WordAddr *int `json:"source_word_address,omitempty"`
    RawLE *string `json:"raw_dword_le_hex"`
    ValueKind string `json:"type_candidate"`
    SourceWordValid bool `json:"source_two_words_valid"`
    SourceCellType int `json:"source_cell_type"`
    AdvancedSelectedID *uint32 `json:"source_advanced_selected_id,omitempty"`
}
type sourceValuesRawTick struct {
    Schema string `json:"schema"`
    LocalTime string `json:"local_source_capture_hh_nn_ss_zzz"`
    OrderedFields []sourceSelectedRawValue `json:"original_selected_cell_order"`
    RawRowSHA256 string `json:"source_raw_layout_line_sha256"`
    TextCandidateRowSHA256 string `json:"source_text_candidate_line_sha256,omitempty"`
    TextCandidateFormatterVersion string `json:"source_text_candidate_formatter_version,omitempty"`
    RUProfileCandidateRowSHA256 string `json:"source_ru_profile_candidate_line_sha256,omitempty"`
    RUProfileCandidateFormatterVersion string `json:"source_ru_profile_candidate_formatter_version,omitempty"`
    ValidDWORDs int `json:"source_known_full_register_dwords"`
    UnknownSelected int `json:"unknown_or_unmapped_selected_cells"`
    ExtraLegacyFlagsIgnored int `json:"non_original_legacy_73_flag_bits_ignored"`
    OriginalGetValueTextParityVerified bool `json:"original_get_value_text_parity_verified"`
    OriginalLocalTimeParityVerified bool `json:"original_delphi_local_time_parity_verified"`
    OriginalCSVByteParityVerified bool `json:"original_delphi_values_csv_byte_parity_verified"`
}
func sourceRawWordsIncludedInCurrentParam(blocks []RegBlock, addr int) bool {
    first,second:=false,false
    for _,b:=range blocks{
        start:=int(b.Addr)
        end:=start+int(b.Words)
        if addr>=start && addr<end {first=true}
        if addr+1>=start && addr+1<end {second=true}
    }
    return first&&second
}
func sourceResultAdcSixAddress(base,index int) (int,string) {
    // 00804A82..00804BA4 adds exactly 6 GetValueText slots:
    // ResultOverload (bits0..0), ResultBuffers (bits3..6),
    // ResultSensorState (bits2..11), all from 0x120;
    // AlarmBandCell1 (0x00), AlarmBandCell48 (0x5E),
    // AlarmBandCell47 (0x5C).
    switch index {
    case 0,1,2:return base+0x120,"U32_ADVANCED_UNFORMATTED"
    case 3:return base+0x00,"F32_CANDIDATE"
    case 4:return base+0x5E,"F32_CANDIDATE"
    case 5:return base+0x5C,"F32_CANDIDATE"
    }
    return -1,"UNMAPPED"
}

func(m *Monitor) sourceValuesOrderedRawTick(
    w *sourceLiveValuesWindow, blocks []RegBlock, at time.Time,
)(sourceValuesRawTick,[]byte,error){
    if m==nil{
        return sourceValuesRawTick{},nil,errors.New("source WriteValues tick requires register image")
    }
    return sourceValuesOrderedRawTickFromImage(&m.image,w,blocks,at)
}

// The live writer passes the image and accepted descriptor prefix captured
// at 0x3100. The wrapper above is retained for independent layout tests.
func sourceValuesOrderedRawTickFromImage(
    image *RegisterImage, w *sourceLiveValuesWindow, blocks []RegBlock, at time.Time, latchMode ...bool,
)(sourceValuesRawTick,[]byte,error){
    if w==nil || image==nil || at.IsZero(){
        return sourceValuesRawTick{},nil,errors.New("source WriteValues tick requires live time and selected window")
    }
    sourceLatch:=len(latchMode)==1 && latchMode[0]
    schema:=sourceValuesRawLayoutSchema
    if sourceLatch{schema=sourceValuesLatchLayoutSchema}
    tick:=sourceValuesRawTick{
        Schema:schema,
        LocalTime:at.Format("15:04:05.000"),
        OrderedFields:make([]sourceSelectedRawValue,0,8*(43+6+24)+2*6),
    }
    var line strings.Builder
    line.WriteString(tick.LocalTime)
    appendField:=func(channel int,group string,index int,addr int,kind string,fresh bool){
        field:=sourceSelectedRawValue{
            Channel:channel,Group:group,CellIndex:index,
            ValueKind:kind,
            SourceCellType:0,
        }
        var raw *string
        if addr>=0{
            location:=addr
            field.WordAddr=&location
            if fresh{raw=sourceRegisterImageRawDWORD(image,addr)}
        }
        field.RawLE=raw
        field.SourceWordValid=raw!=nil
        // _Unit115:007CF4DC differentiates 0x0A Advanced from
        // the source type-0 Float32 and type-2 Cardinal cases.
        if kind=="U32_ADVANCED_UNFORMATTED" {
            field.SourceCellType=10
            if raw!=nil && group=="RESULT" && index<3 {
                b,_:=hex.DecodeString(*raw)
                u:=uint32(b[0])|uint32(b[1])<<8|uint32(b[2])<<16|uint32(b[3])<<24
                starts:=[3]uint{0,4,10}
                widths:=[3]uint{1,3,2}
                selected:=(u>>starts[index])&((uint32(1)<<widths[index])-1)
                field.AdvancedSelectedID=&selected
            }
        } else if kind=="U32_CANDIDATE" {
            field.SourceCellType=2
        }
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
    // Source WriteValues loops channel first, then 0/1/2 lists, then
    // tach. Each cell's index uses its OWN original mask address.
    for ch:=0;ch<8;ch++ {
        if !w.Channels[ch]{continue}
        base:=0x2000+ch*0x200
        for i:=0;i<43;i++{
            if w.Spec[i]{
                appendField(ch+1,"SPEC",i,base+2+2*i,
                    "F32_CANDIDATE",true)
            }
        }
        for i:=0;i<6;i++{
            if w.Values[i]{
                addr,kind:=sourceResultAdcSixAddress(base,i)
                appendField(ch+1,"RESULT",i,addr,kind,true)
            }
        }
        for i:=0;i<24;i++{
            if w.Values[6+i]{
                appendField(ch+1,"BAND",i,base+0x60+2*i,
                    "F32_CANDIDATE",true)
            }
        }
    }
    for tach:=0;tach<2;tach++ {
        if !w.Channels[8+tach]{continue}
        base:=0x3000+tach*0x100
        for i,offset:=range [...]int{0,2,4,6,8,0xFE} {
            if !w.Values[30+i]{continue}
            addr:=base+offset
            // Unlike an old full snapshot, 0xFE needs independent
            // freshness evidence from THIS accepted PARAM prefix, up
            // to and including its 0x3100 trigger descriptor.
            fresh:=i<5 || sourceLatch || sourceRawWordsIncludedInCurrentParam(blocks,addr)
            kind:="U32_CANDIDATE"
            if i<2 {kind="F32_CANDIDATE"}
            appendField(9+tach,"TACH",i,addr,kind,fresh)
        }
    }
    for i:=36;i<len(w.Values);i++{
        if w.Values[i]{tick.ExtraLegacyFlagsIgnored++}
    }
    if len(tick.OrderedFields)==0 {
        return sourceValuesRawTick{},nil,errors.New(
            "source WriteValues no originally selected 43 SPEC or 36 VALUES cells")
    }
    line.WriteString("\r\n")
    raw:=[]byte(line.String())
    if len(raw)>sourceValuesMaxRowBytes {
        return sourceValuesRawTick{},nil,errors.New("source WriteValues selected row too large")
    }
    h:=sha256.Sum256(raw)
    tick.RawRowSHA256=hex.EncodeToString(h[:])
    return tick,raw,nil
}
