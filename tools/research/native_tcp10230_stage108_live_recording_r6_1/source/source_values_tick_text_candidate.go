package main

// Separate, source-shaped TEXT CANDIDATE companion for the real 0x3100
// tick. The vendor _Unit115:007CE6E4 has 30 dispatch types; the live
// _Unit125:00804A30/00804DEC/00805040/008053B8 selected lists actually
// use Float32 type 0, Cardinal type 2, and advanced type 10. The latter
// requires TMvkAdvancedCell.GetTitleByID and TLanguage, not a numeric
// substitute. All source bytes remain in the independent RAW CSV/JSONL.
//
// Numeric conversion below is a deliberate local FORMAT CANDIDATE.
// Delphi Win32 FormatFloat/locale/x87, ANSI code page, advanced language
// and hardware byte parity have NOT been established. Never use this
// companion as proof of byte-identical MVKView WriteValues.
import (
    "encoding/binary"
    "encoding/hex"
    "errors"
    "fmt"
    "math"
    "strconv"
    "strings"
)

const sourceValuesTextCandidateFormatterVersion="MVK_SOURCE_WRITEVALUES_SOURCE_TEXT_CANDIDATE_V2"

// Approximate _Unit114:007B2090 FormatSpec=4 (from
// _Unit115:007CF3A8). It uses a source Float32 value, 4 significant
// digits and trailing-zero cleanup; differences near decimal rounding
// boundaries are explicitly NOT certified against Win32 FormatFloat.
func sourceFloat32FourSignificantCandidate(data []byte)string{
    f32:=math.Float32frombits(binary.LittleEndian.Uint32(data))
    f:=float64(f32)
    if math.IsNaN(f){return "NAN"}
    if math.IsInf(f,0){return "UNKNOWN_NONFINITE"}
    if f==0{return "0"}
    a:=f32
    if a<0 {a=-a}
    // _Unit114:007B20F3..007B2151: multiply Float32 by 10 until
    // abs>=10^(FormatSpec-1), appending one fractional zero each time.
    // The common GetValueText overload uses FormatSpec=4.
    places:=0
    for a<float32(1000) {
        a*=float32(10)
        places++
        if places>64 {return "UNKNOWN_FLOAT32_FORMAT"}
    }
    // Go rounding is a candidate, NOT certified Win32/x87 FormatFloat.
    s:=strconv.FormatFloat(f,'f',places,32)
    if strings.Contains(s,"."){
        s=strings.TrimRight(s,"0")
        s=strings.TrimRight(s,".")
    }
    if s=="-0"{return "0"}
    return s
}
func sourceAdvancedIsOriginalSelectorValue(field sourceSelectedRawValue)bool{
    if field.AdvancedSelectedID==nil||field.Group!="RESULT"{return false}
    id:=*field.AdvancedSelectedID
    switch field.CellIndex {
    case 0:return id<=1
    case 1:return id==0||id==1||id==3||id==7
    case 2:return id<=3
    }
    return false
}

func sourceValuesTextCandidateRow(tick sourceValuesRawTick)([]byte,error){
    if tick.Schema!=sourceValuesRawLayoutSchema ||
        tick.LocalTime=="" || len(tick.OrderedFields)==0{
        return nil,errors.New("source text candidate requires a checked 0x3100 source tick")
    }
    var row strings.Builder
    row.WriteString(tick.LocalTime)
    for _,field:=range tick.OrderedFields{
        row.WriteByte('|')
        if field.RawLE==nil{
            row.WriteString("UNKNOWN")
            continue
        }
        raw,e:=hex.DecodeString(*field.RawLE)
        if e!=nil || len(raw)!=4{
            return nil,errors.New("source text candidate requires a full little-endian DWORD")
        }
        switch field.ValueKind{
        case "F32_CANDIDATE":
            if field.SourceCellType!=0{
                return nil,errors.New("source Float32 cell type conflict")
            }
            row.WriteString(sourceFloat32FourSignificantCandidate(raw))
        case "U32_CANDIDATE":
            if field.SourceCellType!=2{
                return nil,errors.New("source Cardinal cell type conflict")
            }
            row.WriteString(strconv.FormatUint(
                uint64(binary.LittleEndian.Uint32(raw)),10))
        case "U32_ADVANCED_UNFORMATTED":
            if field.SourceCellType!=10 || field.AdvancedSelectedID==nil{
                return nil,errors.New("source Advanced cell missing original ID evidence")
            }
            // This is NOT the original localized GetTitleByID.
            if sourceAdvancedIsOriginalSelectorValue(field){
                row.WriteString("UNRESOLVED_ADVANCED_ID_")
                row.WriteString(strconv.FormatUint(uint64(*field.AdvancedSelectedID),10))
            } else if field.Group=="RESULT" && field.CellIndex>=0 &&
                       field.CellIndex<3 {
                // _Unit115:007D0845: unknown GetTitleByID is (0xXXXXXXXX).
                row.WriteString(fmt.Sprintf("(0x%08X)",*field.AdvancedSelectedID))
            } else {
                return nil,errors.New("source Advanced list index invalid")
            }
        default:
            return nil,errors.New("source text candidate unknown original cell kind")
        }
    }
    row.WriteString("\r\n")
    b:=[]byte(row.String())
    if len(b)>sourceValuesMaxRowBytes{
        return nil,errors.New("source text candidate exceeds maximum row length")
    }
    return b,nil
}
