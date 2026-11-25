package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSourceMultipleValuesDescriptorsInOneParam(t *testing.T) {
	m, marks := markFixture(t)
	defer m.CloseFiles()
	exerciseSourceMultipleValuesDescriptors(t, m, marks)
}

// Optional offline fixture from the real Go receiver for Python acceptance.
func TestMultipleValuesDescriptorsCoreFixture(t *testing.T) {
	root := os.Getenv("MVK_PREFIX_FIXTURE_DIR")
	if root == "" {
		t.Skip("cross-language fixture not requested")
	}
	root = filepath.Join(root, "multi_3100")
	if err := os.MkdirAll(root, 0700); err != nil {
		t.Fatal(err)
	}
	run := filepath.Join(root, "TEST_2026-11-16_10-01-00.000")
	m, err := NewMonitor(run, "OFFLINE_REPLAY", "192.0.2.84")
	if err != nil {
		t.Fatal(err)
	}
	defer m.CloseFiles()
	marks, err := newFrameMarkController(root, run)
	if err != nil {
		t.Fatal(err)
	}
	m.frameMarks = marks
	exerciseSourceMultipleValuesDescriptors(t, m, marks)
}

func exerciseSourceMultipleValuesDescriptors(t *testing.T, m *Monitor, marks *frameMarkController) {
	t.Helper()
	m.sourceOriginalTask2Stage = newSourceOriginalTask2Lifecycle()
	m.sourceOriginalTask2Stage.onConnected(0)
	m.sourceOriginalRXGate = newSourceOriginalReceiveGate()
	m.sourceLiveValuesWriter = newSourceLiveValuesWriter(m.dir)
	gate, err := newSourceOriginalParamGateJournal(m.dir)
	if err != nil {
		t.Fatal(err)
	}
	m.sourceParamGate = gate
	queueMark(t, marks, 1, "values_begin")
	frame := makeParam([]RegBlock{
		{Addr: 0x2002, Words: 2, Payload: []byte{0, 0, 0x80, 0x3f}},
		{Addr: 0x3100, Words: 2, Payload: []byte{0, 0, 0, 0x40}},
		{Addr: 0x2002, Words: 2, Payload: []byte{0, 0, 0x40, 0x40}},
		{Addr: 0x3100, Words: 2, Payload: []byte{0, 0, 0x80, 0x40}},
		{Addr: 0x2002, Words: 2, Payload: []byte{0, 0, 0xa0, 0x40}},
	})
	blocks, err := decodeBlocks(frame)
	if err != nil || len(blocks) != 5 {
		t.Fatalf("bad fixture: %v", err)
	}
	// A genuine admitted TACH frame sets its byte latch to 1.
	tach := sourceLiveWriterSample(typeTach, 8, 65536, 0, 0x01010101)
	now := time.Now()
	if err = m.ProcessChunk(tach, now); err != nil {
		t.Fatal(err)
	}
	if err = m.ProcessChunk(frame, now.Add(time.Millisecond)); err != nil {
		t.Fatal(err)
	}
	// Freeze must exclude BOTH descriptors without clearing the RAW copy.
	m.sourceOriginalRXGate.setFreeze(true)
	if err = m.ProcessChunk(frame, now.Add(2*time.Millisecond)); err != nil {
		t.Fatal(err)
	}
	report, _, err := m.Finalize("STOPPED_BY_USER")
	if err != nil {
		t.Fatal(err)
	}
	if report.SourceLiveValuesEventRecords != 2 || report.ValuesTicks != 2 ||
		report.SourceFrozenValuesTicks != 2 || report.InvalidFrames != 0 {
		t.Fatalf("incorrect 0x3100 descriptor counts; written=%d, ticks=%d, frozen=%d, invalid=%d",
			report.SourceLiveValuesEventRecords, report.ValuesTicks, report.SourceFrozenValuesTicks, report.InvalidFrames)
	}
	raw, err := os.ReadFile(filepath.Join(m.dir, "incoming.raw"))
	if err != nil || !bytes.Equal(raw, bytes.Join([][]byte{tach, frame, frame}, nil)) {
		t.Fatalf("RAW not preserved: %v", err)
	}
	body, err := os.ReadFile(filepath.Join(m.dir, "SOURCE_W01_VALUES_3100_RECEIVED.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	lines := bytes.Split(bytes.TrimSpace(body), []byte{10})
	if len(lines) != 2 {
		t.Fatalf("wrong row count: %d", len(lines))
	}
	wantSpec := []string{"0000803f", "00004040"} // Values before each independent trigger, not suffix 5.0.
	wantTach := []string{"01000000", "00000000"} // Reset between triggers.
	wantPayload := []string{"00000040", "00008040"}
	for i, line := range lines {
		var row sourceLiveValuesEvent
		if err = json.Unmarshal(line, &row); err != nil {
			t.Fatal(err)
		}
		if row.FrameIndex != 2 || row.DescriptorIndex != i*2+1 ||
			row.TickIndex != uint64(i) || row.PayloadLEHex != wantPayload[i] {
			t.Fatalf("row identity/payload mismatch: %+v", row)
		}
		var spec, tach string
		for _, field := range row.RawTickEvidence.OrderedFields {
			if field.RawLE == nil {
				continue
			}
			if field.Channel == 1 && field.Group == "SPEC" && field.CellIndex == 0 {
				spec = *field.RawLE
			}
			if field.Channel == 9 && field.Group == "TACH" && field.CellIndex == 5 {
				tach = *field.RawLE
			}
		}
		if spec != wantSpec[i] || tach != wantTach[i] {
			t.Fatalf("row %d snapshot spec=%q TACH=%q", i, spec, tach)
		}
	}
	body, err = os.ReadFile(filepath.Join(m.dir, sourceOriginalParamGateName))
	if err != nil {
		t.Fatal(err)
	}
	lines = bytes.Split(bytes.TrimSpace(body), []byte{10})
	if len(lines) != 2 {
		t.Fatalf("wrong PARAM journal count: %d", len(lines))
	}
	for i, line := range lines {
		var row sourceOriginalParamGateRecord
		if err = json.Unmarshal(line, &row); err != nil {
			t.Fatal(err)
		}
		if row.Values3100DescriptorCount != 2 || !row.Values3100 || row.FreezeUpdate != (i == 1) {
			t.Fatalf("incorrect PARAM journal: %+v", row)
		}
	}
}

// A generalized two-trigger PARAM can happen to be the same size as
// the historical AUX companion. Its local source rows are independent
// of that historical reconstructed report, which must still open.
func TestMultipleValuesDescriptorsPreserveLegacyArchive(t *testing.T) {
	fixture := makeFixture()
	generalized := syntheticParam(76, []RegBlock{
		{Addr: 0x3100, Words: 10, Payload: make([]byte, 20)},
		{Addr: 0x3100, Words: 10, Payload: make([]byte, 20)},
	})
	// Place it just before the actual 76B legacy AUX companion so it
	// cannot consume the pending legacy AUX update.
	fixture = append(fixture[:len(fixture)-1:len(fixture)-1], generalized, fixture[len(fixture)-1])
	raw, frames, summary := writeFixture(t, fixture)
	report, err := export(raw, frames, summary, filepath.Join(t.TempDir(), "output"), 420)
	if err != nil {
		t.Fatal(err)
	}
	if report.ValuesRows != 1 || report.AUX != 1 || len(report.Channels) != 8 {
		t.Fatalf("legacy AUX reconstruction changed: %+v", report)
	}
}
