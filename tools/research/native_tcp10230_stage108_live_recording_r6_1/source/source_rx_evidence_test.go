package main

// Stage111Z31DG: compare passive Go live counters against PRIVATE Delphi
// _Unit125.pas 0080807B, 008080AC and 00808617 receive semantics.
//
// No outgoing application bytes, no physical instrument, no new Go client.
import (
    "encoding/binary"
    "path/filepath"
    "testing"
    "time"
)

func sourceReply(t uint32) []byte {
    b := make([]byte, 8)
    binary.LittleEndian.PutUint32(b[:4], t)
    binary.LittleEndian.PutUint32(b[4:], 8)
    return b
}

func TestSourceRXNonemptyRegisterAndUnattributedReplies(t *testing.T) {
    // The original TMVKThread only transitions Stage0->1 after a
    // parameter message with at least one valid register descriptor.
    // Pure passive Go can OBSERVE this event, not physically become
    // the Delphi command-writing TMVKThread.
    param := makeParam([]RegBlock{{
        Addr: 0x3100, Words: 2, Payload: []byte{1,2,3,4},
    }})
    stream := append(makeIdentity(), makeSample(typeADC, 0, 65536, 0)...)
    stream = append(stream, param...)
    stream = append(stream, sourceReply(typeAck)...)
    stream = append(stream, sourceReply(typeDenied)...)
    summary, _ := runTestMonitor(t, stream, 7)
    if summary.TotalFrames != 5 || summary.InvalidFrames != 0 ||
            summary.SourceNonemptyParameters != 1 ||
            summary.ACK != 1 || summary.Denials != 1 {
        t.Fatalf("source RX counters incorrect: %+v", summary)
    }
    if !summary.ReadOnly {
        t.Fatal("read-only contract was lost")
    }
}

func TestSourceRXCountersAppearInLiveStatusOnlyFromReceivedFrames(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "TEST_source_received")
    m, err := NewMonitor(dir, "OFFLINE_REPLAY", "10.13.42.84")
    if err != nil { t.Fatal(err) }
    defer m.CloseFiles()
    initial := m.snapshotLiveStatus("CONNECTING", time.Now())
    if initial.SourceRXNonemptyParam != 0 || initial.SourceRXACKObserved != 0 ||
            initial.SourceRXDenials != 0 {
        t.Fatal("no source protocol replies existed before receiving bytes")
    }
    param := makeParam([]RegBlock{{Addr: 0x3100, Words: 2,
        Payload: []byte{0,0,0,0}}})
    for _, b := range [][]byte{
        makeIdentity(), param, sourceReply(typeAck), sourceReply(typeDenied),
    } {
        if err := m.ProcessChunk(b, time.Now()); err != nil {
            t.Fatal(err)
        }
    }
    report := m.snapshotLiveStatus("RECORDING", time.Now())
    if report.SourceRXNonemptyParam != 1 ||
            report.SourceRXACKObserved != 1 || report.SourceRXDenials != 1 ||
            report.TotalFrames != 4 || !report.ReadOnly {
        t.Fatalf("live source RX receipt incorrect: %+v", report)
    }
}
