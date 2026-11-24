package main

import (
	"archive/zip"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func sourceEpochTestMonitor(t *testing.T) *Monitor {
	t.Helper()
	m, e := NewMonitor(filepath.Join(t.TempDir(), "TEST_DISPLAY_EPOCH"), "LIVE_TASK2", "127.0.0.1")
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { m.CloseFiles() })
	m.liveProgressEnabled = true
	m.sourceTCP = &sourceTCPLedger{}
	m.sourceOriginalRXGate = newSourceOriginalReceiveGate()
	m.sourceOriginalTask2Stage = newSourceOriginalTask2Lifecycle()
	sourceEpochTestBegin(t, m)
	return m
}

func sourceEpochTestBegin(t *testing.T, m *Monitor) {
	t.Helper()
	if err := m.sourceTCP.begin(m); err != nil {
		t.Fatal(err)
	}
	m.sourceOriginalTask2Stage.onConnected(m.summary.SourceNonemptyParameters)
}

func sourceEpochTestFeed(t *testing.T, m *Monitor, raw []byte) {
	t.Helper()
	if err := m.ProcessChunk(raw, time.Now()); err != nil {
		t.Fatal(err)
	}
}

func sourceEpochTestSample(typ, channel, rate, index uint32, value float32) []byte {
	raw := makeSample(typ, channel, rate, index)
	for i := 28; i < len(raw); i += 4 {
		binary.LittleEndian.PutUint32(raw[i:], math.Float32bits(value))
	}
	return raw
}

func sourceEpochTestRequest(t *testing.T, m *Monitor, id, channel, tag int) sourceLongWindowRequest {
	t.Helper()
	c := &m.sourceOriginalStorage.channels[channel-1]
	n, e := sourceLongWindowLength(c.sampleRate, tag)
	if e != nil {
		t.Fatal(e)
	}
	width := sourceOriginalElementWidth(channel - 1)
	return sourceLongWindowRequest{
		Schema: sourceLongWindowRequestSchema, SessionID: filepath.Base(m.dir),
		RequestID: fmt.Sprintf("%032x", id), ADC: channel, HTag: tag, Samples: n,
		CaptureEnd: c.rxPos, SampleRateHz: c.sampleRate, DeviceEnd: c.nextDeviceIndex,
		SampleWidth: width, SourceRangeState: c.rangeState,
		SourceEpoch: m.sourceOriginalStorage.displayEpoch(channel - 1),
	}
}

func sourceEpochTestService(t *testing.T, m *Monitor, req sourceLongWindowRequest) error {
	t.Helper()
	raw, err := json.Marshal(req)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(m.dir, sourceLongWindowRequestName), raw, 0600); err != nil {
		t.Fatal(err)
	}
	return m.handleSourceLongWindowRequest(time.Now())
}

func sourceEpochTestResult(t *testing.T, m *Monitor, req sourceLongWindowRequest) []byte {
	t.Helper()
	if e := sourceEpochTestService(t, m, req); e != nil {
		t.Fatal(e)
	}
	z, e := zip.OpenReader(filepath.Join(m.dir, sourceLongWindowResultName))
	if e != nil {
		t.Fatal(e)
	}
	defer z.Close()
	var result sourceLongWindowResult
	var data []byte
	for _, entry := range z.File {
		f, e := entry.Open()
		if e != nil {
			t.Fatal(e)
		}
		bytes, e := io.ReadAll(f)
		f.Close()
		if e != nil {
			t.Fatal(e)
		}
		if entry.Name == "MANIFEST.json" {
			if e := json.Unmarshal(bytes, &result); e != nil {
				t.Fatal(e)
			}
		} else {
			data = bytes
		}
	}
	if result.RequestID != req.RequestID || !reflect.DeepEqual(result.SourceEpoch, req.SourceEpoch) ||
		len(data) != int(req.Samples)*req.SampleWidth {
		t.Fatalf("response did not verify current epoch and exact window: %+v data bytes=%d", result, len(data))
	}
	return data
}

