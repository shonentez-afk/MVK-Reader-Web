package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func makeNativeMonitorForFixture(t *testing.T, raw []byte, endReason string) (string, Summary) {
	t.Helper()
	dir := filepath.Join(t.TempDir(), "RUN")
	m, e := NewMonitor(dir, "OFFLINE_REPLAY", "")
	if e != nil {
		t.Fatal(e)
	}
	for pos := 0; pos < len(raw); {
		n := pos + 1791
		if n > len(raw) {
			n = len(raw)
		}
		if e = m.ProcessChunk(raw[pos:n], time.Now().UTC()); e != nil {
			t.Fatal(e)
		}
		pos = n
	}
	r, _, e := m.Finalize(endReason)
	if e != nil {
		t.Fatal(e)
	}
	return dir, r
}

func fixtureBytes(frames []Frame) []byte {
	var b bytes.Buffer
	for _, f := range frames {
		b.Write(f.Raw)
	}
	return b.Bytes()
}

func TestStage108MonitorToAutomaticEightBIN(t *testing.T) {
	dir, s := makeNativeMonitorForFixture(t, fixtureBytes(makeFixture()), "REPLAY_EOF")
	st, e := completeStage108Export(dir, s, nil, true, 7*60, nil)
	if e != nil {
		t.Fatal(e)
	}
	if st.State != "EXPORTED" || st.ValuesRows != 1 || st.ADCFiles != 8 || st.AUXUpdates != 1 || st.TerminalBytesExcluded != 0 {
		t.Fatalf("unexpected embedded export status %+v", st)
	}
	var audit ExportReport
	data, e := os.ReadFile(filepath.Join(dir, reconstructedDirName, "EXPORT_AUDIT.json"))
	if e != nil {
		t.Fatal(e)
	}
	if e = json.Unmarshal(data, &audit); e != nil {
		t.Fatal(e)
	}
	if audit.SourceRawSHA != s.RawSHA256 || audit.FrameCount != s.TotalFrames || audit.AUX != s.Aux4700 {
		t.Fatalf("audit not tied to monitor %+v", audit)
	}
	for ch := 0; ch < 8; ch++ {
		if audit.Channels[ch].Samples != 512 {
			t.Fatalf("ADC%d samples", ch+1)
		}
	}
	check, e := os.ReadFile(filepath.Join(dir, "STAGE108_EXPORT_STATUS.json"))
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Contains(check, []byte("EXPORTED")) {
		t.Fatalf("status missing %q", check)
	}
}

func TestStage108DeliberateIncompleteTerminalFrameIsExcludedButRawRetained(t *testing.T) {
	full := fixtureBytes(makeFixture())
	partial := append(append([]byte{}, full...), []byte{0xDC, 0x0A, 0x80, 0xFF, 0x1C}...)
	dir, s := makeNativeMonitorForFixture(t, partial, "DURATION_REACHED")
	if s.TailBytes != 5 || s.Result != "VALID_FRAMES_WITH_INCOMPLETE_LAST_FRAME" {
		t.Fatalf("monitor tail %d status %s", s.TailBytes, s.Result)
	}
	if _, e := export(filepath.Join(dir, "incoming.raw"), filepath.Join(dir, "frames.csv"), filepath.Join(dir, "summary.json"), filepath.Join(dir, "STRICT"), 7*60); e == nil {
		t.Fatal("Stage107 strict mode must reject incomplete frame")
	}
	st, e := completeStage108Export(dir, s, nil, true, 7*60, nil)
	if e != nil {
		t.Fatal(e)
	}
	if st.State != "EXPORTED" || st.TerminalBytesExcluded != 5 {
		t.Fatalf("unexpected terminal exclusion %+v", st)
	}
	if st.OriginalRawSHA256 != s.RawSHA256 {
		t.Fatal("RAW hash changed")
	}
	b, e := os.ReadFile(filepath.Join(dir, "incoming.raw"))
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(b, partial) {
		t.Fatal("original RAW must remain complete and untouched")
	}
}

