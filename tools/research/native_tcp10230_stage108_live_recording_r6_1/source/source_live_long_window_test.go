package main

import (
    "archive/zip"
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "math"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceLongTestMonitor(t *testing.T, frames int) *Monitor {
    t.Helper()
    dir:=filepath.Join(t.TempDir(),"TEST_2026-11-17_12-00-00.000")
    m,e:=NewMonitor(dir,"LIVE_READ_ONLY","127.0.0.1")
    if e!=nil {t.Fatal(e)}
    t.Cleanup(func(){m.CloseFiles()})
    m.liveProgressEnabled=true
    m.liveBin=&LiveBinSpool{} // existing calibrated Go source spool enabled
    m.summary.Channels[0].rates=map[uint32]bool{65536:true}
    firstDevice:=uint32(0xFFFFFE00)
    for i:=0;i<frames;i++ {
        buf:=make([]byte,1024)
        value:=math.Float32bits(float32(i))
        for j:=0;j<256;j++ {
            buf[j*4]=byte(value)
            buf[j*4+1]=byte(value>>8)
            buf[j*4+2]=byte(value>>16)
            buf[j*4+3]=byte(value>>24)
        }
        h:=SampleHeader{Channel:0,Rate:65536,
            Index:firstDevice+uint32(i*256),Samples:256}
        if e:=m.sourceOriginalStorage.appendFrame(h,buf,
            sourceStorageCalibratedADC);e!=nil {t.Fatal(e)}
    }
    m.summary.Channels[0].Samples=uint64(frames*256)
    m.summary.RawBytes=uint64(frames)*1052
    m.summary.TotalFrames=uint64(frames)
    return m
}

func sourceLongTestRequest(t *testing.T,m *Monitor,id string,tag int) sourceLongWindowRequest {
    t.Helper()
    c:=m.sourceOriginalStorage.channels[0]
    count,e:=sourceLongWindowLength(c.sampleRate,tag)
    if e!=nil {t.Fatal(e)}
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(m.dir),
        RequestID:id,ADC:1,HTag:tag,Samples:count,
        CaptureEnd:c.rxPos,SampleRateHz:c.sampleRate,DeviceEnd:c.nextDeviceIndex,
    }
    raw,e:=json.Marshal(req)
    if e!=nil {t.Fatal(e)}
    if e=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),
        raw,0600);e!=nil {t.Fatal(e)}
    return req
}

func TestSourceLongWindowTwentySecondsFromActualOriginalRingAndSHA(t *testing.T) {
    count:=65536*20
    m:=sourceLongTestMonitor(t,count/256)
    req:=sourceLongTestRequest(t,m,"0123456789abcdef0123456789abcdef",0)
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil {t.Fatal(e)}
    if m.sourceLongWindowLastID!=req.RequestID {t.Fatal("request not serviced")}
    z,e:=zip.OpenReader(filepath.Join(m.dir,sourceLongWindowResultName))
    if e!=nil {t.Fatal(e)}
    defer z.Close()
    if len(z.File)!=2 {t.Fatalf("source long window must contain one ADC plus manifest: %d",len(z.File))}
    var receipt sourceLongWindowResult
    var data []byte
    for _,f:=range z.File {
        r,e:=f.Open();if e!=nil {t.Fatal(e)}
        buf:=new(bytes.Buffer)
        _,e=buf.ReadFrom(r);r.Close();if e!=nil {t.Fatal(e)}
        if f.Name=="MANIFEST.json" {
            if e=json.Unmarshal(buf.Bytes(),&receipt);e!=nil {t.Fatal(e)}
        } else if f.Name=="ADC1.f32" {
            data=buf.Bytes()
            if f.Method!=zip.Store {t.Fatal("compressed long window stalls single TCP owner")}
        } else {t.Fatal("unexpected ZIP member",f.Name)}
    }
    if len(data)!=count*4 || receipt.Samples!=uint32(count) ||
       receipt.CaptureEnd!=uint64(count) ||
       receipt.NextIndex!=req.DeviceEnd ||
       receipt.FirstIndex!=req.DeviceEnd-uint32(count) ||
       receipt.InputDomain!=sourceStorageCalibratedADC ||
       !receipt.CalibrationAlreadyApplied ||
       !receipt.Provisional {
        t.Fatalf("wrong source full-window receipt: %+v, size=%d",receipt,len(data))
    }
    sha:=sha256.Sum256(data)
    if receipt.SHA256!=hex.EncodeToString(sha[:]) {t.Fatal("source Float32 SHA mismatch")}
    // First/last actual source packet must be present in selected
    // 20-second GetSignal without 262144 downshift or fabricated zeros.
    if b:=math.Float32frombits(uint32(data[0])|uint32(data[1])<<8|
       uint32(data[2])<<16|uint32(data[3])<<24);b!=0 {t.Fatal("first real frame lost",b)}
    if m.sourceOriginalStorage.channels[0].rxPos!=uint64(count) {
        t.Fatal("on-demand selection changed original receive cursor")
    }
    // An unchanged local request must not write 5MiB again.
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil {t.Fatal(e)}
    if m.summary.ReadOnly!=true || m.summary.SourceSetRateBytes!=0 {
        t.Fatal("window extraction transmitted a device command")
    }
}

