package main

// Offline only. This synthetic contract tests source GetSignal HTag and
// Go 2M ring integrity without private original FIR banks or MVK01 commands.
import (
    "archive/zip"
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "io"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSourceFIRGetSignalHistoryFromOriginalTimeHTag(t *testing.T){
    for _,tc:=range []struct {
        code int
        tag int
        wantIn uint32
        wantOut uint32
        wantFs uint32
    }{{20,9,1361,655,32768},{1,9,1407,327,16384},
      {26,9,1359,1310,65536}} {
        n,out,fs,e:=sourceFIRGetSignalWindowLength(65536,tc.code,tc.tag)
        if e!=nil || n!=tc.wantIn || out!=tc.wantOut || fs!=tc.wantFs {
            t.Fatalf("GetSignal Code%d HTag%d: got %d/%d/%d: %v",
                tc.code,tc.tag,n,out,fs,e)
        }
    }
    for _,tc:=range []struct{rate uint32;code,tag int}{
        {65536,0,9},{65536,32,9},{65536,20,-1},
        {65536,20,14},{65536,24,9},{512,20,9},
    }{
        if _,_,_,e:=sourceFIRGetSignalWindowLength(
                tc.rate,tc.code,tc.tag);e==nil {
            t.Fatalf("invalid GetSignal FIR request accepted %+v",tc)
        }
    }
}

func TestSourceFIRGetSignalFromRealRingBoundToHScaleAndSourceIndex(t *testing.T){
    m:=sourceLongTestMonitor(t,48) // actual 12288 synthetic ADC samples
    c:=m.sourceOriginalStorage.channels[0]
    n,_,_,e:=sourceFIRGetSignalWindowLength(c.sampleRate,20,9)
    if e!=nil || n!=1361 {t.Fatal("source Code20 HTag9 length",n,e)}
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(m.dir),
        RequestID:"a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1",
        ADC:1,HTag:-3,Samples:n,CaptureEnd:c.rxPos,
        SampleRateHz:c.sampleRate,DeviceEnd:c.nextDeviceIndex,
        EnvelopeCode:20,OriginalHTag:9,
    }
    raw,_:=json.Marshal(req)
    path:=filepath.Join(m.dir,sourceLongWindowRequestName)
    if e=os.WriteFile(path,raw,0600);e!=nil{t.Fatal(e)}
    if e=m.handleSourceLongWindowRequest(time.Now());e!=nil{t.Fatal(e)}
    z,e:=zip.OpenReader(filepath.Join(m.dir,sourceLongWindowResultName))
    if e!=nil{t.Fatal(e)}
    var receipt sourceLongWindowResult
    var payload []byte
    for _,f:=range z.File {
        stream,e:=f.Open();if e!=nil{t.Fatal(e)}
        v,e:=io.ReadAll(stream);stream.Close();if e!=nil{t.Fatal(e)}
        if f.Name=="MANIFEST.json" {
            if e=json.Unmarshal(v,&receipt);e!=nil{t.Fatal(e)}
        }else if f.Name=="ADC1.f32"{payload=v}
    }
    z.Close()
    expected,e:=m.sourceOriginalStorage.window(0,c.rxPos-uint64(n),uint64(n))
    if e!=nil || !bytes.Equal(payload,expected) {t.Fatal("Go FIR GetSignal did not return exact ring bytes")}
    sum:=sha256.Sum256(expected)
    if receipt.HTag!=-3 || receipt.EnvelopeCode!=20 ||
       receipt.OriginalHTag!=9 || receipt.Samples!=1361 ||
       receipt.SHA256!=hex.EncodeToString(sum[:]) ||
       receipt.CaptureEnd!=c.rxPos || receipt.NextIndex!=c.nextDeviceIndex ||
       !m.summary.ReadOnly || m.summary.SourceSetRateBytes!=0 {
        t.Fatalf("false/unsafe filtered GetSignal result: %+v",receipt)
    }
    bad:=req
    bad.RequestID="b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"
    bad.OriginalHTag=8  // 50ms requires different PRE-FIR data
    raw,_=json.Marshal(bad)
    if e=os.WriteFile(path,raw,0600);e!=nil{t.Fatal(e)}
    if e=m.handleSourceLongWindowRequest(time.Now());e==nil {
        t.Fatal("Go accepted stale HTag9 history for HTag8")
    }
    bad=req
    bad.RequestID="c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3"
    bad.OriginalBSpecLines=4096
    raw,_=json.Marshal(bad)
    if e=os.WriteFile(path,raw,0600);e!=nil{t.Fatal(e)}
    if e=m.handleSourceLongWindowRequest(time.Now());e==nil {
        t.Fatal("source GetSignal accepted GetSpectrum menu metadata")
    }
}