func TestSourceDisplayEpochRecoversAfterSelectedRateAndRejectsPreviousEqualRate(t *testing.T) {
	m := sourceEpochTestMonitor(t)
	m.sourceTask2TX = newSourceLiveTask2TX()
	m.liveBin = &LiveBinSpool{} // exercise rate transition export guard without writing a BIN
	feed := func(raw []byte) { sourceEpochTestFeed(t, m, raw) }
	feed(task2Status0Param(0).Raw)
	feed(sourceEpochTestSample(typeADC, 0, 65536, 0, 1))
	original := sourceEpochTestRequest(t, m, 1, 1, 13)
	if original.SourceEpoch == nil || original.SourceEpoch.StartPos != 0 {
		t.Fatalf("unexpected initial proof %+v", original.SourceEpoch)
	}
	sourceEpochTestResult(t, m, original)
	if e := m.sourceTask2TX.takeOperatorLine(m, "RATE 8192"); e != nil {
		t.Fatal(e)
	}
	if m.sourceOriginalStorage.displayEpoch(0) != nil {
		t.Fatal("selected Fs change left a previous display window available")
	}
	// This stale-rate packet is forensic RAW only.
	feed(sourceEpochTestSample(typeADC, 0, 65536, 256, 100))
	feed(sourceEpochTestSample(typeADC, 0, 8192, 512, 2))
	if !m.summary.SourceRateTransition || isSafeCaptureForExport(m.Snapshot()) == nil {
		t.Fatal("graph recovery must not allow mixed-rate export")
	}
	req := sourceEpochTestRequest(t, m, 2, 1, 13)
	if req.SourceEpoch == nil || req.SourceEpoch.StartPos != 256 {
		t.Fatalf("rate switch lacks a fresh epoch: %+v", req.SourceEpoch)
	}
	if got := math.Float32frombits(binary.LittleEndian.Uint32(sourceEpochTestResult(t, m, req))); got != 2 {
		t.Fatal("old-rate sample entered the recovered window")
	}
	cross := sourceEpochTestRequest(t, m, 3, 1, 8) // 409 samples; only 256 belong to this epoch
	if e := sourceEpochTestService(t, m, cross); e == nil {
		t.Fatal("accepted a window that crossed the rate boundary")
	}
	legacy := req
	legacy.RequestID = fmt.Sprintf("%032x", 4)
	legacy.SourceEpoch = nil
	if e := sourceEpochTestService(t, m, legacy); e == nil {
		t.Fatal("mixed-rate status accepted an epochless request")
	}
	if e := m.sourceTask2TX.takeOperatorLine(m, "RATE 65536"); e != nil {
		t.Fatal(e)
	}
	feed(sourceEpochTestSample(typeADC, 0, 65536, 768, 3))
	back := sourceEpochTestRequest(t, m, 5, 1, 13)
	if back.SourceEpoch == nil || back.SourceEpoch.ContinuityGeneration <= req.SourceEpoch.ContinuityGeneration {
		t.Fatal("A→B→A Fs change reused a prior generation")
	}
	wrong := back
	wrong.SourceEpoch = original.SourceEpoch
	if e := sourceEpochTestService(t, m, wrong); e == nil {
		t.Fatal("first A epoch accepted with second A cursors")
	}
	back.RequestID = fmt.Sprintf("%032x", 6)
	if got := math.Float32frombits(binary.LittleEndian.Uint32(sourceEpochTestResult(t, m, back))); got != 3 {
		t.Fatal("new A epoch did not recover")
	}
	if m.sourceSentBytes() != 0 {
		t.Fatal("local fixture or graph invoked a hardware write")
	}
}

func TestSourceDisplayEpochReconnectExcludesMatchingOldAndPrePARAMHistory(t *testing.T) {
	m := sourceEpochTestMonitor(t)
	feed := func(raw []byte) { sourceEpochTestFeed(t, m, raw) }
	feed(task2Status0Param(0).Raw)
	feed(sourceEpochTestSample(typeADC, 0, 65536, 0, 1))
	feed(sourceEpochTestSample(typeTach, 8, 65536, 0, 1))
	old := sourceEpochTestRequest(t, m, 1, 1, 13)
	m.sourceOriginalTask2Stage.onDisconnected("REMOTE_DISCONNECTED")
	m.sourceTCP.finish(m, "REMOTE_DISCONNECTED")
	sourceEpochTestBegin(t, m)
	// Device indices and Fs align exactly across the reconnect; neither one
	// is adequate proof. These are deliberately pre-PARAM packets.
	feed(sourceEpochTestSample(typeADC, 0, 65536, 256, 2))
	feed(sourceEpochTestSample(typeTach, 8, 65536, 64, 2))
	for _, index := range []int{0, 8} {
		if m.sourceOriginalStorage.displayEpoch(index) != nil {
			t.Fatal("old or pre-PARAM storage exposed after reconnect")
		}
	}
	pre := sourceEpochTestRequest(t, m, 2, 1, 13)
	if e := sourceEpochTestService(t, m, pre); e == nil {
		t.Fatal("request accepted before re-latch")
	}
	feed(task2Status0Param(0).Raw)
	if m.sourceOriginalStorage.displayEpoch(0) != nil {
		t.Fatal("pre-PARAM storage exposed by re-latch")
	}
	feed(sourceEpochTestSample(typeADC, 0, 65536, 512, 3))
	tach := sourceEpochTestSample(typeTach, 8, 65536, 128, 1024)
	feed(tach)
	for i, ch := range []int{1, 9} {
		req := sourceEpochTestRequest(t, m, 3+i, ch, 13)
		wantStart := uint64(512) // ADC: 2 × 256 samples; TACH: 2 × 64 × 4 byte elements.
		if req.SourceEpoch == nil || req.SourceEpoch.SocketAttempt != 2 ||
			req.SourceEpoch.StartPos != wantStart {
			t.Fatalf("channel %d incorrect reconnect proof: %+v", ch, req.SourceEpoch)
		}
		data := sourceEpochTestResult(t, m, req)
		if ch == 1 && math.Float32frombits(binary.LittleEndian.Uint32(data)) != 3 ||
			ch == 9 && !bytes.Equal(data, tach[len(tach)-len(data):]) {
			t.Fatal("reconnect returned prior data")
		}
	}
	stale := sourceEpochTestRequest(t, m, 5, 1, 13)
	stale.SourceEpoch = old.SourceEpoch
	if e := sourceEpochTestService(t, m, stale); e == nil {
		t.Fatal("same-rate request accepted with previous socket proof")
	}
	if !m.summary.SourceTCPMultiSocket || isSafeCaptureForExport(m.Snapshot()) == nil {
		t.Fatal("graph recovery must not allow multi-socket export")
	}
}

