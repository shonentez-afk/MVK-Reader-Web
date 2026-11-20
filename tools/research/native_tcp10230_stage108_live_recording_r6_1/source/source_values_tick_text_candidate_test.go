package main

import (
    "encoding/hex"
    "strings"
    "testing"
)

func TestSourceValuesTextCandidateNoAdvancedGuessAndExactSelectedOrder(t *testing.T){
    spec:="00002040"
    advanced:="51000000"
    tach:="0000d040"
    id:=uint32(1)
    tick:=sourceValuesRawTick{
        Schema:sourceValuesRawLayoutSchema,
        LocalTime:"16:24:12.173",
        OrderedFields:[]sourceSelectedRawValue{
            {Group:"SPEC",ValueKind:"F32_CANDIDATE",SourceCellType:0,RawLE:&spec},
            {Group:"RESULT",ValueKind:"U32_ADVANCED_UNFORMATTED",SourceCellType:10,AdvancedSelectedID:&id,RawLE:&advanced},
            {Group:"TACH",ValueKind:"F32_CANDIDATE",SourceCellType:0,RawLE:&tach},
            {Group:"TACH",ValueKind:"U32_CANDIDATE",SourceCellType:2},
        },
    }
    got,e:=sourceValuesTextCandidateRow(tick)
    if e!=nil{t.Fatal(e)}
    want:="16:24:12.173|2.5|UNRESOLVED_ADVANCED_ID_1|6.5|UNKNOWN\r\n"
    if string(got)!=want{t.Fatalf("source tick text mismatch: %q",got)}
    if strings.Contains(string(got),"RAW_"){t.Fatal("diagnostic raw leaked into text companion")}
    tick.OrderedFields[1].AdvancedSelectedID=nil
    if _,e:=sourceValuesTextCandidateRow(tick);e==nil{
        t.Fatal("advanced text is never guessed without bit evidence")
    }
}

func TestSourceValuesTextCandidateKnownNumericPrimitivesAndNonfinite(t *testing.T){
    for _,x:=range []struct{raw,want string}{
        {"00000000","0"},{"0000803f","1"},{"0000c03f","1.5"},
        {"00002040","2.5"},{"0000c07f","NAN"},
        {"0000807f","UNKNOWN_NONFINITE"},
        {"cdcccc3d","0.1"},
    }{
        b,_:=hex.DecodeString(x.raw)
        if got:=sourceFloat32FourSignificantCandidate(b);got!=x.want{
            t.Fatalf("text Float32 %s: got %q want %q",x.raw,got,x.want)
        }
    }
}
