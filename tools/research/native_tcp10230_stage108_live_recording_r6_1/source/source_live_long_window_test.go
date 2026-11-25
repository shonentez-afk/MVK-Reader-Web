package main

import (
    "archive/zip"
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "io"
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
    m.liveBin=&LiveBinSpool{} // local verified source ring, not BIN-gain injection
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
            sourceStorageOriginalLiveADC);e!=nil {t.Fatal(e)}
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
       receipt.InputDomain!=sourceStorageOriginalLiveADC ||
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
            sourceStorageOriginalLiveADC);e!=nil {t.Fatal(e)}
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
    }{{65536,0,true},{65536,1,true},{8192,0,true},
      {512,0,true},{512,13,false},{65536,14,false},{123,0,false}} {
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

func TestSourceLongWindowAfterFreezeRequiresFullPostThawOriginalRingHistory(t *testing.T) {
    // The Native TCP counter includes 256 frozen packet words, but
    // original FRxPos advances only on accepted packet data. Once the
    // requested entire 20s resides after thaw, the on-demand GetSignal
    // must recover instead of being permanently denied by unequal counts.
    n:=65536*20
    m:=sourceLongTestMonitor(t,n/256)
    g:=newSourceOriginalReceiveGate()
    g.allowed[0]=uint64(n)
    g.skippedFrozen[0]=256
    g.skippedFrozenFrames[0]=1
    g.lastSkippedNativeSample[0]=256
    g.freezeChanges=2
    m.sourceOriginalRXGate=g
    m.summary.Channels[0].Samples=uint64(n)+256
    req:=sourceLongTestRequest(t,m,"dddddddddddddddddddddddddddddddd",0)
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil {
        t.Fatal("source post-freeze long signal rejected: ",e)
    }
    if _,e:=os.Stat(filepath.Join(m.dir,sourceLongWindowResultName));e!=nil {
        t.Fatal("post-thaw real source Float32 not published",e)
    }
    g.setFreeze(true)
    req.RequestID="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    data,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),
        data,0600);e!=nil {t.Fatal(e)}
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil {
        t.Fatal("source Go published a new GetSignal while FreezeUpdate active")
    }
}

func TestSourceFFTWindowExactNFromActual2MRingNoNewTCP(t *testing.T) {
    // Source _Unit115:007D13D4 GetSpectrum accepts N up to 0x40000.
    // Use a full actual receive-ring copy, not the ordinary preview.
    m:=sourceLongTestMonitor(t,512) // 131072 accepted ADC samples
    n,e:=sourceFFTWindowLength(65536)
    if e!=nil || n!=65536{t.Fatalf("invalid original FFT N: %d %v",n,e)}
    for _,bad:=range []uint32{0,512,2048,12345,262145,524288}{
        if _,e:=sourceFFTWindowLength(bad);e==nil{
            t.Fatalf("invented bSpecLines FFT N=%d accepted",bad)
        }
    }
    c:=m.sourceOriginalStorage.channels[0]
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,SessionID:filepath.Base(m.dir),
        RequestID:"b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0",
        ADC:1,HTag:-1,Samples:n,CaptureEnd:c.rxPos,
        SampleRateHz:c.sampleRate,DeviceEnd:c.nextDeviceIndex,
    }
    raw,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil{
        t.Fatal(e)
    }
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil{t.Fatal(e)}
    z,e:=zip.OpenReader(filepath.Join(m.dir,sourceLongWindowResultName))
    if e!=nil{t.Fatal(e)}
    defer z.Close()
    var receipt sourceLongWindowResult
    var payload []byte
    for _,f:=range z.File{
        src,e:=f.Open();if e!=nil{t.Fatal(e)}
        v,e:=io.ReadAll(src);src.Close();if e!=nil{t.Fatal(e)}
        if f.Name=="MANIFEST.json"{
            if e:=json.Unmarshal(v,&receipt);e!=nil{t.Fatal(e)}
        }else if f.Name=="ADC1.f32"{payload=v}
    }
    if receipt.HTag!=-1 || receipt.Samples!=n ||
        receipt.CaptureEnd!=c.rxPos || len(payload)!=int(n)*4 ||
        receipt.NextIndex!=c.nextDeviceIndex || !receipt.CalibrationAlreadyApplied{
        t.Fatalf("FFT request not exact source ring: %+v size=%d",receipt,len(payload))
    }
    expected,e:=m.sourceOriginalStorage.window(0,c.rxPos-uint64(n),uint64(n))
    if e!=nil{t.Fatal(e)}
    if !bytes.Equal(expected,payload){t.Fatal("FFT window differs from REAL original ring")}
    sum:=sha256.Sum256(payload)
    if receipt.SHA256!=hex.EncodeToString(sum[:]){t.Fatal("source FFT SHA mismatch")}
    if !m.summary.ReadOnly || m.summary.SourceSetRateBytes!=0{
        t.Fatal("source FFT local IPC must never command instrument")
    }
}