func TestStage108RejectsRawChecksumMismatchWithoutPublishing(t *testing.T) {
	dir, s := makeNativeMonitorForFixture(t, fixtureBytes(makeFixture()), "REPLAY_EOF")
	p := filepath.Join(dir, "incoming.raw")
	f, e := os.OpenFile(p, os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = f.WriteAt([]byte{0xAE}, 280); e != nil {
		t.Fatal(e)
	}
	f.Close()
	st, e := completeStage108Export(dir, s, nil, true, 7*60, nil)
	if e == nil || st.State != "FAILED_CLOSED" {
		t.Fatalf("expected checksum refusal: %+v %v", st, e)
	}
	if _, e := os.Stat(filepath.Join(dir, reconstructedDirName)); !os.IsNotExist(e) {
		t.Fatal("failed export must not publish directory")
	}
}

func TestStage108RefusesCaptureOnlyAndKeepsRaw(t *testing.T) {
	b := append(fixtureBytes(makeFixture()), []byte{0xEA, 0xFE, 0xED, 0xCC, 8, 0, 0, 0}...)
	dir, s := makeNativeMonitorForFixture(t, b, "REPLAY_EOF")
	if !s.CaptureOnly || s.InvalidFrames == 0 {
		t.Fatalf("expected capture-only, got %+v", s)
	}
	st, e := completeStage108Export(dir, s, nil, true, 7*60, nil)
	if e == nil || st.State != "REFUSED" {
		t.Fatalf("should reject invalid frames: %+v %v", st, e)
	}
	if _, e := os.Stat(filepath.Join(dir, "incoming.raw")); e != nil {
		t.Fatal("forensic RAW missing")
	}
}

func TestStage108RejectsUnexpectedCaptureStop(t *testing.T) {
	dir, s := makeNativeMonitorForFixture(t, fixtureBytes(makeFixture()), "REMOTE_DISCONNECTED")
	st, e := completeStage108Export(dir, s, nil, true, 0, nil)
	if e == nil || st.State != "REFUSED" {
		t.Fatalf("should refuse unexpected disconnect %+v %v", st, e)
	}
}

func TestStage108RejectsManipulatedTailSummary(t *testing.T) {
	full := fixtureBytes(makeFixture())
	dir, s := makeNativeMonitorForFixture(t, append(full, []byte{1, 2, 3}...), "DURATION_REACHED")
	p := filepath.Join(dir, "summary.json")
	b, e := os.ReadFile(p)
	if e != nil {
		t.Fatal(e)
	}
	var ss Summary
	if e = json.Unmarshal(b, &ss); e != nil {
		t.Fatal(e)
	}
	ss.TailBytes = 2
	bb, _ := json.Marshal(ss)
	if e = os.WriteFile(p, bb, 0600); e != nil {
		t.Fatal(e)
	}
	st, e := completeStage108Export(dir, s, nil, true, 7*60, nil)
	if e == nil || st.State != "FAILED_CLOSED" {
		t.Fatalf("unexpected tail accepted %+v %v", st, e)
	}
}

func TestStage108PreservesCompletedOutputOnRepeatAttempt(t *testing.T) {
	dir, s := makeNativeMonitorForFixture(t, fixtureBytes(makeFixture()), "REPLAY_EOF")
	_, e := completeStage108Export(dir, s, nil, true, 0, nil)
	if e != nil {
		t.Fatal(e)
	}
	// Stage108's operator status file is itself O_EXCL; the primary safeguard
	// is exported destination already existing and immutable.
	_, e = exportWithPolicy(filepath.Join(dir, "incoming.raw"), filepath.Join(dir, "frames.csv"), filepath.Join(dir, "summary.json"), filepath.Join(dir, reconstructedDirName), 0, true)
	if e == nil || !strings.Contains(e.Error(), "exists") {
		t.Fatalf("overwrite not blocked: %v", e)
	}
}

func TestStage108DisabledDoesNotPublishOutputs(t *testing.T) {
	dir, s := makeNativeMonitorForFixture(t, fixtureBytes(makeFixture()), "REPLAY_EOF")
	st, e := completeStage108Export(dir, s, nil, false, 0, nil)
	if e != nil || st.State != "DISABLED" {
		t.Fatalf("disabled result %+v %v", st, e)
	}
	if _, e := os.Stat(filepath.Join(dir, reconstructedDirName)); !os.IsNotExist(e) {
		t.Fatal("export produced when disabled")
	}
}

func TestStage108TimezoneResolutionAndBadOffsets(t *testing.T) {
	pc := time.Date(2026, 10, 29, 11, 0, 0, 0, time.FixedZone("factory", 7*3600))
	for input, want := range map[string]int{"auto": 420, "+07:00": 420, "-12:00": -720, "+14:00": 840, "+00:00": 0} {
		got, e := parseOffset(input, pc)
		if e != nil || got != want {
			t.Fatalf("parse %s=%d/%v expected %d", input, got, e, want)
		}
	}
	for _, input := range []string{"+14:30", "-13:00", "+07:60", "UTC", "-12:01"} {
		if _, e := parseOffset(input, pc); e == nil {
			t.Errorf("accepted offset %q", input)
		}
	}
}

func TestStage108LiveLoopbackCaptureZeroClientPayloadAndExports(t *testing.T) {
	if testing.Short() {
		t.Skip("1-second local TCP integration")
	}
	ln, e := net.Listen("tcp4", "127.0.0.1:0")
	if e != nil {
		t.Fatal(e)
	}
	defer ln.Close()
	b := fixtureBytes(makeFixture())
	devicePayload := make(chan []byte, 1)
	deviceErrors := make(chan error, 1)
	go func() {
		c, e := ln.Accept()
		if e != nil {
			deviceErrors <- e
			return
		}
		defer c.Close()
		if _, e = c.Write(b); e != nil {
			deviceErrors <- e
			return
		}
		c.SetReadDeadline(time.Now().Add(1300 * time.Millisecond))
		dat := make([]byte, 128)
		n, e := c.Read(dat)
		if e != nil && e != io.EOF {
			if ne, ok := e.(net.Error); !ok || !ne.Timeout() {
				deviceErrors <- e
				return
			}
		}
		devicePayload <- dat[:n]
	}()
	dir := filepath.Join(t.TempDir(), "RUN")
	m, e := NewMonitor(dir, "LIVE_READ_ONLY", "127.0.0.1")
	if e != nil {
		t.Fatal(e)
	}
	if e = m.EnableLiveBinSpool(); e != nil {
		t.Fatal(e)
	}
	nic := &LocalNIC{Name: "lo", Index: 1, IP: net.ParseIP("127.0.0.1")}
	reason, e := liveCaptureAddressOnNIC(context.Background(), m, ln.Addr().String(), 1, 5<<20, nic)
	if e != nil {
		t.Fatal(e)
	}
	if reason != "DURATION_REACHED" {
		t.Fatalf("expected duration stop, got %s", reason)
	}
	s, _, e := m.Finalize(reason)
	if e != nil {
		t.Fatal(e)
	}
	st, e := completeStage108Export(dir, s, nil, true, 0, m.liveBin)
	if e != nil {
		t.Fatalf("live end-to-end: %v status=%+v", e, st)
	}
	if st.ADCFiles != 8 || st.ValuesRows != 1 {
		t.Fatalf("live data missing: %+v", st)
	}
	select {
	case payload := <-devicePayload:
		if len(payload) > 0 {
			t.Fatalf("device received %d client app bytes", len(payload))
		}
	case e := <-deviceErrors:
		t.Fatalf("device socket: %v", e)
	case <-time.After(3 * time.Second):
		t.Fatal("TCP server did not complete")
	}
	got, err := os.ReadFile(filepath.Join(dir, "incoming.raw"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(b, got) {
		t.Fatalf("TCP capture byte mismatch %d vs %d", len(b), len(got))
	}
	fmt.Printf("loopback stage108 live: %d received bytes, zero transmitted application payload, exported 8 calibrated BIN\n", len(got))
}

func TestStage108StreamingWritesBeforeCaptureIsFinished(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "LIVE")
	m, e := NewMonitor(dir, "LIVE_READ_ONLY", "192.0.2.84")
	if e != nil {
		t.Fatal(e)
	}
	if e = m.EnableLiveBinSpool(); e != nil {
		t.Fatal(e)
	}
	b := fixtureBytes(makeFixture())
	if e = m.ProcessChunk(b, time.Now().UTC()); e != nil {
		t.Fatal(e)
	}
	partial := filepath.Join(dir, ".stage108_live_calibrated_pending", "ADC1.bin.partial")
	data, e := os.ReadFile(partial)
	if e != nil {
		t.Fatal(e)
	}
	if len(data) != 2048 {
		t.Fatalf("streaming BIN should already contain 512 calibrated samples, got %d bytes", len(data))
	}
	want := float32(0.125) * float32(510)
	got := math.Float32frombits(binary.LittleEndian.Uint32(data[:4]))
	if got != want {
		t.Fatalf("live spool calibration %g != %g", got, want)
	}
	if _, e = os.Stat(filepath.Join(dir, reconstructedDirName)); !os.IsNotExist(e) {
		t.Fatal("completed BIN published before session finish")
	}
	s, _, e := m.Finalize("DURATION_REACHED")
	if e != nil {
		t.Fatal(e)
	}
	stat, e := completeStage108Export(dir, s, nil, true, 0, m.liveBin)
	if e != nil || stat.State != "EXPORTED" || !stat.StreamingBINVerified {
		t.Fatalf("streaming publish status=%+v error=%v", stat, e)
	}
	if _, e = os.Stat(partial); !os.IsNotExist(e) {
		t.Fatal("temporary BIN persisted after publication")
	}
}

func TestStage108RefusesCorruptedPhysicalStreamingSpool(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "LIVE")
	m, e := NewMonitor(dir, "LIVE_READ_ONLY", "192.0.2.84")
	if e != nil {
		t.Fatal(e)
	}
	if e = m.EnableLiveBinSpool(); e != nil {
		t.Fatal(e)
	}
	if e = m.ProcessChunk(fixtureBytes(makeFixture()), time.Now().UTC()); e != nil {
		t.Fatal(e)
	}
	s, _, e := m.Finalize("DURATION_REACHED")
	if e != nil {
		t.Fatal(e)
	}
	p := filepath.Join(dir, ".stage108_live_calibrated_pending", "ADC1.bin.partial")
	f, e := os.OpenFile(p, os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = f.WriteAt([]byte{0xFD}, 0); e != nil {
		t.Fatal(e)
	}
	if e = f.Close(); e != nil {
		t.Fatal(e)
	}
	status, e := completeStage108Export(dir, s, nil, true, 0, m.liveBin)
	if e == nil || status.State != "FAILED_CLOSED" || status.StreamingBINVerified {
		t.Fatalf("bad spool must refuse, %+v err=%v", status, e)
	}
	if _, e = os.Stat(filepath.Join(dir, reconstructedDirName)); !os.IsNotExist(e) {
		t.Fatal("bad physical spool was marked complete")
	}
	if _, e = os.Stat(filepath.Join(dir, "incoming.raw")); e != nil {
		t.Fatal("forensic RAW lost")
	}
}

func TestStage108StreamingSafelyTrimsOnlyLastIncompleteFrame(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "LIVE")
	m, e := NewMonitor(dir, "LIVE_READ_ONLY", "192.0.2.84")
	if e != nil {
		t.Fatal(e)
	}
	if e = m.EnableLiveBinSpool(); e != nil {
		t.Fatal(e)
	}
	b := append(fixtureBytes(makeFixture()), []byte{0xDC, 0x0A, 0x80, 0xFF, 0x1C, 0x04, 0, 0, 0xAA}...)
	if e = m.ProcessChunk(b, time.Now().UTC()); e != nil {
		t.Fatal(e)
	}
	s, _, e := m.Finalize("DURATION_REACHED")
	if e != nil {
		t.Fatal(e)
	}
	if s.TailBytes != 9 {
		t.Fatalf("expected 9 trailing bytes, got %d", s.TailBytes)
	}
	stat, e := completeStage108Export(dir, s, nil, true, 0, m.liveBin)
	if e != nil || stat.State != "EXPORTED" || stat.TerminalBytesExcluded != 9 || !stat.StreamingBINVerified {
		t.Fatalf("wrong final-tail policy %+v %v", stat, e)
	}
}
