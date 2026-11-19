package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/binary"
    "math"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceRingADCBlock(seed uint32) []byte {
    p:=make([]byte,1024)
    for i:=0;i<256;i++ {binary.LittleEndian.PutUint32(p[i*4:],seed+uint32(i))}
    return p
}

func TestOriginalSourceRingTenChannelsAndByteWidths(t *testing.T) {
    r:=newSourceOriginalStorageRing()
    p:=r.receipt()
    if p.Schema!=sourceOriginalStorageSchema || p.BufferSamples!=1<<21 ||
       len(p.Channels)!=10 {t.Fatal("source Mode2 must allocate 10 identical-capacity storages")}
    for i,c:=range p.Channels {
        width:=4
        if i>=8 {width=1}
        if c.Channel!=i+1 || c.SampleWidthBytes!=width ||
           c.RxPos!=0 || c.Available!=0 || c.NextDeviceIndex!=nil {
            t.Fatalf("source storage[%d]: %+v",i,c)
        }
    }
    for i:=0;i<8;i++ {
        h:=SampleHeader{Channel:i,Rate:65536,Index:uint32(i*256),Samples:256}
        if e:=r.appendFrame(h,sourceRingADCBlock(uint32(i)),sourceStorageUnscaledADC);e!=nil {t.Fatal(e)}
        got,e:=r.window(i,0,256)
        if e!=nil || !bytes.Equal(got,sourceRingADCBlock(uint32(i))) {
            t.Fatalf("ADC%d original Float32 ring mismatch: %v",i+1,e)
        }
    }
    for i:=8;i<10;i++ {
        p:=bytes.Repeat([]byte{byte(i)},256)
        h:=SampleHeader{Channel:i,Rate:512,Index:0xFFFFFFC0,Samples:64,
            NonFinite:uint32(i-8+1)}
        // As ORIGINAL AdcDataType=2/Byte, any bit pattern is valid TACH
        // payload, regardless of an incidental Float32 nonfinite counter.
        if e:=r.appendFrame(h,p,sourceStorageTachBytes);e!=nil {t.Fatal(e)}
        c:=r.receipt().Channels[i]
        if c.RxPos!=256 || c.Available!=256 || *c.NextDeviceIndex!=0 ||
           c.RejectedNonfinite!=0 {
            t.Fatalf("TACH byte/rate/source cursor conflated: %+v",c)
        }
        got,e:=r.window(i,0,256)
        if e!=nil || !bytes.Equal(got,p) {t.Fatal("TACH byte payload changed",e)}
    }
}

func TestOriginalSourceRingFullTwoMillionWrapWithoutLostOrInventedData(t *testing.T) {
    r:=newSourceOriginalStorageRing()
    // Wrap across the *memory* ring and, independently, the uint32 device
    // index. No stream gap; consume 2,097,152+512 real Float32 elements.
    total:=(sourceOriginalStorageSamples+512)/256
    firstDevice:=uint32(0xFFFFFE00)
    for i:=0;i<total;i++ {
        h:=SampleHeader{Channel:0,Rate:65536,
            Index:firstDevice+uint32(i*256),Samples:256}
        if e:=r.appendFrame(h,sourceRingADCBlock(uint32(i*256)),sourceStorageCalibratedADC);e!=nil {t.Fatal(e)}
    }
    c:=r.receipt().Channels[0]
    if c.RxPos!=uint64(total*256) || c.ValidPos!=0 ||
       c.FirstReadable!=512 || c.Available!=sourceOriginalStorageSamples ||
       c.SequenceGaps!=0 || c.RateChanges!=0 {
        t.Fatalf("original ring wrap metadata mismatch: %+v",c)
    }
    if _,e:=r.window(0,0,256);e==nil {t.Fatal("overwritten source data falsely accepted")}
    if _,e:=r.window(0,512,sourceOriginalStorageSamples);e!=nil {
        t.Fatal("full original 2^21 window unavailable",e)
    }
    tail,e:=r.window(0,c.RxPos-512,512)
    if e!=nil {t.Fatal(e)}
    for i:=0;i<512;i++ {
        actual:=binary.LittleEndian.Uint32(tail[i*4:])
        want:=uint32((total*256)-512+i)
        if actual!=want {t.Fatalf("ring index %d has %d, want %d",i,actual,want)}
    }
}

func TestOriginalSourceRingInvalidateOnGapRateOrInputDomain(t *testing.T) {
    r:=newSourceOriginalStorageRing()
    add:=func(idx,rate uint32,domain string,nonfinite uint32) {
        t.Helper()
        h:=SampleHeader{Channel:3,Index:idx,Rate:rate,
            Samples:256,NonFinite:nonfinite}
        if e:=r.appendFrame(h,sourceRingADCBlock(idx),domain);e!=nil {t.Fatal(e)}
    }
    add(0,65536,sourceStorageCalibratedADC,0)
    add(256,65536,sourceStorageCalibratedADC,0)
    add(1024,65536,sourceStorageCalibratedADC,0) // missing frames
    p:=r.receipt().Channels[3]
    if p.SequenceGaps!=1 || p.ValidPos!=512 || p.Available!=256 {
        t.Fatalf("failed to invalidate discontinuous history: %+v",p)
    }
    if _,e:=r.window(3,0,512);e==nil {t.Fatal("stale pre-gap history readable")}
    add(1280,32768,sourceStorageCalibratedADC,0)
    add(1536,32768,sourceStorageUnscaledADC,0)
    add(1792,32768,sourceStorageUnscaledADC,1)
    p=r.receipt().Channels[3]
    if p.RateChanges!=1 || p.ValidPos!=p.RxPos ||
       p.RejectedNonfinite!=1 || p.Available!=0 {
        t.Fatalf("source InvalidateData semantics not preserved: %+v",p)
    }
    add(2048,32768,sourceStorageUnscaledADC,0)
    p=r.receipt().Channels[3]
    if p.Available!=256 || p.Domain!=sourceStorageUnscaledADC {
        t.Fatal("rate/domain transition must restart only with new real data")
    }
}

