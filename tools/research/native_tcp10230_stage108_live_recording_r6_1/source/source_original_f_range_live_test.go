package main

// Full original live FRange reconciliation:
//  - _Unit128.pas bTaskConnectClick 00846C7A..00846CB2 constructs 8
//    Float32 + 2 BYTE storages, leaving FRange=1 from 007D0A61.
//  - _Unit125.pas 00808284/0080828C calls ProcessBufferChunk with
//    ApplyRange=true for valid rate/unfrozen ADC.
//  - _Unit115.pas 007D23D1..23E1 multiplies each ring Float32 * FRange
//    IN PLACE, then advances FRxPos.
//  - offline viewer _Unit128.pas 008464B0..0084655E assigns V/S;
//    that code is NOT in the live bTaskConnectClick branch.
//  - mvk_idr(1).sqlite function/calls and mvkview.idp field offsets.
// No private source, device connection or vendor DSP coefficients here.
import (
    "bytes"
    "encoding/binary"
    "math"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestSourceOriginalLiveFRange1IsNotNativeBINGain(t *testing.T){
    dir:=filepath.Join(t.TempDir(),"source_frange_separated")
    m,e:=NewMonitor(dir,"LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    if e=m.EnableLiveBinSpool();e!=nil{t.Fatal(e)}
    if m.sourceOriginalStorage.receipt().Channels[0].RxPos!=0{
        t.Fatal("source original ring unexpectedly already received samples")
    }
    frames:=makeFixture()
    // Initial all-register PARAM has ADC1 gain=510, not FRange=1.
    // This must start only the reconstructed BIN sidecar.
    if e=m.ProcessChunk(frames[1].Raw,time.Now());e!=nil{t.Fatal(e)}
    if !m.liveBin.begun || m.liveBin.gain[0]!=510 {
        t.Fatal("synthetic gain fixture not initialized")
    }
    f:=syntheticFrame(0,0,0.125)
    if e=m.ProcessChunk(f.Raw,time.Now());e!=nil{t.Fatal(e)}
    ring,e:=m.sourceOriginalStorage.window(0,0,256)
    if e!=nil{t.Fatal(e)}
    if !bytes.Equal(ring,f.Raw[28:]) {
        t.Fatal("live original 2M ring incorrectly used Native gain")
    }
    c:=m.sourceOriginalStorage.receipt().Channels[0]
    if c.Domain!=sourceStorageOriginalLiveADC ||
       c.OriginalLiveFRangeSingle==nil ||
       *c.OriginalLiveFRangeSingle!=1 ||
       c.RxPos!=256 || c.Available!=256 ||
       m.liveBin.samples[0]!=256{
        t.Fatalf("source FRange input proof: %+v",c)
    }
    if e=m.liveBin.Close();e!=nil{t.Fatal(e)}
    calibrated,e:=os.ReadFile(filepath.Join(
        m.liveBin.dir,"ADC1.bin.partial"))
    if e!=nil{t.Fatal(e)}
    if len(calibrated)!=1024 ||
       math.Float32frombits(binary.LittleEndian.Uint32(calibrated[:4]))!=63.75 {
        t.Fatal("separate forensic exporter lost its unchanged ADC1 gain")
    }
    if bytes.Equal(ring,calibrated) {
        t.Fatal("two numerically distinct paths silently merged")
    }
    // READ-ONLY source ring is still complete before the second PARAM;
    // GetSignal must never wait for forensic calibrated BIN.
}

func TestSourceFRangeFloat32MultiplyMatchesOriginalX87StoreOnce(t *testing.T){
    values:=[]float32{0,1.25,-1.25,0.1,math.SmallestNonzeroFloat32}
    raw:=make([]byte,len(values)*4)
    for i,v:=range values {
        binary.LittleEndian.PutUint32(raw[i*4:],math.Float32bits(v))
    }
    original:=append([]byte(nil),raw...)
    identity,e:=sourceApplyOriginalFRange(raw,sourceOriginalLiveFRange)
    if e!=nil||!bytes.Equal(identity,original) {
        t.Fatal("live original FRange1 changed Float32 bits")
    }
    // A real non-one FRange occurs in the ARCHIVE viewer, not
    // when clicking Measure. Check *one* x87 fmul/stp rounding stage.
    scale:=float32(2.0)
    result,e:=sourceApplyOriginalFRange(raw,scale)
    if e!=nil{t.Fatal(e)}
    for i,v:=range values{
        scaled:=math.Float32frombits(binary.LittleEndian.Uint32(result[i*4:]))
        expected:=float32(float64(v)*float64(scale))
        if math.Float32bits(scaled)!=math.Float32bits(expected){
            t.Fatalf("x87 fmul Float32 store at index %d: got %08X want %08X",
                i,math.Float32bits(scaled),math.Float32bits(expected))
        }
    }
    if !bytes.Equal(raw,original) {
        t.Fatal("source FRange helper mutated incoming RAW payload")
    }
    if _,e=sourceApplyOriginalFRange(raw[:5],1);e==nil{
        t.Fatal("partial Float32 source payload accepted")
    }
    if _,e=sourceApplyOriginalFRange(raw,0);e==nil{
        t.Fatal("zero original FRange invented")
    }
    if _,e=sourceApplyOriginalFRange(raw,float32(math.Inf(1)));e==nil{
        t.Fatal("nonfinite original FRange invented")
    }
}
