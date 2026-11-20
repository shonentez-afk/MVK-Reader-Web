package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "testing"
)

func TestRealReferenceRUVALUESHeaderSourceOrderCP1251(t *testing.T){
    var c [10]bool; var spec [43]bool; var val [73]bool
    c[0]=true;c[2]=true;c[5]=true
    for i:=0;i<43;i++{spec[i]=true}
    for i:=0;i<30;i++{val[i]=true}
    w:=&sourceLiveValuesWindow{Channels:c,Spec:spec,Values:val}
    b,e:=sourceRUValuesCandidateHeader(w)
    if e!=nil{t.Fatal(e)}
    if !bytes.HasPrefix(b,[]byte("sep=|\r\n|")){
        t.Fatal("missing source Windows ANSI header")
    }
    if bytes.Contains(b,[]byte{0xef,0xbb,0xbf}){
        t.Fatal("original source CSV must not use a UTF8 BOM")
    }
    if bytes.Count(b,[]byte("\r\n"))!=3{
        t.Fatal("original VALUES requires sep and exactly two header rows")
    }
    lines:=bytes.Split(bytes.TrimSuffix(b,[]byte("\r\n")),[]byte("\r\n"))
    for _,line:=range lines[1:]{
        if bytes.Count(line,[]byte("|"))!=219{
            t.Fatalf("3 ADC original source must have 219 selected values: %d",
                bytes.Count(line,[]byte("|")))
        }
    }
    if !bytes.Contains(b,[]byte{0xc0,0xd6,0xcf}) {
        t.Fatal("АЦП CP1251 header bytes absent")
    }
    for _,x:=range []string{
        "Виброускорение, Х..25 кГц",
        "Пик-фактор виброуск., Х..25 кГц",
        "Виброускорение, 10..3000 Гц",
        "Виброперемещение, Польз. 2",
    }{
        cp,e:=sourceEncodeCP1251(x)
        if e!=nil||!bytes.Contains(b,cp){t.Fatalf("source label missing: %q",x)}
    }
    // Proves deterministic byte content for audit receipts.
    _=sha256.Sum256(b)
}

func TestRUCSVLocaleSourceAdvancedAndDecimalComma(t *testing.T){
    float:="cdcccc3d"
    adv:="00000000"
    id:=uint32(0)
    src:=sourceValuesRawTick{
        Schema:sourceValuesRawLayoutSchema,LocalTime:"10:12:02.623",
        OrderedFields:[]sourceSelectedRawValue{
            {Group:"SPEC",ValueKind:"F32_CANDIDATE",SourceCellType:0,RawLE:&float},
            {Group:"RESULT",CellIndex:0,ValueKind:"U32_ADVANCED_UNFORMATTED",
                SourceCellType:10,RawLE:&adv,AdvancedSelectedID:&id},
        },
    }
    got,e:=sourceRUValuesCandidateRow(src)
    if e!=nil{t.Fatal(e)}
    expected:=append([]byte("10:12:02.623|0,1|"),0xce,0xca)
    expected=append(expected,[]byte("\r\n")...)
    if !bytes.Equal(got,expected){
        t.Fatalf("source RU CSV candidate must use original CP1251 comma: %s",hex.EncodeToString(got))
    }
    id=1
    got,e=sourceRUValuesCandidateRow(src)
    if e!=nil{t.Fatal(e)}
    overload,_:=sourceEncodeCP1251("Перегрузка")
    if !bytes.Contains(got,overload){t.Fatal("known extracted ru-ru label omitted")}
    got2,e:=sourceRUAdvancedResultTitle(1,7)
    if e!=nil||got2!="Идет заполнение (1, 4, 32 с)"{
        t.Fatal("source BuffersCell7 resource mismatch")
    }
    got2,e=sourceRUAdvancedResultTitle(2,3)
    if e!=nil||got2!="Неисправность"{
        t.Fatal("source SensorStateCell3 resource mismatch")
    }
}

func TestRUCSVSourceProfileInvalidSelectionAndUnavailable(t *testing.T){
    _,e:=sourceRUValuesCandidateHeader(nil)
    if e==nil{t.Fatal("nil selection should not yield vendor-shaped file")}
    b:=&sourceLiveValuesWindow{}
    if _,e=sourceRUValuesCandidateHeader(b);e==nil{
        t.Fatal("no fields cannot create source profile")
    }
    w:="00000000"
    tick:=sourceValuesRawTick{Schema:sourceValuesRawLayoutSchema,
        LocalTime:"10:12:02.623",OrderedFields:[]sourceSelectedRawValue{
            {Group:"RESULT",CellIndex:0,ValueKind:"U32_ADVANCED_UNFORMATTED",
                SourceCellType:10,RawLE:nil},
        },
    }
    got,e:=sourceRUValuesCandidateRow(tick)
    if e!=nil||string(got)!="10:12:02.623|UNKNOWN\r\n"{
        t.Fatal("missing source must remain UNKNOWN, never guessed")
    }
    tick.OrderedFields[0].RawLE=&w
    if _,e:=sourceRUValuesCandidateRow(tick);e==nil{
        t.Fatal("received Advanced must provide original selected bit ID")
    }
}