func TestOriginalSourceRingMonitorReceivesAndProvesAllTenChannels(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_ring_input"),"OFFLINE_REPLAY","")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    for ch:=0;ch<10;ch++ {
        n:=256
        typ:=typeADC
        if ch>=8 {n=64;typ=typeTach}
        raw:=make([]byte,28+n*4)
        binary.LittleEndian.PutUint32(raw[0:4],uint32(len(raw)))
        binary.LittleEndian.PutUint32(raw[4:8],typ)
        binary.LittleEndian.PutUint32(raw[12:16],0xFFFFFF00)
        binary.LittleEndian.PutUint32(raw[20:24],uint32(ch))
        binary.LittleEndian.PutUint32(raw[24:28],65536)
        for i:=0;i<n;i++ {binary.LittleEndian.PutUint32(raw[28+i*4:],math.Float32bits(float32(i)/8))}
        f:=Frame{Type:typ,Raw:raw}
        if e:=m.consume(f,time.Now());e!=nil {t.Fatal(e)}
    }
    proof:=m.sourceOriginalStorage.receipt()
    if len(proof.Channels)!=10 {t.Fatal("source ring not wired into native receiver")}
    for ch,p:=range proof.Channels {
        expected:=uint64(256)
        if p.RxPos!=expected || p.Available!=expected ||
           p.NextDeviceIndex==nil || p.SampleRate!=65536 {
            t.Fatalf("channel %d missing actual original source storage %+v",ch+1,p)
        }
    }
    status:=m.snapshotLiveStatus("RECORDING",time.Now())
    if status.SourceOriginalStorage==nil ||
       status.SourceOriginalStorage.Channels[9].SampleWidthBytes!=1 {
        t.Fatal("Live status must carry truthful source ring proof")
    }
}


func TestReconstructedCalibratedSpoolCannotWriteOriginalFloat32Ring(t *testing.T) {
    // No sourceOriginalStorage pointer exists on LiveBinSpool anymore.
    // Source original bTaskConnectClick FRange1 storage must be written
    // ONLY by Monitor.consume after the original rate/Freeze gate.
    r:=newSourceOriginalStorageRing()
    spool:=&LiveBinSpool{begun:true}
    f,e:=os.Create(filepath.Join(t.TempDir(),"forensic_adc1.partial"))
    if e!=nil{t.Fatal(e)}
    defer f.Close()
    spool.files[0]=f
    spool.digest[0]=sha256.New()
    spool.gain[0]=2.0
    payload:=make([]byte,1052)
    for i:=0;i<256;i++{
        binary.LittleEndian.PutUint32(payload[28+i*4:],
            math.Float32bits(1.25))
    }
    h:=SampleHeader{Channel:0,Rate:65536,Index:0xFFFFFF00,Samples:256}
    if e:=spool.adcFrame(Frame{Type:typeADC,Raw:payload},h);e!=nil{
        t.Fatal(e)
    }
    if r.receipt().Channels[0].RxPos!=0 {
        t.Fatal("Native forensic spool wrote original live ring implicitly")
    }
    if e=r.appendFrame(h,payload[28:],sourceStorageOriginalLiveADC);e!=nil{
        t.Fatal(e)
    }
    win,e:=r.window(0,0,256)
    if e!=nil{t.Fatal(e)}
    if !bytes.Equal(win,payload[28:]){
        t.Fatal("original live ring differs from full wire Float32 payload")
    }
    if e:=f.Sync();e!=nil{t.Fatal(e)}
    disk,e:=os.ReadFile(f.Name())
    if e!=nil{t.Fatal(e)}
    if bytes.Equal(disk,win) {
        t.Fatal("two independent source/forensic domains merged")
    }
    if got:=math.Float32frombits(binary.LittleEndian.Uint32(win));got!=1.25 {
        t.Fatalf("source live FRange1 applied exporter gain: %f",got)
    }
    if got:=math.Float32frombits(binary.LittleEndian.Uint32(disk));got!=2.5 {
        t.Fatalf("forensic exporter lost gain: %f",got)
    }
    info:=r.receipt().Channels[0]
    if info.Domain!=sourceStorageOriginalLiveADC ||
        info.OriginalLiveFRangeSingle==nil ||
        *info.OriginalLiveFRangeSingle!=1 ||
        info.RxPos!=256 || info.NextDeviceIndex==nil ||
        *info.NextDeviceIndex!=0{
        t.Fatalf("lost original source FRange/RxPos evidence %+v",info)
    }
}