func TestSourceLongWindowRejectsOverwriteAndForgedSourceIndex(t *testing.T) {
    count:=65536*20
    m:=sourceLongTestMonitor(t,count/256)
    req:=sourceLongTestRequest(t,m,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",0)
    req.DeviceEnd--
    raw,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil {t.Fatal(e)}
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {
        t.Fatal("forged device cursor accepted")
    }
    // Requested old 20s no longer exists after original ring wrap.
    const moreFrames=(sourceOriginalStorageSamples/256)
    c:=m.sourceOriginalStorage.channels[0]
    for i:=0;i<moreFrames;i++ {
        h:=SampleHeader{Channel:0,Rate:65536,
            Index:c.nextDeviceIndex,Samples:256}
        buf:=make([]byte,1024)
        if e:=m.sourceOriginalStorage.appendFrame(h,buf,
            sourceStorageCalibratedADC);e!=nil {t.Fatal(e)}
        c=m.sourceOriginalStorage.channels[0]
    }
    m.summary.Channels[0].Samples=c.rxPos
    m.summary.TotalFrames+=moreFrames
    req.RequestID="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    req.DeviceEnd=(c.nextDeviceIndex-uint32(m.summary.Channels[0].Samples-uint64(count)))
    raw,_=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil {t.Fatal(e)}
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {
        t.Fatal("overwritten 20-second window used as fresh GetSignal")
    }
    if _,e:=os.Stat(filepath.Join(m.dir,sourceLongWindowResultName));!errors.Is(e,os.ErrNotExist) {
        t.Fatal("bad window produced source ZIP")
    }
}

func TestSourceLongWindowRequiresOriginalRateTagAndSameSession(t *testing.T) {
    for _,tc:=range []struct{
        hz uint32;tag int;valid bool
    }{{65536,0,true},{65536,1,true},{8192,0,false},{65536,14,false},{123,0,false}} {
        _,e:=sourceLongWindowLength(tc.hz,tc.tag)
        if (e==nil)!=tc.valid {t.Fatalf("rate/tag %d/%d: %v",tc.hz,tc.tag,e)}
    }
    m:=sourceLongTestMonitor(t,65536*20/256)
    req:=sourceLongTestRequest(t,m,"cccccccccccccccccccccccccccccccc",0)
    req.SessionID="TEST_FOREIGN_RUN"
    raw,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil {t.Fatal(e)}
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {t.Fatal("foreign session")}
    req.SessionID=filepath.Base(m.dir)
    req.Samples=262144
    raw,_=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil {t.Fatal(e)}
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {t.Fatal("silent N downshift")}
    // Never open a request symlink, even a symlink to a benign regular file.
    if e:=os.Remove(filepath.Join(m.dir,sourceLongWindowRequestName));e!=nil {t.Fatal(e)}
    other:=filepath.Join(m.dir,"elsewhere.json")
    if e:=os.WriteFile(other,raw,0600);e!=nil {t.Fatal(e)}
    if e:=os.Symlink(other,filepath.Join(m.dir,sourceLongWindowRequestName));e==nil {
        if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {
            t.Fatal("source IPC followed a symlink")
        }
    }
}
