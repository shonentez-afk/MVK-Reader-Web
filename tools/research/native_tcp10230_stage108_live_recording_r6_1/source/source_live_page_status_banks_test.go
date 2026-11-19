package main

import (
    "encoding/binary"
    "math"
    "path/filepath"
    "testing"
    "time"
)

// Source _Unit125 00804A30/008053B8: the UI sees only REGISTER-VALID
// words. This is not a synthetic FFT or vendor GetValueText oracle.
func TestMode2SourceAllStatusBanksFromActualParamAndFreeze(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_source_results"),"OFFLINE_REPLAY","")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    empty:=m.snapshotLiveStatus("CONNECTING",time.Now()).SourceLivePageStatusBanks
    if empty.Schema!=sourceLiveResultBanksSchema || len(empty.ADC)!=8 ||
        len(empty.TACH)!=2 || empty.ADC[0].Bands43[0]!=nil ||
        empty.TACH[1].Fields[0]!=nil {
        t.Fatalf("unknown original RegisterImage must not synthesize values: %+v",empty)
    }
    // Half a source DWORD must never show a Float32 result.
    m.image.Valid[0x2002]=true
    if got:=m.snapshotSourceLivePageStatusBanks().ADC[0].Bands43[0];got!=nil{
        t.Fatalf("half original source register exposed: %q",*got)
    }
    m.image.Valid[0x2002]=false
    for _,entry:=range []struct{
        addr uint16
        bits uint32
    }{
        {0x2002,math.Float32bits(1.5)},
        {0x2060,math.Float32bits(2.5)},
        {0x20A0,math.Float32bits(3.5)},
        {0x20E0,math.Float32bits(4.5)},
        {0x2120,0x00000051},
        {0x2130,math.Float32bits(5.5)},
        {0x2132,0x00000203},
        {0x3000,math.Float32bits(6.5)},
        {0x3002,math.Float32bits(7.5)},
        {0x3104,0x0000AA55},
    }{
        payload:=make([]byte,4)
        binary.LittleEndian.PutUint32(payload,entry.bits)
        if e:=m.ProcessChunk(makeParam([]RegBlock{{Addr:entry.addr,Words:2,Payload:payload}}),
            time.Now());e!=nil {t.Fatal(e)}
    }
    live:=m.snapshotLiveStatus("RECORDING",time.Now()).SourceLivePageStatusBanks
    if live.AcceptedParamFrames!=10 || live.ADC[0].Bands43[0]==nil ||
       *live.ADC[0].Bands43[0]!="0000c03f" || live.ADC[0].RMS24[0]==nil ||
       *live.ADC[0].RMS24[0]!="00002040" || live.ADC[0].Peak24[0]==nil ||
       live.ADC[0].PeakPeak24[0]==nil ||
       live.ADC[0].SensorStatus==nil || *live.ADC[0].SensorStatus!="51000000" ||
       live.ADC[0].AlarmValues[0]==nil || live.ADC[0].AlarmStatus[0]==nil ||
       live.TACH[0].Fields[0]==nil || live.TACH[1].Fields[2]==nil ||
       live.ADC[1].Bands43[0]!=nil || live.TACH[1].Fields[0]!=nil ||
       live.GetValueTextParityVerified || live.DelphiRuntimeParityVerified {
        t.Fatalf("Mode2 original source LIVE registers mixed/corrupted: %+v",live)
    }
    count:=live.AcceptedParamFrames
    m.sourceOriginalRXGate.frozen=true
    payload:=make([]byte,4)
    binary.LittleEndian.PutUint32(payload,math.Float32bits(999))
    if e:=m.ProcessChunk(makeParam([]RegBlock{{Addr:0x2002,Words:2,Payload:payload}}),
        time.Now());e!=nil{t.Fatal(e)}
    frozen:=m.snapshotSourceLivePageStatusBanks()
    if frozen.AcceptedParamFrames!=count || frozen.ADC[0].Bands43[0]==nil ||
       *frozen.ADC[0].Bands43[0]!="0000c03f" ||
       m.summary.SourceFrozenParamFrames==0{
        t.Fatal("original source FreezeUpdate must not change current PageStatus register")
    }
}

func TestMode2StatusBanksDropPreviousSocketRegImage(t *testing.T){
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_socket_results"),"OFFLINE_REPLAY","")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceTCP=&sourceTCPLedger{}
    if e:=m.sourceTCP.begin(m);e!=nil{t.Fatal(e)}
    payload:=make([]byte,4)
    binary.LittleEndian.PutUint32(payload,math.Float32bits(13.0))
    if e:=m.ProcessChunk(makeParam([]RegBlock{{Addr:0x2002,Words:2,Payload:payload}}),
      time.Now());e!=nil{t.Fatal(e)}
    if m.snapshotSourceLivePageStatusBanks().ADC[0].Bands43[0]==nil{
        t.Fatal("first accepted socket missing value")
    }
    m.sourceTCP.finish(m,"REMOTE_DISCONNECTED")
    if e:=m.sourceTCP.begin(m);e!=nil{t.Fatal(e)}
    fresh:=m.snapshotSourceLivePageStatusBanks()
    if fresh.TCPConnectionCount!=2 || fresh.ADC[0].Bands43[0]!=nil {
        t.Fatal("old socket live PageStatus result leaked into new TCP session")
    }
    m.sourceTCP.finish(m,"STOPPED_BY_USER")
}
