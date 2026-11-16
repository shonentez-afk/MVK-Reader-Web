package main

import (
    "path/filepath"
    "testing"
    "time"
)

// Original 10-channel TMVKThread includes both tachometers; a gap in a
// 64-sample TACH frame must be reflected in live Go JSON and the Core/Qt
// red data-quality indicator, not just in completed offline RAW audit.
func TestTachIndexDiscontinuityEntersNativeLiveStatus(t *testing.T) {
    dir:=filepath.Join(t.TempDir(),"passive_capture")
    m,err:=NewMonitor(dir,"OFFLINE_REPLAY","192.0.2.84")
    if err!=nil {t.Fatal(err)}
    defer m.CloseFiles()
    now:=time.Date(2026,11,16,8,30,0,0,time.UTC)
    for i,frame:=range []Frame{
        syntheticFrame(8,0,1.25),
        syntheticFrame(8,128,1.25), // expected index64, missing one packet
        syntheticFrame(9,0,2.25),
        syntheticFrame(9,64,2.25),
    } {
        if err:=m.ProcessChunk(frame.Raw,now.Add(time.Duration(i)*time.Millisecond));err!=nil {
            t.Fatal(err)
        }
    }
    summary:=m.Snapshot()
    if summary.Channels[8].SequenceDiscontinuities!=1 {
        t.Fatalf("TACH1 gap not counted: %+v",summary.Channels[8])
    }
    if summary.Channels[9].SequenceDiscontinuities!=0 {
        t.Fatalf("TACH2 false gap: %+v",summary.Channels[9])
    }
    status:=m.snapshotLiveStatus("RECORDING",now.Add(5*time.Millisecond))
    if len(status.Channels)!=10 ||
       status.Channels[8].SequenceDiscontinuities!=1 ||
       status.Channels[9].SequenceDiscontinuities!=0 {
        t.Fatal("Go live_status omitted original tachometer stream gap")
    }
    if status.InvalidFrames!=0 || status.CaptureOnly ||
       summary.Channels[8].Samples!=128 {
        t.Fatal("forensic RAW was wrongly discarded by a TACH gap")
    }
}