func TestSourceShortGetSignalAfterFreezeUsesAcceptedRingNotTCPPreview(t *testing.T) {
    // Stage0..1 original ring after thaw: native TCP saw an extra frozen
    // ADC packet; a short GetSignal must not include it in the output.
    m:=sourceLongTestMonitor(t,256) // 65536 accepted elements
    gate:=newSourceOriginalReceiveGate()
    gate.allowed[0]=65536
    gate.skippedFrozen[0]=256
    gate.skippedFrozenFrames[0]=1
    m.sourceOriginalRXGate=gate
    m.summary.Channels[0].Samples=65536+256
    req:=sourceLongTestRequest(t,m,
        "c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0",5) // 500ms=32768
    if req.Samples!=32768{t.Fatal("short H scale cannot change N")}
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil{
        t.Fatal("Go source ring rejected valid post-Freeze short window:",e)
    }
    z,e:=zip.OpenReader(filepath.Join(m.dir,sourceLongWindowResultName))
    if e!=nil{t.Fatal(e)}
    defer z.Close()
    for _,f:=range z.File{
        if f.Name=="ADC1.f32"{
            src,e:=f.Open();if e!=nil{t.Fatal(e)}
            data,e:=io.ReadAll(src);src.Close();if e!=nil{t.Fatal(e)}
            if len(data)!=32768*4{t.Fatal("lost source short window samples")}
            expected,e:=m.sourceOriginalStorage.window(0,65536-32768,32768)
            if e!=nil || !bytes.Equal(expected,data){
                t.Fatal("short GetSignal used all-TCP preview instead of accepted ring")
            }
        }
    }
}

func TestSourceEnvelopeWindowUsesPreFIRParamsCountNotPostFFTCount(t *testing.T) {
    // PRIVATE _Unit115:007D1158/007D1462/007D1E70 proves bSpecLines
    // N is BEFORE decimation/IQ, and GetAdjusted uses taps*Fs/target.
    for _,tc:=range []struct{code int;selected uint32;want uint32}{
        {1,4096,4193},{2,4096,4225},{5,4096,4399},
        {20,4096,4147},{21,4096,4243},{26,4096,4145},
        {24,4096,5265},{25,4096,6479},{19,1024,7951},
    }{
        n,e:=sourceFIREnvelopeWindowLength(65536,tc.code,tc.selected)
        if e!=nil || n!=tc.want{
            t.Fatalf("source FIR code=%d N=%d: got %d (want %d), %v",
                tc.code,tc.selected,n,tc.want,e)
        }
    }
    for _,tc:=range []struct{hz uint32;code int;n uint32}{
        {65536,0,4096},{65536,32,4096},
        {65536,20,2048},{65536,20,1234},
        {512,20,4096},{8192,21,4096},
    }{
        if _,e:=sourceFIREnvelopeWindowLength(tc.hz,tc.code,tc.n);e==nil{
            t.Fatalf("invalid source FIR history silently admitted %+v",tc)
        }
    }
}

