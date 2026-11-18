package main

import (
  "bytes"
  "encoding/binary"
  "math"
  "path/filepath"
  "testing"
  "time"
)

func TestOriginalTMVKThreadRateSelectionFreezeGateFromAllThreeSources(t *testing.T) {
    g:=newSourceOriginalReceiveGate()
    proof:=g.receipt()
    if proof.InitialThreadRate!=777 || proof.OriginalMenuRate!=65536 ||
       proof.SelectedRate!=65536 || proof.SelectionChanges!=1 ||
       proof.Frozen || !proof.PhysicalSetRateNotInferred ||
       proof.OriginalDelphiParityVerified {
        t.Fatalf("source Create -> mRate1Click -> SetRate (without device TX): %+v",proof)
    }
    f:=SampleHeader{Channel:0,Rate:8192,Samples:17}
    if g.allowedFrame(f,17) {t.Fatal("source Store accepted wrong MvkSampleRate")}
    f.Rate=65536
    if !g.allowedFrame(f,34) {t.Fatal("source Store rejected selected MvkSampleRate")}
    g.setFreeze(true)
    if g.allowedFrame(f,51) {t.Fatal("source FreezeUpdate wrote samples")}
    g.setFreeze(true)
    g.setFreeze(false)
    if !g.allowedFrame(f,68) {t.Fatal("source thaw did not restore source receive")}
    h:=SampleHeader{Channel:8,Rate:65536,Samples:7}
    g.setFreeze(true)
    if g.allowedFrame(h,7) {t.Fatal("source TACH Byte FreezeUpdate did not apply")}
    p:=g.receipt()
    if p.FreezeChanges!=3 || p.Channels[0].RateSkippedElements!=17 ||
       p.Channels[0].FrozenSkippedElements!=17 ||
       p.Channels[0].StoredGateElements!=34 ||
       p.Channels[8].FrozenSkippedElements!=28 {
       t.Fatalf("original source rate/freeze gate accounting: %+v",p)
    }
    if e:=g.selectRate(2048);e!=nil {t.Fatal(e)}
    f.Rate=2048
    g.setFreeze(false)
    if !g.allowedFrame(f,85) {t.Fatal("original SetRate updated MvkSampleRate too late")}
    if e:=g.selectRate(777);e==nil {t.Fatal("777 is initial sentinel, not a valid operator rate")}
}

func TestOriginalTMVKThreadReceiveGatePreservesRawButNotRingOnFreeze(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_original_freeze"),"LIVE_READ_ONLY","")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    frame:=func(rate uint32,index uint32) []byte {
        raw:=make([]byte,28+7*4)
        binary.LittleEndian.PutUint32(raw[:4],typeADC)
        binary.LittleEndian.PutUint32(raw[4:8],uint32(len(raw)))
        binary.LittleEndian.PutUint32(raw[12:16],index)
        binary.LittleEndian.PutUint32(raw[20:24],0)
        binary.LittleEndian.PutUint32(raw[24:28],rate)
        for i:=0;i<7;i++ {binary.LittleEndian.PutUint32(raw[28+i*4:],math.Float32bits(float32(i)+1))}
        return raw
    }
    initial:=frame(8192,0)
    accepted:=frame(65536,7)
    frozen:=frame(65536,14)
    thawed:=frame(65536,21)
    for _,f:=range [][]byte{initial,accepted} {
        if e:=m.ProcessChunk(f,time.Now());e!=nil {t.Fatal(e)}
    }
    if m.sourceOriginalStorage.receipt().Channels[0].RxPos!=7 {
        t.Fatal("rate gate did not reject mismatched source")
    }
    m.sourceOriginalRXGate.setFreeze(true)
    if e:=m.ProcessChunk(frozen,time.Now());e!=nil {t.Fatal(e)}
    if m.sourceOriginalStorage.receipt().Channels[0].RxPos!=7 {
        t.Fatal("FreezeUpdate wrongly advanced original FRxPos")
    }
    m.sourceOriginalRXGate.setFreeze(false)
    if e:=m.ProcessChunk(thawed,time.Now());e!=nil {t.Fatal(e)}
    proof:=m.sourceOriginalStorage.receipt().Channels[0]
    if proof.RxPos!=14 || proof.FirstReadable!=7 {
       t.Fatalf("frozen interlude must invalidate stitched GetSignal history: %+v",proof)
    }
    if _,e:=m.sourceOriginalStorage.window(0,0,14);e==nil {
        t.Fatal("source gap was not denied")
    }
    got,e:=m.sourceOriginalStorage.window(0,7,7)
    if e!=nil || !bytes.Equal(got,thawed[28:]) {
        t.Fatal("post-thaw real source data lost",e)
    }
    if m.summary.Channels[0].Samples!=28 || m.summary.TotalFrames!=4 {
        t.Fatal("original continuous TCP RAW parser stopped during FreezeUpdate")
    }
    gate:=m.sourceOriginalRXGate.receipt()
    if gate.Channels[0].RateSkippedElements!=7 ||
       gate.Channels[0].FrozenSkippedElements!=7 ||
       gate.Channels[0].StoredGateElements!=14 ||
       m.summary.ReadOnly!=true {
        t.Fatalf("false original source gate or device TX: %+v",gate)
    }
}

func TestOriginalFreezeLocalStdinDoesNotTransmitToMVK(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_no_device_control"),
        "LIVE_READ_ONLY","")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    local:=make(chan string,3)
    local<-"FREEZE 1"
    if e:=m.drainSourceOperatorRates(local);e!=nil {t.Fatal(e)}
    if !m.sourceOriginalRXGate.frozen {t.Fatal("Go source ring not frozen")}
    local<-"RATE 8192"
    if e:=m.drainSourceOperatorRates(local);e!=nil {t.Fatal(e)}
    if m.sourceOriginalRXGate.rate!=65536 ||
       m.summary.SourceSetRateBytes!=0 || !m.summary.ReadOnly {
        t.Fatal("local FREEZE permitted unapproved instrument SetRate")
    }
    local<-"FREEZE 0"
    if e:=m.drainSourceOperatorRates(local);e!=nil {t.Fatal(e)}
    if m.sourceOriginalRXGate.frozen ||
       m.sourceOriginalRXGate.freezeChanges!=2 {
        t.Fatal("local source thaw did not update original freeze flag")
    }
    status:=m.snapshotLiveStatus("RECORDING",time.Now())
    if status.SourceOriginalReceiveGate==nil ||
       status.SourceOriginalReceiveGate.SelectedRate!=65536 ||
       status.SourceOriginalReceiveGate.Frozen {
        t.Fatal("status omitted exact source receive gate proof")
    }
}
