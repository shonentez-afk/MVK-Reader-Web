package main

// Proof from private _Unit125.pas 00808192..0080823B:
// Device sample rate is an arbitrary received uint32, checked against
// TMVKThread.MvkSampleRate only after reading all payload bytes.
// Native must not tear down a valid Task2 TCP merely because Fs does
// not match any of the five selectable original menu rates.
//
// All tests are synthetic, no industrial hardware or private files.
import (
    "bytes"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalTask2NonMenuWireSampleRateDrainsRAWWithoutSocketFault(t *testing.T){
    dir:=filepath.Join(t.TempDir(),"source_nonmenu_fs")
    m,e:=NewMonitor(dir,"OFFLINE_REPLAY","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalTask2Stage.onConnected(0)
    // Source Task2 SetRate is selected at 65536 in memory.
    original:=task2Status0Param(0).Raw
    for _,fs:=range []uint32{0,12345,44100,65536} {
        sample:=sourceTestSampleFrame(typeADC,0,0,fs,[]float32{1.25})
        original=append(original,sample...)
    }
    if e=m.ProcessChunk(original,time.Now());e!=nil{
        t.Fatalf("valid length non-menu wire Fs incorrectly stopped Task2: %v",e)
    }
    stage:=m.sourceOriginalTask2Stage
    if stage.stage!=1 || m.summary.InvalidFrames!=0 ||
        m.summary.SourceTask2ProtocolExceptions!=0 || m.captureOnly {
        t.Fatalf("raw source Fs mismatch must not be invalid packet: %+v",m.summary)
    }
    gate:=m.sourceOriginalRXGate.receipt().Channels[0]
    if gate.RateSkippedElements!=3 || gate.StoredGateElements!=1 ||
        m.sourceOriginalStorage.receipt().Channels[0].RxPos!=1 ||
        m.summary.TotalFrames!=5 || m.summary.Channels[0].Samples!=4 {
        t.Fatalf("valid raw Fs sample was stored or dropped incorrectly: gate=%+v",gate)
    }
    stage.onDisconnected("STOPPED_BY_USER")
    result,_,e:=m.Finalize("STOPPED_BY_USER")
    if e!=nil{t.Fatal(e)}
    raw,e:=os.ReadFile(filepath.Join(dir,"incoming.raw"))
    if e!=nil || !bytes.Equal(raw,original) {
        t.Fatalf("valid raw sample Fs bytes changed: %v",e)
    }
    if result.CaptureOnly || result.InvalidFrames!=0 ||
        result.SourceTask2ProtocolExceptions!=0 ||
        result.TailBytes!=0 || result.Channels[0].Samples!=4 {
        t.Fatal("unsupported raw Fs misreported as a faulty packet")
    }
}
