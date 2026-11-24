package main

// Synthetic end-to-end receive -> ring -> WriteData -> close. No device.
import (
    "bytes"
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "encoding/json"
    "math"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSourcePhysicalWriteDataSharesProcessedRingNotCloseGain(t *testing.T) {
    m,marks:=testLiveWriterMonitor(t)
    defer m.CloseFiles()
    journal,e:=newSourceOriginalParamGateJournal(m.dir)
    if e!=nil{t.Fatal(e)}
    m.sourceParamGate=journal
    var raw []byte
    push:=func(frame []byte){
        t.Helper()
        raw=append(raw,frame...)
        if err:=m.ProcessChunk(frame,time.Now());err!=nil{t.Fatal(err)}
    }
    cfg:=func(v float32)[]byte{
        b:=make([]byte,36)
        binary.LittleEndian.PutUint32(b,math.Float32bits(v))
        copy(b[4:],[]byte("V"))
        return makeParam([]RegBlock{{Addr:0x10e,Words:18,Payload:b}})
    }
    push(cfg(4))
    queueMark(t,marks,1,"data_begin")
    a:=sourceLiveWriterSample(typeADC,0,65536,0,math.Float32bits(2))
    push(a)
    unknown:=sourceLiveWriterSample(typeADC,1,65536,0,math.Float32bits(3))
    push(unknown)
    tach:=sourceLiveWriterSample(typeTach,8,65536,0,0x7fc00000)
    push(tach)
    m.sourceOriginalRXGate.setFreeze(true)
    push(cfg(7))
    push(sourceLiveWriterSample(typeADC,0,65536,1,math.Float32bits(99)))
    m.sourceOriginalRXGate.setFreeze(false)
    push(cfg(9))
    b:=sourceLiveWriterSample(typeADC,0,65536,2,math.Float32bits(-1))
    push(b)
    queueMark(t,marks,2,"data_end")
    push(makeIdentity())
    summary,_,err:=m.Finalize("STOPPED_BY_USER")
    if err!=nil{t.Fatal(err)}
    read:=func(name string)[]byte{
        t.Helper()
        x,err:=os.ReadFile(filepath.Join(m.dir,name))
        if err!=nil{t.Fatal(err)}
        return x
    }
    if !bytes.Equal(raw,read("incoming.raw")){t.Fatal("RAW mutated")}
    wire:=append(append([]byte{},a[28:]...),b[28:]...)
    if !bytes.Equal(read("SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"),wire){t.Fatal("wire mutated")}
    physical:=read("SOURCE_W01_ADC1_LIVE_PHYSICAL_CANDIDATE.bin")
    want:=make([]byte,8)
    binary.LittleEndian.PutUint32(want,math.Float32bits(8))
    binary.LittleEndian.PutUint32(want[4:],math.Float32bits(-4))
    if !bytes.Equal(physical,want){t.Fatalf("physical must use latch=4, not close=9: %x",physical)}
    // Freeze and index discontinuity may invalidate earlier history, but the
    // last stored accepted sample must be the identical processed value.
    ring:=m.sourceOriginalStorage
    tail,err:=ring.window(0,ring.channels[0].rxPos-1,1)
    if err!=nil||!bytes.Equal(tail,want[4:]){t.Fatal("physical/ring mismatch",err)}
    if len(read("SOURCE_W01_ADC2_LIVE_PHYSICAL_CANDIDATE.bin"))!=0 ||
       !bytes.Equal(read("SOURCE_W01_ADC2_LIVE_RX_UNSCALED.bin"),unknown[28:]) {
        t.Fatal("unknown range must preserve wire without inventing physical value")
    }
    if !bytes.Equal(read("SOURCE_W01_TACH1_LIVE_RX_UNSCALED.bin"),tach[28:]){
        t.Fatal("TACH bytes altered")
    }
    var audit sourceLiveDataAudit
    doc:=read(sourceLiveWriterAudit)
    if err=json.Unmarshal(doc,&audit);err!=nil{t.Fatal(err)}
    d:=sha256.Sum256(doc)
    if summary.SourceLiveWriteDataAuditSHA256!=hex.EncodeToString(d[:])||
       audit.PhysicalSchema!=sourceLivePhysicalSchema||audit.OriginalDelphiByteParityVerified {
        t.Fatal("missing or overstated physical evidence")
    }
    for _,f:=range audit.Windows[0].Files{
        switch f.Channel {
        case 1:
            d:=sha256.Sum256(want)
            if f.Physical==nil||f.Physical.Packets!=2||f.Physical.Skipped!=0||
               f.Physical.SHA256!=hex.EncodeToString(d[:])||f.Physical.Bytes!=8{t.Fatal("physical receipt mismatch")}
        case 2:
            if f.Physical==nil||f.Physical.Packets!=0||f.Physical.Skipped!=1{t.Fatal("unknown range receipt mismatch")}
        case 9:
            if f.Physical!=nil{t.Fatal("TACH must stay bytes")}
        }
    }
}
