package main

import (
    "archive/zip"
    "bytes"
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "io"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestPreviewRingSameBytesAsAlreadyCalibratedSpoolAndWrap(t *testing.T) {
    p:=newLivePreviewBuffer()
    initial:=uint32(1024)
    complete:=make([]byte,0,40*1024)
    for frame:=0; frame<40; frame++ { // wraps capacity at 32 ADC packets
        data:=make([]byte,1024)
        for j:=0;j<256;j++ {
            binary.LittleEndian.PutUint32(data[j*4:],uint32(frame*256+j))
        }
        header:=SampleHeader{Channel:3,Rate:65536,Index:initial+uint32(frame*256),Samples:256}
        if err:=p.appendCalibratedADC(header,data);err!=nil {t.Fatal(err)}
        complete=append(complete,data...)
    }
    captured,n,first:=p.channelBytes(3)
    if n!=livePreviewSamples || first != initial+uint32(8*256) ||
        !bytes.Equal(captured,complete[len(complete)-len(captured):]) {
        t.Fatal("wrap/order/Float32 stored bits disagree with original spool byte sequence")
    }
    if p.samples[0]!=0 {t.Fatal("must not invent unobserved ADC samples")}
    dir:=t.TempDir()
    summary:=Summary{ReadOnly:true,RawBytes:100000,TotalFrames:42}
    if err:=writePreviewAtomic(dir,p,summary,time.Now());err!=nil {t.Fatal(err)}
    z,err:=zip.OpenReader(filepath.Join(dir,livePreviewFile))
    if err!=nil {t.Fatal(err)}
    defer z.Close()
    var meta LivePreviewManifest
    for _,file:=range z.File {
        in,e:=file.Open();if e!=nil {t.Fatal(e)}
        b,e:=io.ReadAll(in);in.Close();if e!=nil {t.Fatal(e)}
        if file.Name=="MANIFEST.json" {
            if e:=json.Unmarshal(b,&meta);e!=nil {t.Fatal(e)}
        } else if file.Name=="ADC4.f32" {
            if !bytes.Equal(b,captured) {t.Fatal("atomic ZIP changed any Float32 bits")}
        } else {t.Fatalf("unexpected channel or file %q",file.Name)}
    }
    if len(meta.Channels)!=1 || meta.Channels[0].FirstSampleIndex!=first ||
        meta.Channels[0].Samples!=livePreviewSamples || !meta.CalibrationAlreadyApplied ||
        !meta.Provisional || !meta.ReadOnly || meta.Schema!=livePreviewSchema {
        t.Fatalf("incomplete or untrustworthy manifest: %+v",meta)
    }
    sha:=sha256.Sum256(captured)
    if meta.Channels[0].SHA256!=hex.EncodeToString(sha[:]) {t.Fatal("missing real SHA")}
    pending,_:=filepath.Glob(filepath.Join(dir,".mvk_live_preview_pending_*"))
    if len(pending)!=0 {t.Fatalf("atomic temp files left: %v",pending)}
}

func TestPreviewNeverCreatesUnrequestedFiles(t *testing.T) {
    dir:=t.TempDir()
    var p *LivePreviewBuffer
    if err:=writePreviewAtomic(dir,p,Summary{},time.Now());err!=nil {t.Fatal(err)}
    names,err:=os.ReadDir(dir)
    if err!=nil || len(names)!=0 {t.Fatalf("unexpected default preview: %v %v",names,err)}
    var real LivePreviewBuffer
    if err:=real.appendCalibratedADC(SampleHeader{Channel:8,Rate:65536,Samples:256},make([]byte,1024));err==nil {
        t.Fatal("invalid channel must never enter preview")
    }
}

func TestTransientLocalPreviewFailureDoesNotAffectNativeCapture(t *testing.T) {
    dir:=filepath.Join(t.TempDir(),"TEST_preview")
    m,err:=NewMonitor(dir,"OFFLINE_REPLAY","")
    if err!=nil {t.Fatal(err)}
    defer m.CloseFiles()
    m.liveProgressEnabled=true
    p:=newLivePreviewBuffer()
    h:=SampleHeader{Channel:0,Rate:65536,Index:4096,Samples:256}
    if err:=p.appendCalibratedADC(h,make([]byte,1024));err!=nil {t.Fatal(err)}
    m.liveBin=&LiveBinSpool{begun:true,preview:p}
    blocking:=filepath.Join(dir,livePreviewFile)
    if err:=os.Mkdir(blocking,0700);err!=nil {t.Fatal(err)}
    m.publishLiveStatus("RECORDING",true,"")
    if !m.liveProgressEnabled || m.livePreviewFailures!=1 || m.liveBin.preview==nil {
        t.Fatal("brief preview file lock must not stop accepted native capture")
    }
    if err:=os.Remove(blocking);err!=nil {t.Fatal(err)}
    m.publishLiveStatus("RECORDING",true,"")
    if m.livePreviewFailures!=0 || m.liveBin.preview==nil {
        t.Fatal("next local update must recover preview without a second TCP")
    }
    if _,err:=os.Stat(blocking);err!=nil {t.Fatal("preview did not recover",err)}
}