func TestSourceDisplayEpochRetainsDenialAndNonfiniteInterlocks(t *testing.T) {
	for _, fault := range []string{"denial", "nonfinite"} {
		t.Run(fault, func(t *testing.T) {
			m := sourceEpochTestMonitor(t)
			feed := func(raw []byte) { sourceEpochTestFeed(t, m, raw) }
			feed(task2Status0Param(0).Raw)
			feed(sourceEpochTestSample(typeADC, 0, 65536, 0, 1))
			if fault == "denial" {
				if e := m.ProcessChunk(sourceReply(typeDenied), time.Now()); e == nil {
					t.Fatal("original denial did not abort current socket")
				}
			} else {
				feed(sourceEpochTestSample(typeADC, 0, 65536, 256, float32(math.NaN())))
			}
			m.sourceOriginalTask2Stage.onDisconnected("REMOTE_DISCONNECTED")
			m.sourceTCP.finish(m, "REMOTE_DISCONNECTED")
			sourceEpochTestBegin(t, m)
			feed(task2Status0Param(0).Raw)
			feed(sourceEpochTestSample(typeADC, 0, 65536, 512, 3))
			req := sourceEpochTestRequest(t, m, 1, 1, 13)
			if req.SourceEpoch == nil || req.SourceEpoch.SocketAttempt != 2 {
				t.Fatal("interlock fixture did not reach an otherwise fresh socket")
			}
			if e := sourceEpochTestService(t, m, req); e == nil {
				t.Fatal("fresh epoch bypassed a historical fault interlock")
			}
			if _, e := os.Stat(filepath.Join(m.dir, sourceLongWindowResultName)); !os.IsNotExist(e) {
				t.Fatalf("interlock wrote a source result despite %s: %v", fault, e)
			}
		})
	}
}

func TestSourceDisplayEpochTachOnlyTransitionScopesWindow(t *testing.T) {
	m := sourceEpochTestMonitor(t)
	m.sourceTask2TX = newSourceLiveTask2TX()
	sourceEpochTestFeed(t, m, task2Status0Param(0).Raw)
	sourceEpochTestFeed(t, m, sourceEpochTestSample(typeTach, 8, 65536, 0, 1))
	if err := m.sourceTask2TX.takeOperatorLine(m, "RATE 8192"); err != nil {
		t.Fatal(err)
	}
	sourceEpochTestFeed(t, m, sourceEpochTestSample(typeTach, 8, 8192, 64, 2))
	if !m.summary.SourceRateTransition || !m.sourceRateTransitionDetected {
		t.Fatal("admitted rate transition was missed without an ADC packet")
	}
	req := sourceEpochTestRequest(t, m, 7, 9, 13) // 1ms at 8192 Hz -> 8 bytes
	answer := sourceEpochTestResult(t, m, req)
	if req.SourceEpoch.StartPos != 256 || len(answer) != 8 ||
		binary.LittleEndian.Uint32(answer) != math.Float32bits(2) {
		t.Fatalf("typed TACH epoch did not isolate new-rate bytes: %v", answer)
	}
}
