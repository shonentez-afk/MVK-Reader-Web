package main

import (
    "archive/zip"
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "io"
    "os"
    "path/filepath"
    "strings"
    "testing"
    "time"
)

// Real ProcessChunk -> Byte ring -> local ZIP. Word cursor wraps into
// byte cursor zero even though the wire word index is still nonzero.
func runTachByteWindowTest(t *testing.T,dir string){
    t.Helper()
    m,e:=NewMonitor(dir,"OFFLINE_REPLAY","192.0.2.84")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.liveProgressEnabled=true
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    now:=time.Now().UTC()
    words:=make([]uint32,512)
    for i:=range words{words[i]=0x7fc00000|uint32(i&255)}
    first:=uint32(0x40000000-512)
    payloads:=make([][]byte,2)
    for i:=0;i<2;i++{
        raw:=sourceLiveWriterSample(typeTach,i+8,65536,first,words...)
        if e=m.ProcessChunk(raw,now);e!=nil{t.Fatal(e)}
        payloads[i]=append([]byte(nil),raw[28:]...)
    }
    for i:=0;i<2;i++{
        tag,n:=9,uint32(1310)
        if i==1{tag,n=-1,1024}
        row:=m.sourceOriginalStorage.channels[i+8]
        epoch:=m.sourceOriginalStorage.displayEpoch(i+8)
        if epoch==nil{t.Fatal("missing display epoch for typed TACH window")}
        req:=sourceLongWindowRequest{Schema:sourceLongWindowRequestSchema,
            SessionID:filepath.Base(dir),RequestID:strings.Repeat(string(rune('a'+i)),32),
            ADC:i+9,HTag:tag,Samples:n,CaptureEnd:row.rxPos,
            SampleRateHz:65536,DeviceEnd:row.nextDeviceIndex,SampleWidth:1,SourceEpoch:epoch}
        write:=func(req sourceLongWindowRequest){
            t.Helper()
            b,e:=json.Marshal(req);if e!=nil{t.Fatal(e)}
            if e=os.WriteFile(filepath.Join(dir,sourceLongWindowRequestName),b,0600);e!=nil{t.Fatal(e)}
        }
        write(req)
        if e=m.handleSourceLongWindowRequest(now);e!=nil{t.Fatal(e)}
        z,e:=zip.OpenReader(filepath.Join(dir,sourceLongWindowResultName));if e!=nil{t.Fatal(e)}
        var rec sourceLongWindowResult
        var data []byte
        entry:="TACH1.u8";if i==1{entry="TACH2.u8"}
        for _,f:=range z.File{
            fp,e:=f.Open();if e!=nil{t.Fatal(e)}
            b,e:=io.ReadAll(fp);fp.Close();if e!=nil{t.Fatal(e)}
            if f.Name=="MANIFEST.json"{if e=json.Unmarshal(b,&rec);e!=nil{t.Fatal(e)}}else if f.Name==entry{data=b}else{t.Fatal("wrong member")}
        }
        z.Close()
        want:=payloads[i][len(payloads[i])-int(n):]
        sha:=sha256.Sum256(want)
        if !bytes.Equal(data,want)||rec.SHA256!=hex.EncodeToString(sha[:])||
           rec.SampleWidth!=1||rec.InputDomain!=sourceStorageTachBytes||
           rec.CalibrationAlreadyApplied||rec.NextIndex!=0||rec.FirstIndex!=uint32(0)-n||
           rec.DeviceEndWordIndex==nil||*rec.DeviceEndWordIndex!=0x40000000||
           rec.SourceEpoch==nil||*rec.SourceEpoch!=*epoch||
           rec.CaptureEnd!=2048||row.rxPos!=2048 {
            t.Fatalf("wrong typed TACH window %+v len=%d",rec,len(data))
        }
        // Save actual IPC artifacts for isolated cross-language CI.
        b,e:=os.ReadFile(filepath.Join(dir,sourceLongWindowResultName));if e!=nil{t.Fatal(e)}
        if e=os.WriteFile(filepath.Join(dir,entry+".zip"),b,0600);e!=nil{t.Fatal(e)}
        // Four byte-cursor aliases are possible; verify the true wire word.
        bad:=req;bad.RequestID=strings.Repeat(string(rune('c'+i)),32);bad.DeviceEnd+=0x40000000
        write(bad)
        if e=m.handleSourceLongWindowRequest(now);e==nil{t.Fatal("aliased wire word cursor accepted")}
        bad=req;bad.RequestID=strings.Repeat(string(rune('e'+i)),32);bad.SampleWidth=4
        write(bad)
        if e=m.handleSourceLongWindowRequest(now);e==nil{t.Fatal("Float32 TACH request accepted")}
        bad=req;bad.RequestID=strings.Repeat(string(rune('1'+i)),32);bad.HTag=-2;bad.EnvelopeCode=20
        write(bad)
        if e=m.handleSourceLongWindowRequest(now);e==nil{t.Fatal("TACH FIR request accepted")}
        m.sourceOriginalRXGate.setFreeze(true)
        bad=req;bad.RequestID=strings.Repeat(string(rune('3'+i)),32);write(bad)
        if e=m.handleSourceLongWindowRequest(now);e==nil{t.Fatal("frozen TACH request accepted")}
        m.sourceOriginalRXGate.setFreeze(false)
    }
    status:=m.snapshotLiveStatus("RECORDING",now)
    b,e:=json.Marshal(status);if e!=nil{t.Fatal(e)}
    if e=os.WriteFile(filepath.Join(dir,"TACH_WINDOW_STATUS.json"),b,0600);e!=nil{t.Fatal(e)}
    if m.summary.SourceSetRateBytes!=0||!m.summary.ReadOnly{t.Fatal("local ring request sent device command")}
}

func TestSourceTachByteWindowFromRealReceive(t *testing.T){
    runTachByteWindowTest(t,filepath.Join(t.TempDir(),"TEST_2026-11-24_06-00-00.000"))
}
func TestSourceTachByteWindowCoreFixture(t *testing.T){
    root:=os.Getenv("MVK_PREFIX_FIXTURE_DIR")
    if root==""{t.Skip("cross-language fixture not requested")}
    runTachByteWindowTest(t,filepath.Join(root,"TEST_2026-11-24_06-00-00.000"))
}
