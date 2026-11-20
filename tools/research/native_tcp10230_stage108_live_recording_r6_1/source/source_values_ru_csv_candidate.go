package main

// Additional RU source-layout CSV candidate for the existing real 0x3100
// stream. Two uploaded original operator files (Oct 28) independently
// establish sep=|, CP1251, CRLF, 2 header lines, 43+6+24 per selected ADC.
// The original extracted EXTLOCALIZATION ru-ru resource establishes 10
// Advanced titles for RESULT 0/1/2. This file contains NO measurements,
// no private source files, no actual localization resource and no device TX.
//
// This is a SOURCE-LAYOUT CANDIDATE, not an original Win32 byte-for-byte
// WriteValues. True binary32/Delphi rounding, unavailable DWORDs, current
// Win32 ACP and actual original live register values still require parity.
import (
    "encoding/binary"
    "encoding/hex"
    "errors"
    "fmt"
    "strconv"
    "strings"
)

const sourceValuesRUCSVProfileVersion = "MVK_SOURCE_VALUES_3100_CP1251_RU_LAYOUT_CANDIDATE_V1"

var sourceRUOctaveTitles = [...]string{
    "0.63","0.8","1","1.25","1.6","2","2.5","3.15","4","5",
    "6.3","8","10","12.5","16","20","25","31.5","40","50",
    "63","80","100","125","160","200","250","315","400","500",
    "630","800","1000","1250","1600","2000","2500","3150",
    "4000","5000","6300","8000","10000",
}
var sourceRUResultTitles = [...]string{
    "Индикатор перегрузки",
    "Индикатор заполнения буферов",
    "Состояние датчика",
    "Напряжение на датчике",
    "Виброускорение, Х..25 кГц",
    "Пик-фактор виброуск., Х..25 кГц",
}
var sourceRUBandRangeTitles = [...]string{
    "10..3000 Гц","10..2000 Гц","10..1000 Гц","2..1000 Гц",
    "0,8..300 Гц","0,8..150 Гц","Польз. 1","Польз. 2",
}
var sourceRUTachTitles = [...]string{
    "Частота вращения",
    "Среднее приращение ЧВ на один оборот",
    "Ошибка датчика оборотов",
    "Последняя метка времени",
    "Текущее значение на входе",
    "Наличие импульсов на входе",
}

func sourceRUResultTitle(index int) (string,error) {
    if index<0 || index>=len(sourceRUResultTitles){
        return "",errors.New("result source cell not in original Result6")
    }
    return sourceRUResultTitles[index],nil
}
func sourceRUBandTitle(index int)(string,error){
    if index<0 || index>=24{return "",errors.New("source band is not among Band24")}
    names:=[...]string{"Виброускорение, ","Виброскорость, ","Виброперемещение, "}
    return names[index%3]+sourceRUBandRangeTitles[index/3],nil
}
func sourceRUOriginalCellTitle(group string,index int)(string,error){
    switch group{
    case "SPEC":
        if index<0||index>=len(sourceRUOctaveTitles){
            return "",errors.New("source SPEC not in 43 bands")
        }
        return "Полоса "+sourceRUOctaveTitles[index]+" Гц",nil
    case "RESULT": return sourceRUResultTitle(index)
    case "BAND": return sourceRUBandTitle(index)
    case "TACH":
        if index<0||index>=len(sourceRUTachTitles){
            return "",errors.New("source Tach not in 6 selected cells")
        }
        return sourceRUTachTitles[index],nil
    }
    return "",errors.New("source unknown selected group")
}

// CP1251 subset sufficient for the verified Russian CSV field names and
// original extracted RU Advanced values, without external dependencies.
// Do not silently replace characters unsupported by the original profile.
func sourceEncodeCP1251(s string)([]byte,error){
    out:=make([]byte,0,len(s))
    for _,r:=range s{
        switch{
        case r>=0&&r<=0x7f: out=append(out,byte(r))
        case r>=0x0410&&r<=0x044f: out=append(out,byte(r-0x0410+0xc0))
        case r==0x0401:out=append(out,0xa8)
        case r==0x0451:out=append(out,0xb8)
        case r==0x2116:out=append(out,0xb9)
        default:return nil,fmt.Errorf("source CP1251 profile cannot represent rune U+%04X",r)
        }
    }
    return out,nil
}

