package main

// Verified directly against PRIVATE _Unit125.pas:008080EB..00808339 and
// _Unit115.pas:007D1B08/007D2398, with IDP+SQLite address crosschecks.
// The fixed packet sizes 1052/284 are common capture examples only.
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

func sourceTestSampleFrame(t uint32,ch int,index,rate uint32,values []float32) []byte {
  out:=make([]byte,28+4*len(values))
  binary.LittleEndian.PutUint32(out[:4],t)
  binary.LittleEndian.PutUint32(out[4:8],uint32(len(out)))
  binary.LittleEndian.PutUint32(out[12:16],index)
  binary.LittleEndian.PutUint32(out[20:24],uint32(ch))
  binary.LittleEndian.PutUint32(out[24:28],rate)
  for i,v:=range values {
    binary.LittleEndian.PutUint32(out[28+4*i:],math.Float32bits(v))
  }
  return out
}

func TestOriginalVariableSamplePacketSizeAndFragmentedTCP(t *testing.T) {
  m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_source_variable"),
    "OFFLINE_REPLAY","")
  if e!=nil {t.Fatal(e)}
  defer m.CloseFiles()
  adc:=sourceTestSampleFrame(typeADC,0,0xFFFFFFF0,65536,
    []float32{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17})
  tach:=sourceTestSampleFrame(typeTach,8,100,512,
    []float32{1,2,3,4,5,6,7})
  if len(adc)!=96 || len(tach)!=56 {
    t.Fatal("source frame layout changed")
  }
  both:=append(adc,tach...)
  // A real TCP socket can split frame headers and samples anywhere.
  for _,part:=range [][]byte{both[:3],both[3:26],both[26:101],both[101:]} {
    if e:=m.ProcessChunk(part,time.Now());e!=nil {t.Fatal(e)}
  }
  if m.summary.InvalidFrames!=0 || m.summary.TotalFrames!=2 ||
     m.summary.Channels[0].Samples!=17 ||
     m.summary.Channels[8].Samples!=7 {
    t.Fatalf("source-length variable TCP receive rejected: %+v",m.Snapshot())
  }
  a:=m.sourceOriginalStorage.receipt().Channels[0]
  x:=m.sourceOriginalStorage.receipt().Channels[8]
  if a.RxPos!=17 || *a.NextDeviceIndex!=1 ||
     x.RxPos!=28 || *x.NextDeviceIndex!=107 ||
     a.Domain!=sourceStorageUnscaledADC || x.Domain!=sourceStorageTachBytes {
    t.Fatalf("source wire words vs ring elements confused: ADC=%+v TACH=%+v",a,x)
  }
  data,e:=m.sourceOriginalStorage.window(0,0,17)
  if e!=nil || !bytes.Equal(data,adc[28:]) {
    t.Fatal("original ADC variable size bits were changed",e)
  }
  data,e=m.sourceOriginalStorage.window(8,0,28)
  if e!=nil || !bytes.Equal(data,tach[28:]) {
    t.Fatal("original TACH byte payload was truncated/converted",e)
  }
}

func TestOriginalVariableChunkCrossesFloat32AndTACHRingWrap(t *testing.T) {
  r:=newSourceOriginalStorageRing()
  for _,ch:=range []int{0,8} {
    width:=sourceOriginalElementWidth(ch)
    c:=&r.channels[ch]
    c.rxPos=sourceOriginalStorageSamples-3
    c.validPos=c.rxPos
    h:=SampleHeader{Channel:ch,Rate:65536,Index:0xfffffff9,Samples:7}
    payload:=make([]byte,28)
    for i:=range payload {payload[i]=byte(i+1)}
    domain:=sourceStorageUnscaledADC
    if ch==8 {domain=sourceStorageTachBytes}
    if e:=r.appendFrame(h,payload,domain);e!=nil {t.Fatal(e)}
    count:=uint64(7)
    if ch==8 {count=28}
    read,e:=r.window(ch,uint64(sourceOriginalStorageSamples-3),count)
    if e!=nil || !bytes.Equal(read,payload) {
      t.Fatalf("source ring wrap width=%d: %v",width,e)
    }
    if *r.receipt().Channels[ch].NextDeviceIndex!=0 {
      t.Fatal("device uint32 wrap confused with ring storage cursor")
    }
  }
}

func TestOriginalEmptySourcePacketDoesNotCreateFakeSamples(t *testing.T) {
  m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_empty_source"),"OFFLINE_REPLAY","")
  if e!=nil {t.Fatal(e)}
  defer m.CloseFiles()
  empty:=sourceTestSampleFrame(typeADC,0,0,65536,nil)
  if len(empty)!=28 {t.Fatal("zero-payload header")}
  if e=m.ProcessChunk(empty,time.Now());e!=nil {t.Fatal(e)}
  if m.summary.TotalFrames!=1 || m.summary.Channels[0].Samples!=0 ||
     m.sourceOriginalStorage.receipt().Channels[0].Available!=0 {
     t.Fatal("original zero-size source header must not fabricate signal")
  }
}

func TestOriginalVariableCalibratedADCSpoolMatchesPreviewAndRing(t *testing.T) {
  dir:=t.TempDir()
  f,e:=os.Create(filepath.Join(dir,"real.f32"))
  if e!=nil {t.Fatal(e)}
  defer f.Close()
  ring:=newSourceOriginalStorageRing()
  preview:=newLivePreviewBuffer()
  spool:=&LiveBinSpool{begun:true,sourceOriginalStorage:ring,preview:preview}
  spool.files[0]=f
  spool.digest[0]=sha256.New()
  spool.gain[0]=2.0
  payload:=sourceTestSampleFrame(typeADC,0,123,65536,
    []float32{1.25,2.5,3.75,5,6.25,7.5,8.75})
  h,e:=decodeSampleHeader(Frame{Type:typeADC,Raw:payload})
  if e!=nil {t.Fatal(e)}
  if e:=spool.adcFrame(Frame{Type:typeADC,Raw:payload},h);e!=nil {t.Fatal(e)}
  if e=f.Sync();e!=nil {t.Fatal(e)}
  disk,e:=os.ReadFile(f.Name());if e!=nil {t.Fatal(e)}
  memory,e:=ring.window(0,0,7);if e!=nil {t.Fatal(e)}
  view,n,_:=preview.channelBytes(0)
  if n!=7 || !bytes.Equal(memory,disk) || !bytes.Equal(view,disk) {
    t.Fatal("variable source ADC was changed while writing to spool/preview/ring")
  }
  if math.Float32frombits(binary.LittleEndian.Uint32(disk))!=2.5 {
    t.Fatal("gain applied a wrong number of times")
  }
}