func TestSourceEnvelopeGoRingExactPreFIRLengthAndRawSHA(t *testing.T){
    m:=sourceLongTestMonitor(t,512) // 131072 actual admitted source words
    c:=m.sourceOriginalStorage.channels[0]
    n,e:=sourceFIREnvelopeWindowLength(c.sampleRate,20,4096)
    if e!=nil || n!=4147{t.Fatalf("source GetAdjusted: %d %v",n,e)}
    req:=sourceLongWindowRequest{
        Schema:sourceLongWindowRequestSchema,
        SessionID:filepath.Base(m.dir),
        RequestID:"f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0",
        ADC:1,HTag:-2,Samples:n,CaptureEnd:c.rxPos,
        SampleRateHz:c.sampleRate,DeviceEnd:c.nextDeviceIndex,
        EnvelopeCode:20,OriginalBSpecLines:4096,
    }
    raw,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),raw,0600);e!=nil{
        t.Fatal(e)
    }
    if e:=m.handleSourceLongWindowRequest(time.Now());e!=nil{t.Fatal(e)}
    z,e:=zip.OpenReader(filepath.Join(m.dir,sourceLongWindowResultName))
    if e!=nil{t.Fatal(e)}
    defer z.Close()
    var receipt sourceLongWindowResult
    var payload []byte
    for _,f:=range z.File{
        fp,e:=f.Open();if e!=nil{t.Fatal(e)}
        v,e:=io.ReadAll(fp);fp.Close();if e!=nil{t.Fatal(e)}
        if f.Name=="MANIFEST.json"{
            if e:=json.Unmarshal(v,&receipt);e!=nil{t.Fatal(e)}
        }else if f.Name=="ADC1.f32"{payload=v}
    }
    if receipt.HTag!=-2 || receipt.EnvelopeCode!=20 ||
       receipt.OriginalBSpecLines!=4096 || receipt.Samples!=4147 ||
       len(payload)!=int(n)*4 || receipt.CaptureEnd!=c.rxPos ||
       receipt.InputDomain!=sourceStorageOriginalLiveADC{
        t.Fatalf("wrong original source FIR receipt: %+v bytes=%d",receipt,len(payload))
    }
    expected,e:=m.sourceOriginalStorage.window(0,c.rxPos-uint64(n),uint64(n))
    if e!=nil || !bytes.Equal(payload,expected){
        t.Fatal("Go used TCP Preview or invented samples instead of real original ring")
    }
    sum:=sha256.Sum256(expected)
    if receipt.SHA256!=hex.EncodeToString(sum[:]){
        t.Fatal("Source pre-FIR SHA mismatch")
    }
    if !m.summary.ReadOnly || m.summary.SourceSetRateBytes!=0{
        t.Fatal("FIR local read must not issue physical MVK01 commands")
    }
    req.RequestID="f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1"
    req.Samples=4198 // previous WRONG local algorithm
    invalid,_:=json.Marshal(req)
    if e:=os.WriteFile(filepath.Join(m.dir,sourceLongWindowRequestName),invalid,0600);e!=nil{
        t.Fatal(e)
    }
    if e:=m.handleSourceLongWindowRequest(time.Now());e==nil{
        t.Fatal("outdated 4198-word FIR history accepted")
    }
}

 
func TestSourceFIRAllRateCodeAndOriginalMenuLengthPairs(t *testing.T) {
    accepted:=0
    for _,rate:=range []uint32{512,2048,8192,32768,65536} {
        for code:=1;code<=31;code++ {
            target:=sourceFIREnvelopeRates[code]
            for _,n:=range []uint32{1024,4096,8192,16384,32768,65536,131072,262144} {
                pre,post,fs,e:=sourceFIRWindowCounts(rate,code,n)
                if target>rate {
                    if e==nil {t.Fatalf("invalid FIR rate %d code %d",rate,code)}
                    continue
                }
                ratio:=rate/target
                want:=n/ratio/sourceFIRDecim[sourceFIREnvelopeStages[code]]
                if e!=nil || pre<n || post!=want || fs!=target/sourceFIRDecim[sourceFIREnvelopeStages[code]] {
                    t.Fatalf("FIR Fs=%d code=%d N=%d: %d/%d/%d %v",rate,code,n,pre,post,fs,e)
                }
                again,err:=sourceFIREnvelopeWindowLength(rate,code,n)
                if err!=nil||again!=pre {t.Fatalf("FIR exact window mismatch: %v",err)}
                accepted++
            }
        }
    }
    if accepted!=608 {t.Fatalf("source FIR coverage=%d",accepted)}
}