// Header exactly follows the 2 source lines visible in operator's real
// Oct 28 VALUES file, then 1 original time/column-name row.
func sourceRUValuesCandidateHeader(w *sourceLiveValuesWindow)([]byte,error){
    if w==nil{return nil,errors.New("source header requires original selection")}
    groups:=[]string{""}
    titles:=[]string{"Время"}
    appendField:=func(ch string,group string,index int)error{
        title,e:=sourceRUOriginalCellTitle(group,index)
        if e!=nil{return e}
        groups=append(groups,ch)
        titles=append(titles,title)
        return nil
    }
    for ch:=0;ch<8;ch++{
        if !w.Channels[ch]{continue}
        name:=fmt.Sprintf("АЦП %d",ch+1)
        for i,selected:=range w.Spec{
            if selected{if e:=appendField(name,"SPEC",i);e!=nil{return nil,e}}
        }
        for i:=0;i<6;i++{
            if w.Values[i]{if e:=appendField(name,"RESULT",i);e!=nil{return nil,e}}
        }
        for i:=0;i<24;i++{
            if w.Values[6+i]{if e:=appendField(name,"BAND",i);e!=nil{return nil,e}}
        }
    }
    for tach:=0;tach<2;tach++{
        if !w.Channels[8+tach]{continue}
        name:=fmt.Sprintf("Тахометр %d",tach+1)
        for i:=0;i<6;i++{
            if w.Values[30+i]{if e:=appendField(name,"TACH",i);e!=nil{return nil,e}}
        }
    }
    if len(titles)<2 || len(groups)!=len(titles){
        return nil,errors.New("source original VALUES header has no selected cells")
    }
    return sourceEncodeCP1251("sep=|\r\n"+strings.Join(groups,"|")+
        "\r\n"+strings.Join(titles,"|")+"\r\n")
}

// Extracted original vendor EXTLOCALIZATION ru-ru (not embedded full JSON).
// Unlike a guessed "ОК", all IDs below are actually attested by the
// original source selector table AND by an extracted localization resource.
// The user-supplied TABLE/VALUES snapshot independently confirms three
// ID=0 string outputs as ОК, 63 ticks across ADC 1,3,6.
func sourceRUAdvancedResultTitle(index int,id uint32)(string,error){
    switch index{
    case 0:
        switch id{
        case 0:return "ОК",nil
        case 1:return "Перегрузка",nil
        }
    case 1:
        switch id{
        case 0:return "ОК",nil
        case 1:return "Идет заполнение (32 с)",nil
        case 3:return "Идет заполнение (4, 32 с)",nil
        case 7:return "Идет заполнение (1, 4, 32 с)",nil
        }
    case 2:
        switch id{
        case 0:return "ОК",nil
        case 1:return "Обрыв",nil
        case 2:return "КЗ линии",nil
        case 3:return "Неисправность",nil
        }
    default:return "",errors.New("Advanced not in original three Result list fields")
    }
    return fmt.Sprintf("(0x%08X)",id),nil
}

// A direct companion to RAW_LAYOUT and TEXT_CANDIDATE, built at precisely
// the same accepted PARAM 0x3100 tick and in identical original cell order.
func sourceRUValuesCandidateRow(tick sourceValuesRawTick)([]byte,error){
    if tick.Schema!=sourceValuesRawLayoutSchema || tick.LocalTime=="" ||
        len(tick.OrderedFields)==0{
        return nil,errors.New("Russian VALUES row requires validated real tick")
    }
    var b strings.Builder
    b.WriteString(tick.LocalTime)
    for _,cell:=range tick.OrderedFields{
        b.WriteByte('|')
        if cell.RawLE==nil{
            b.WriteString("UNKNOWN") // Never infer nil pointer or zero
            continue
        }
        data,e:=hex.DecodeString(*cell.RawLE)
        if e!=nil||len(data)!=4{
            return nil,errors.New("source candidate text requires complete DWORD")
        }
        switch cell.ValueKind{
        case "F32_CANDIDATE":
            if cell.SourceCellType!=0{return nil,errors.New("wrong source Float32 type")}
            b.WriteString(strings.ReplaceAll(
                sourceFloat32FourSignificantCandidate(data),".",","))
        case "U32_CANDIDATE":
            if cell.SourceCellType!=2{return nil,errors.New("wrong source Cardinal type")}
            b.WriteString(strconv.FormatUint(
                uint64(binary.LittleEndian.Uint32(data)),10))
        case "U32_ADVANCED_UNFORMATTED":
            if cell.SourceCellType!=10||cell.AdvancedSelectedID==nil ||
               cell.Group!="RESULT"{
                return nil,errors.New("source Russian Advanced missing typed proof")
            }
            title,e:=sourceRUAdvancedResultTitle(cell.CellIndex,*cell.AdvancedSelectedID)
            if e!=nil{return nil,e}
            b.WriteString(title)
        default:return nil,errors.New("unknown original source cell type")
        }
    }
    b.WriteString("\r\n")
    raw,e:=sourceEncodeCP1251(b.String())
    if e!=nil{return nil,e}
    if len(raw)>sourceValuesMaxRowBytes{return nil,errors.New("source candidate row too long")}
    return raw,nil
}
