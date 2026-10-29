package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func le32(b []byte, off int, x uint32)     { binary.LittleEndian.PutUint32(b[off:off+4], x) }
func leFloat(b []byte, off int, x float32) { le32(b, off, math.Float32bits(x)) }
func syntheticParam(frameSize int, blocks []RegBlock) Frame {
	b := make([]byte, frameSize)
	le32(b, 0, typeParam)
	le32(b, 4, uint32(frameSize))
	le32(b, 24, uint32(len(blocks)))
	pos := 28
	for _, r := range blocks {
		le32(b, pos, uint32(r.Words)<<16|uint32(r.Addr))
		pos += 4
		copy(b[pos:], r.Payload)
		pos += len(r.Payload)
	}
	if pos != frameSize {
		panic(fmt.Sprintf("invalid synthetic param size %d != %d", pos, frameSize))
	}
	return Frame{typeParam, b}
}
func syntheticFrame(ch int, index uint32, v float32) Frame {
	n := 1052
	t := typeADC
	samples := 256
	if ch >= 8 {
		n = 284
		t = typeTach
		samples = 64
	}
	b := make([]byte, n)
	le32(b, 0, t)
	le32(b, 4, uint32(n))
	le32(b, 12, index)
	le32(b, 20, uint32(ch))
	le32(b, 24, 65536)
	for i := 0; i < samples; i++ {
		leFloat(b, 28+4*i, v)
	}
	return Frame{t, b}
}
func makeFixture() []Frame {
	id := make([]byte, 264)
	le32(id, 0, typeIdentity)
	le32(id, 4, 264)
	copy(id[24:], "VAST_MVK")
	img := make([]byte, 0x8000)
	for ch := 0; ch < 8; ch++ {
		a := (0x100 + ch*0x100) * 2
		leFloat(img, a+0x02*2, 0.010194)
		leFloat(img, a+0x0e*2, float32(510+ch))
	}
	copy(img[0x1000*2:], "00000043")
	frames := []Frame{{typeIdentity, id}, syntheticParam(32800, []RegBlock{{Addr: 0, Words: 0x4000, Payload: img}})}
	for block := 0; block < 2; block++ {
		for ch := 0; ch < 8; ch++ {
			frames = append(frames, syntheticFrame(ch, uint32(256*block), 0.125))
		}
	}
	aux := make([]RegBlock, 8)
	for ch := 0; ch < 8; ch++ {
		p := make([]byte, 0x122*2)
		leFloat(p, 0, 10.5)
		leFloat(p, 0x5e*2, 4)
		leFloat(p, 0x5c*2, 5)
		for k := 0; k < 43; k++ {
			leFloat(p, (2+k*2)*2, float32(k)/100)
		}
		for k := 0; k < 24; k++ {
			leFloat(p, (0x60+k*2)*2, float32(k)/10)
		}
		if ch >= 6 {
			le32(p, 0x120*2, 0x400)
		}
		aux[ch] = RegBlock{Addr: uint16(0x2000 + ch*0x200), Words: 0x122, Payload: p}
	}
	frames = append(frames, syntheticParam(4700, aux))
	frames = append(frames, syntheticParam(76, []RegBlock{{Addr: 0x3000, Words: 10, Payload: make([]byte, 20)}, {Addr: 0x3100, Words: 10, Payload: make([]byte, 20)}}))
	return frames
}
func writeFixture(t *testing.T, frames []Frame) (string, string, string) {
	t.Helper()
	dir := t.TempDir()
	var raw bytes.Buffer
	var csvBuf bytes.Buffer
	writer := csv.NewWriter(&csvBuf)
	_ = writer.Write([]string{"received_utc", "frame_index", "type_hex", "length", "channel", "rate_hz", "sequence_index", "note"})
	now := time.Date(2026, 10, 29, 4, 41, 1, 0, time.UTC)
	for i, fr := range frames {
		raw.Write(fr.Raw)
		row := []string{now.Add(time.Duration(i) * time.Millisecond).Format(time.RFC3339Nano), strconv.Itoa(i + 1), fmt.Sprintf("0x%08X", fr.Type), strconv.Itoa(len(fr.Raw)), "", "", "", ""}
		if fr.Type == typeADC || fr.Type == typeTach {
			row[4] = strconv.Itoa(int(binary.LittleEndian.Uint32(fr.Raw[20:24])) + 1)
			row[5] = strconv.Itoa(int(binary.LittleEndian.Uint32(fr.Raw[24:28])))
			row[6] = strconv.Itoa(int(binary.LittleEndian.Uint32(fr.Raw[12:16])))
		}
		if e := writer.Write(row); e != nil {
			t.Fatal(e)
		}
	}
	writer.Flush()
	if e := writer.Error(); e != nil {
		t.Fatal(e)
	}
	rawPath := filepath.Join(dir, "incoming.raw")
	_ = os.WriteFile(rawPath, raw.Bytes(), 0600)
	csvPath := filepath.Join(dir, "frames.csv")
	_ = os.WriteFile(csvPath, csvBuf.Bytes(), 0600)
	h := sha256.Sum256(raw.Bytes())
	sm := logSummary{Version: "Native R5.1 synthetic", Start: now.Format(time.RFC3339Nano), End: now.Add(2 * time.Second).Format(time.RFC3339Nano), RawBytes: uint64(raw.Len()), RawSHA: hex.EncodeToString(h[:]), Port: 10230, DeviceIP: "192.0.2.84"}
	bb, e := json.Marshal(sm)
	if e != nil {
		t.Fatal(e)
	}
	summaryPath := filepath.Join(dir, "summary.json")
	_ = os.WriteFile(summaryPath, bb, 0600)
	return rawPath, csvPath, summaryPath
}
func TestValidSynthetic_AllEightBINAndCSV(t *testing.T) {
	raw, frames, summary := writeFixture(t, makeFixture())
	out := filepath.Join(t.TempDir(), "output")
	r, e := export(raw, frames, summary, out, 7*60)
	if e != nil {
		t.Fatal(e)
	}
	if r.Serial != "MVK00000043" || r.ValuesRows != 1 || r.ValuesColumns != 585 || r.AUX != 1 || r.FullSnapshots != 1 {
		t.Fatalf("unexpected export report %+v", r)
	}
	for ch := 0; ch < 8; ch++ {
		info := r.Channels[ch]
		data, e := os.ReadFile(filepath.Join(out, info.Filename))
		if e != nil {
			t.Fatal(e)
		}
		if len(data) != 2048 || info.Samples != 512 {
			t.Errorf("ADC%d length/samples mismatch", ch+1)
		}
		got := math.Float32frombits(binary.LittleEndian.Uint32(data[:4]))
		want := float32(0.125) * float32(510+ch)
		if got != want {
			t.Errorf("ADC%d gain=%.4f result=%.4f want=%.4f", ch+1, info.Gain, got, want)
		}
		if _, e := os.Stat(filepath.Join(out, info.Filename+".tsxml")); e != nil {
			t.Fatal(e)
		}
		st := "0x00000000"
		if ch >= 6 {
			st = "0x00000400"
		}
		if info.StatusCounts[st] != 1 {
			t.Errorf("ADC%d status %v", ch+1, info.StatusCounts)
		}
	}
	v, e := os.ReadFile(filepath.Join(out, "VALUES_ALL_ADC_RECONSTRUCTED.csv"))
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Contains(v, []byte("sep=|\r\n")) || bytes.Contains(v, []byte("\n\n")) {
		t.Fatalf("unexpected CSV prefix")
	}
	if _, e := os.Stat(filepath.Join(out, "TIMELINE.json")); e != nil {
		t.Fatal(e)
	}
}
func TestFailClosedSequenceGap(t *testing.T) {
	frames := makeFixture()
	le32(frames[10].Raw, 12, 999)
	raw, csv, sum := writeFixture(t, frames)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, csv, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "index gap") {
		t.Fatalf("expected gap, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatalf("published invalid data")
	}
}
func TestFailClosedNonFiniteADC(t *testing.T) {
	frames := makeFixture()
	le32(frames[2].Raw, 28, 0x7FC00000)
	raw, csv, sum := writeFixture(t, frames)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, csv, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "non-finite") {
		t.Fatalf("expected NaN gate, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatalf("published invalid data")
	}
}
func TestFailClosedNoCalibration(t *testing.T) {
	frames := makeFixture()
	leFloat(frames[1].Raw, 32+(0x100+0x0e)*2, 0) // register gain ADC1
	raw, csv, sum := writeFixture(t, frames)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, csv, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "invalid ADC1 gain") {
		t.Fatalf("expected calibration rejection, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatal("invalid output published")
	}
}
func TestFailClosedMidSessionGainChange(t *testing.T) {
	frames := makeFixture()
	p := make([]byte, 4)
	leFloat(p, 0, 777)
	frames = append(frames, syntheticParam(36, []RegBlock{{Addr: 0x10e, Words: 2, Payload: p}}))
	raw, csv, sum := writeFixture(t, frames)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, csv, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "CHANGED") {
		t.Fatalf("expected changed-gain rejection, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatal("invalid output published")
	}
}
func TestFailClosedMismatchedCSV(t *testing.T) {
	raw, frames, sum := writeFixture(t, makeFixture())
	b, _ := os.ReadFile(frames)
	b = bytes.Replace(b, []byte("0xFF800ADC"), []byte("0xFF800AAA"), 1)
	_ = os.WriteFile(frames, b, 0600)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, frames, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "CSV typ/length mismatch") {
		t.Fatalf("expected provenance mismatch, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatal("invalid output published")
	}
}
func TestFailClosedMismatchedRawHash(t *testing.T) {
	raw, frames, sum := writeFixture(t, makeFixture())
	b, _ := os.ReadFile(sum)
	var s logSummary
	_ = json.Unmarshal(b, &s)
	s.RawSHA = strings.Repeat("0", 64)
	j, _ := json.Marshal(s)
	_ = os.WriteFile(sum, j, 0600)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, frames, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "SHA") {
		t.Fatalf("expected hash gate, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatal("invalid output published")
	}
}
func TestFailClosedTruncatedFrame(t *testing.T) {
	frames := makeFixture()
	raw, fc, sum := writeFixture(t, frames)
	b, _ := os.ReadFile(raw)
	b = b[:len(b)-3]
	_ = os.WriteFile(raw, b, 0600)
	out := filepath.Join(t.TempDir(), "export")
	_, e := export(raw, fc, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "truncated frame") {
		t.Fatalf("expected truncate error, got %v", e)
	}
	if _, e = os.Stat(out); !errors.Is(e, os.ErrNotExist) {
		t.Fatal("invalid output published")
	}
}
func TestFailClosedExistingDirectory(t *testing.T) {
	raw, frames, sum := writeFixture(t, makeFixture())
	out := filepath.Join(t.TempDir(), "export")
	_ = os.Mkdir(out, 0700)
	marker := filepath.Join(out, "existing.txt")
	_ = os.WriteFile(marker, []byte("unchanged"), 0600)
	_, e := export(raw, frames, sum, out, 0)
	if e == nil || !strings.Contains(e.Error(), "destination exists") {
		t.Fatalf("expected existing-dir refusal, got %v", e)
	}
	b, e := os.ReadFile(marker)
	if e != nil || string(b) != "unchanged" {
		t.Fatal("modified prior result")
	}
}
func TestOriginalTSXMLSchemaAndCP1251(t *testing.T) {
	stamp := time.Date(2026, 10, 28, 10, 12, 5, 0, time.UTC)
	b, e := tsxml("MVKTEST-ADC1.bin", 0, "MVKTEST", 65536, 510.6, 2124800, stamp)
	if e != nil {
		t.Fatal(e)
	}
	for _, s := range []string{"<DateTime>10/28/2026 10:12:05 AM</DateTime>", "<To Units=\"ms\">32421.88</To>", "<DataLength>8499200</DataLength>", "<DataFileName>.\\MVKTEST-ADC1.bin</DataFileName>"} {
		if !bytes.Contains(b, []byte(s)) {
			t.Errorf("missing XML tag %s", s)
		}
	}
	if !bytes.Contains(b, []byte{'\xEC', '/', '\xF1', '2'}) {
		t.Errorf("CP1251 units absent")
	}
}
func TestOriginalVALUESColumnCountAndTableShape(t *testing.T) {
	if len(valuesLabels) != 73 || len(tableMeasureLabels) != 26 || len(tableUnits) != 26 {
		t.Fatal("header schema mismatch")
	}
	if valuesLabels[0] != "Полоса 0.63 Гц" || valuesLabels[42] != "Полоса 10000 Гц" || valuesLabels[49] != "Виброускорение, 10..3000 Гц" {
		t.Fatal("wrong original titles")
	}
	rows := buildTableRows(snapshot{})
	if len(rows) != 39 || len(rows[0]) != 10 || len(rows[1]) != 10 || rows[1][0] != "Индикатор перегрузки" || rows[30][0] != "Виброперемещение, Польз. 2" {
		t.Fatalf("TABLE mismatch rows=%d", len(rows))
	}
	b, e := legacyCSV(rows)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.HasPrefix(b, []byte("sep=|\r\n")) {
		t.Fatal("MVK legacy CSV prefix missing")
	}
}
func TestInvalidUTCOffset(t *testing.T) {
	raw, frames, sum := writeFixture(t, makeFixture())
	out := filepath.Join(t.TempDir(), "export")
	if _, e := export(raw, frames, sum, out, 15*60); e == nil {
		t.Fatal("invalid timezone accepted")
	}
}
func TestEmbeddedExporterHasNoNetworkImports(t *testing.T) {
	for _, p := range []string{"exporter.go", "csv_recovery.go", "labels.go"} {
		b, e := os.ReadFile(p)
		if e != nil {
			t.Fatal(e)
		}
		for _, needle := range []string{"\"net\"", "\"net/", "DialContext", "net.Dial", "socket.Connect"} {
			if bytes.Contains(b, []byte(needle)) {
				t.Errorf("embedded exporter has a network operation/import in %s", p)
			}
		}
	}
}
