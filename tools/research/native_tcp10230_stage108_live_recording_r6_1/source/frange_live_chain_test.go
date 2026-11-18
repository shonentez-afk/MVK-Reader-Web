package main

// Regression derived from original _Unit125 00806964/00808653 and
// _Unit115 TMvkChannelStorage.ProcessBufferChunk 007D2398.
// Native MUST multiply each raw ADC Float32 by FRange ONCE (never twice)
// before writing its verified BIN spool and mirrored live ring.

import (
    "bytes"
    "encoding/binary"
    "math"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func frangeTestImage(t *testing.T, firstGain float32) *RegisterImage {
    t.Helper()
    image:=&RegisterImage{}
    for channel:=0;channel<8;channel++ {
        base:=0x0100+channel*0x100
        sensitivity:=make([]byte,4)
        binary.LittleEndian.PutUint32(sensitivity,math.Float32bits(0.010194))
        image.Put(RegBlock{Addr:uint16(base+0x02),Words:2,Payload:sensitivity})
        gain:=float32(channel+1)
        if channel==0 {gain=firstGain}
        raw:=make([]byte,4)
        binary.LittleEndian.PutUint32(raw,math.Float32bits(gain))
        image.Put(RegBlock{Addr:uint16(base+0x0E),Words:2,Payload:raw})
    }
    return image
}

func TestNativeFRangex510FromOriginalConfigIsAppliedExactlyOnce(t *testing.T) {
    const originalFRangex32 uint32 = 0x43FF4853
    gain:=math.Float32frombits(originalFRangex32)
    if math.Abs(float64(gain)-510.565033)>1e-5 {
        t.Fatalf("historical FRange bits changed: %g",gain)
    }
    image:=frangeTestImage(t,gain)
    actualGains,_,err:=makeGain(image)
    if err!=nil || math.Float32bits(actualGains[0])!=originalFRangex32 {
        t.Fatalf("initial FC03 channel configuration FRange differs: %g %v",actualGains[0],err)
    }

    ring:=newSourceOriginalStorageRing()
    spool:=&LiveBinSpool{dir:t.TempDir(),sourceOriginalStorage:ring}
    if err:=spool.start(image);err!=nil {t.Fatal(err)}
    defer spool.Close()

    // Raw sensor sample 1.25: the expected calibrated value is around
    // 638.2063, NOT 1.25 and NOT 325,xxx from another FRange multiply.
    frame:=syntheticFrame(0,0,1.25)
    header:=SampleHeader{Channel:0,Rate:65536,Index:0,Samples:256}
    if err:=spool.adcFrame(frame,header);err!=nil {t.Fatal(err)}

    data,proof,err:=ring.snapshotCalibratedADC(0,256)
    if err!=nil {t.Fatal(err)}
    if proof.Domain!=sourceStorageCalibratedADC {
        t.Fatalf("raw ADC bits mislabelled as calibrated: %s",proof.Domain)
    }
    expected:=float32(float64(float32(1.25))*float64(gain))
    if got:=math.Float32frombits(binary.LittleEndian.Uint32(data[:4]));got!=expected {
        t.Fatalf("FRange missing or doubled: %g, expected %g from ADCraw*FRange",got,expected)
    }
    disk,err:=os.ReadFile(spool.files[0].Name())
    if err!=nil {t.Fatal(err)}
    if !bytes.Equal(data,disk) {
        t.Fatal("Go IPC source ring is not bit-exact calibrated BIN spool")
    }
    if spool.samples[0]!=256 {
        t.Fatal("calibration output sample count fabricated")
    }

    m,err:=NewMonitor(filepath.Join(t.TempDir(),"capture"),"LIVE_READ_ONLY","192.168.1.83")
    if err!=nil {t.Fatal(err)}
    defer m.CloseFiles()
    first:=m.snapshotLiveStatus("CONNECTING",time.Now())
    if len(first.OriginalADCFRanges)!=0 {
        t.Fatal("FRange reported before initial real channel configuration")
    }
    m.liveBin=spool
    status:=m.snapshotLiveStatus("RECORDING",time.Now())
    if len(status.OriginalADCFRanges)!=8 ||
       math.Float32bits(status.OriginalADCFRanges[0])!=originalFRangex32 {
        t.Fatal("original 8-channel FRange not reported from the verified spool")
    }
}

func TestNativeFRangexRejectsMissingZeroAndChangingConfiguration(t *testing.T) {
    missing:=&RegisterImage{}
    if _,_,e:=makeGain(missing);e==nil {
        t.Fatal("unknown FRange silently replaced by 1.0")
    }
    invalid:=frangeTestImage(t,0)
    if _,_,e:=makeGain(invalid);e==nil {
        t.Fatal("zero FRange silently accepted as physical ADC calibration")
    }
    image:=frangeTestImage(t,2.5)
    gains,sens,e:=makeGain(image)
    if e!=nil {t.Fatal(e)}
    if e=validGainAfterBlocks(image,gains,sens);e!=nil {t.Fatal(e)}
    changed:=frangeTestImage(t,3.0)
    if e=validGainAfterBlocks(changed,gains,sens);e==nil {
        t.Fatal("changed FRange silently mixed into calibrated recording")
    }
}
