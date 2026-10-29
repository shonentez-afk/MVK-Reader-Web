package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Independent data exporter: NO net/socket calls or MVK commands.
// Stage108 calls it after Native Live capture has been safely closed.
// All artifacts are staged and published as a single directory rename on success.
// On ANY invalid data (missing initial calibration, bad frame, wrong CSV pairing,
// ADC sequence gap, rate/gain change, non-finite sample) outputs are discarded.

func finiteF32(v float32) bool { return !math.IsNaN(float64(v)) && !math.IsInf(float64(v), 0) }

type logSummary struct {
	Version       string `json:"program_version"`
	EndReason     string `json:"end_reason"`
	Result        string `json:"result"`
	TailBytes     int    `json:"incomplete_final_frame_bytes"`
	InvalidFrames uint64 `json:"invalid_application_frames"`
	CaptureOnly   bool   `json:"capture_only_after_parser_error"`
	Start         string `json:"started_utc"`
	End           string `json:"ended_utc"`
	RawBytes      uint64 `json:"raw_bytes"`
	RawSHA        string `json:"raw_sha256"`
	DeviceIP      string `json:"target_ipv4"`
	Port          int    `json:"port"`
}
type sourceFrame struct {
	UTC     string
	Type    string
	Length  uint64
	Channel string
	Rate    string
	Index   string
}
type channelSnap struct {
	Third    [43]float64
	RMS      [24]float64
	Status   uint32
	Voltage  float64
	Accel25k float64
	Crest    float64
}
type snapshot struct {
	AuxFrame    uint64         `json:"aux_frame"`
	TickFrame   uint64         `json:"tick_frame"`
	TickTimeUTC string         `json:"tick_time_utc"`
	Data        [8]channelSnap `json:"-"`
	DSPStatus   uint32         `json:"-"`
	TachF       [2][2]float64  `json:"-"`
	TachU       [2][3]uint32   `json:"-"`
}
type ChannelReport struct {
	ADC          int            `json:"adc"`
	Gain         float32        `json:"gain"`
	Sensitivity  float32        `json:"sensitivity"`
	Rate         uint32         `json:"sample_rate_hz"`
	FirstIndex   uint32         `json:"first_sample_index"`
	LastIndex    uint32         `json:"last_frame_first_sample_index"`
	Frames       uint64         `json:"frames"`
	Samples      uint64         `json:"samples"`
	Bytes        uint64         `json:"bin_bytes"`
	SHA          string         `json:"bin_sha256"`
	StatusCounts map[string]int `json:"sensor_status_counts"`
	Filename     string         `json:"bin_filename"`
}
type ExportReport struct {
	Version              string            `json:"exporter_version"`
	SourceRawSHA         string            `json:"source_raw_sha256"`
	SourceRawBytes       uint64            `json:"source_raw_bytes"`
	SourceVersion        string            `json:"source_program_version"`
	StartUTC             string            `json:"capture_started_utc"`
	EndUTC               string            `json:"capture_ended_utc"`
	Serial               string            `json:"instrument_serial"`
	FrameCount           uint64            `json:"application_frames"`
	FrameTypes           map[string]uint64 `json:"frame_types"`
	FullSnapshots        uint64            `json:"full_register_snapshots"`
	AUX                  uint64            `json:"aux4700_updates"`
	ValuesTicks          uint64            `json:"values_ticks_3100"`
	Channels             [8]ChannelReport  `json:"channels"`
	ValuesColumns        int               `json:"values_columns"`
	ValuesRows           int               `json:"values_rows"`
	TableRows            int               `json:"table_rows"`
	ClockOffset          string            `json:"operator_time_offset"`
	Provenance           []string          `json:"provenance"`
	GeneratedFiles       map[string]string `json:"output_file_sha256"`
	IgnoredTerminalBytes int               `json:"ignored_incomplete_terminal_frame_bytes"`
}

func readSummary(p string) (logSummary, error) {
	b, e := os.ReadFile(p)
	if e != nil {
		return logSummary{}, e
	}
	var s logSummary
	if e = json.Unmarshal(b, &s); e != nil {
		return s, e
	}
	if s.RawBytes < 33064 || len(s.RawSHA) != 64 || s.Start == "" || s.End == "" || s.Port != instrumentPort {
		return s, errors.New("incomplete/incorrect source summary for TCP/10230")
	}
	if _, e = time.Parse(time.RFC3339Nano, s.End); e != nil {
		return s, e
	}
	return s, nil
}
func readFramesCSV(p string) ([]sourceFrame, error) {
	f, e := os.Open(p)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	rd := csv.NewReader(bufio.NewReader(f))
	rd.FieldsPerRecord = 8
	header, e := rd.Read()
	if e != nil {
		return nil, e
	}
	expected := []string{"received_utc", "frame_index", "type_hex", "length", "channel", "rate_hz", "sequence_index", "note"}
	for i, v := range expected {
		if header[i] != v {
			return nil, fmt.Errorf("CSV column %d differs", i)
		}
	}
	res := make([]sourceFrame, 0, 90000)
	for {
		row, e := rd.Read()
		if e == io.EOF {
			break
		}
		if e != nil {
			return nil, e
		}
		ix, e := strconv.ParseUint(row[1], 10, 64)
		if e != nil || ix != uint64(len(res)+1) {
			return nil, fmt.Errorf("frame CSV not consecutive near %d", len(res)+1)
		}
		length, e := strconv.ParseUint(row[3], 10, 64)
		if e != nil {
			return nil, e
		}
		if _, e = time.Parse(time.RFC3339Nano, row[0]); e != nil {
			return nil, fmt.Errorf("invalid frame clock: %w", e)
		}
		res = append(res, sourceFrame{row[0], row[2], length, row[4], row[5], row[6]})
	}
	if len(res) == 0 {
		return nil, errors.New("empty frame CSV")
	}
	return res, nil
}
func sourceMatch(ref sourceFrame, typ uint32, n uint32, h *SampleHeader) error {
	if ref.Type != fmt.Sprintf("0x%08X", typ) || ref.Length != uint64(n) {
		return fmt.Errorf("source frame CSV typ/length mismatch (CSV=%s/%d, raw=%08X/%d)", ref.Type, ref.Length, typ, n)
	}
	if h != nil {
		a := strconv.Itoa(h.Channel + 1)
		if ref.Channel != a || ref.Rate != strconv.FormatUint(uint64(h.Rate), 10) || ref.Index != strconv.FormatUint(uint64(h.Index), 10) {
			return fmt.Errorf("source frame CSV ADC fields mismatch: got %s/%s/%s expected %s/%d/%d", ref.Channel, ref.Rate, ref.Index, a, h.Rate, h.Index)
		}
	} else if ref.Channel != "" || ref.Rate != "" || ref.Index != "" {
		return errors.New("CSV has samples for non-sample frame")
	}
	return nil
}
func readF32(r *RegisterImage, word int) (float64, error) {
	x, e := r.Float32(word)
	if e != nil {
		return 0, e
	}
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return 0, fmt.Errorf("nonfinite float register 0x%04X", word)
	}
	return x, nil
}
func snapshotFromRegs(r *RegisterImage) (snapshot, error) {
	var s snapshot
	for ch := 0; ch < 8; ch++ {
		b := 0x2000 + ch*0x200
		val, e := readF32(r, b)
		if e != nil {
			return s, e
		}
		s.Data[ch].Voltage = val
		val, e = readF32(r, b+0x5E)
		if e != nil {
			return s, e
		}
		s.Data[ch].Accel25k = val
		val, e = readF32(r, b+0x5C)
		if e != nil {
			return s, e
		}
		s.Data[ch].Crest = val
		for k := 0; k < 43; k++ {
			v, e := readF32(r, b+2+2*k)
			if e != nil {
				return s, e
			}
			s.Data[ch].Third[k] = v
		}
		for k := 0; k < 24; k++ {
			v, e := readF32(r, b+0x60+2*k)
			if e != nil {
				return s, e
			}
			s.Data[ch].RMS[k] = v
		}
		x, e := r.Uint32(b + 0x120)
		if e != nil {
			return s, e
		}
		s.Data[ch].Status = x
	}
	return s, nil
}
func addTachAndDSP(s *snapshot, r *RegisterImage) error {
	dsp, e := r.Uint32(0x1020)
	if e != nil {
		return e
	}
	s.DSPStatus = dsp
	for ch := 0; ch < 2; ch++ {
		a := 0x3000 + ch*0x100
		for k := 0; k < 2; k++ {
			v, e := readF32(r, a+2*k)
			if e != nil {
				return e
			}
			s.TachF[ch][k] = v
		}
		for k := 0; k < 3; k++ {
			v, e := r.Uint32(a + 4 + 2*k)
			if e != nil {
				return e
			}
			s.TachU[ch][k] = v
		}
	}
	return nil
}
func validGainAfterBlocks(r *RegisterImage, gains [8]float32, sens [8]float32) error {
	for c := 0; c < 8; c++ {
		a := 0x100 + c*0x100
		v, e := readF32(r, a+0x0E)
		if e != nil {
			return fmt.Errorf("missing channel %d conversion gain: %w", c+1, e)
		}
		w, e := readF32(r, a+0x02)
		if e != nil {
			return fmt.Errorf("missing channel %d sensitivity: %w", c+1, e)
		}
		if math.Float32bits(float32(v)) != math.Float32bits(gains[c]) || math.Float32bits(float32(w)) != math.Float32bits(sens[c]) {
			return fmt.Errorf("channel %d gain/sensitivity CHANGED during recording (refuse fake stationary BIN)", c+1)
		}
	}
	return nil
}
func makeGain(r *RegisterImage) ([8]float32, [8]float32, error) {
	var gains, sens [8]float32
	for ch := 0; ch < 8; ch++ {
		a := 0x0100 + 0x100*ch
		v, e := readF32(r, a+0x0E)
		if e != nil {
			return gains, sens, e
		}
		w, e := readF32(r, a+0x02)
		if e != nil {
			return gains, sens, e
		}
		if v <= 0 || w <= 0 || v > 1e7 || w > 1e7 {
			return gains, sens, fmt.Errorf("invalid ADC%d gain/sensitivity", ch+1)
		}
		gains[ch], sens[ch] = float32(v), float32(w)
	}
	return gains, sens, nil
}
func serialFromRegs(r *RegisterImage) (string, error) {
	for i := 0; i < 8; i++ {
		if !r.Valid[0x1000+i/2] {
			return "", errors.New("initial ID serial not in registers")
		}
	}
	s := string(r.Data[0x1000*2 : 0x1000*2+8])
	if !regexp.MustCompile(`^[0-9]{8}$`).MatchString(s) {
		return "", fmt.Errorf("unknown serial encoding; unsafe output name")
	}
	return "MVK" + s, nil
}

// export preserves the original Stage107 strict semantics: partial frames are errors.
func export(rawPath, framesPath, summaryPath, dest string, offsetMin int) (ExportReport, error) {
	return exportWithPolicy(rawPath, framesPath, summaryPath, dest, offsetMin, false)
}

// exportWithPolicy accepts an incomplete terminal frame ONLY when a completed
// R5/R5.1 monitor summary explicitly reports that exact tail and a controlled
// capture stop. Its bytes remain in the original RAW and in the source SHA256.
// This policy does not alter the Stage107 offline-export behavior.
func exportWithPolicy(rawPath, framesPath, summaryPath, dest string, offsetMin int, allowStoppedTail bool) (rep ExportReport, err error) {
	sum, e := readSummary(summaryPath)
	if e != nil {
		return rep, e
	}
	manifest, e := readFramesCSV(framesPath)
	if e != nil {
		return rep, e
	}
	if offsetMin < -12*60 || offsetMin > 14*60 {
		return rep, errors.New("invalid operator time offset")
	}
	if allowStoppedTail {
		if sum.CaptureOnly || sum.InvalidFrames != 0 || sum.Result == "FRAMING_ERROR_RAW_SAVED" {
			return rep, errors.New("capture has application framing errors: RAW preserved; calibrated export refused")
		}
		switch sum.EndReason {
		case "DURATION_REACHED", "SIZE_LIMIT_REACHED", "STOPPED_BY_USER", "REPLAY_EOF":
		default:
			return rep, fmt.Errorf("capture did not end cleanly (%s): export refused", sum.EndReason)
		}
		if sum.TailBytes < 0 || sum.TailBytes >= maxFrameSize {
			return rep, fmt.Errorf("invalid monitor terminal-tail length %d", sum.TailBytes)
		}
		if sum.TailBytes > 0 && sum.Result != "VALID_FRAMES_WITH_INCOMPLETE_LAST_FRAME" {
			return rep, errors.New("nonzero terminal tail missing in completed monitor result")
		}
		if sum.TailBytes == 0 && sum.Result != "VALID_FRAMES" {
			return rep, errors.New("monitor result is not a valid complete-frame capture")
		}
	}
	if _, e = os.Stat(dest); !errors.Is(e, os.ErrNotExist) {
		if e == nil {
			return rep, fmt.Errorf("destination exists: %s (no overwrite)", dest)
		}
		return rep, e
	}
	if e = os.MkdirAll(filepath.Dir(dest), 0755); e != nil {
		return rep, e
	}
	stage, e := os.MkdirTemp(filepath.Dir(dest), ".stage107-pending-")
	if e != nil {
		return rep, e
	}
	defer func() {
		if err != nil {
			_ = os.RemoveAll(stage)
		}
	}()
	raw, e := os.Open(rawPath)
	if e != nil {
		return rep, e
	}
	defer raw.Close()
	r := bufio.NewReaderSize(raw, 1024*256)
	srcHash := sha256.New()
	var byteTotal uint64
	image := new(RegisterImage)
	var gains, sens [8]float32
	var outs [8]*os.File
	var hstates [8]hashState
	var firstIndex [8]uint32
	var lastIndex [8]uint32
	var next [8]uint32
	var rate [8]uint32
	var framesPer [8]uint64
	var samplesPer [8]uint64
	var statusCounts [8]map[string]int
	var serial string
	var calibrated bool
	var gotIdentity bool
	var full uint64
	var count uint64
	var auxNum uint64
	var tickNum uint64
	var lastAux snapshot
	var haveAux bool
	var ticks []snapshot
	var byType = make(map[string]uint64)
	var saved []string
	// close partially written files on all error paths
	defer func() {
		for _, f := range outs {
			if f != nil {
				_ = f.Close()
			}
		}
	}()
	for {
		// Only the bytes already marked as an incomplete terminal frame in the
		// monitor are eligible for exclusion, and their exact bytes still
		// contribute to the RAW SHA and byte count. Never discard a full frame.
		if allowStoppedTail && count == uint64(len(manifest)) {
			tail, tailErr := io.ReadAll(io.LimitReader(r, int64(maxFrameSize)+1))
			if tailErr != nil {
				return rep, tailErr
			}
			if len(tail) != sum.TailBytes {
				return rep, fmt.Errorf("monitor tail %d differs from RAW suffix %d", sum.TailBytes, len(tail))
			}
			if len(tail) >= 8 {
				tailType := binary.LittleEndian.Uint32(tail[:4])
				tailSize := binary.LittleEndian.Uint32(tail[4:8])
				if tailSize < 8 || tailSize%4 != 0 || tailSize > maxFrameSize || int(tailSize) <= len(tail) {
					return rep, fmt.Errorf("terminal suffix contains an invalid or complete application frame: type %08X size %d tail %d", tailType, tailSize, len(tail))
				}
			}
			srcHash.Write(tail)
			byteTotal += uint64(len(tail))
			rep.IgnoredTerminalBytes = len(tail)
			break
		}
		var header [8]byte
		n, e := io.ReadFull(r, header[:])
		if e == io.EOF && n == 0 {
			break
		}
		if e != nil {
			return rep, fmt.Errorf("truncated frame header at %d: %w", byteTotal, e)
		}
		typ := binary.LittleEndian.Uint32(header[0:4])
		size := binary.LittleEndian.Uint32(header[4:8])
		if size < 8 || size%4 != 0 || size > maxFrameSize {
			return rep, fmt.Errorf("invalid frame size %d at offset %d", size, byteTotal)
		}
		buf := make([]byte, size)
		copy(buf, header[:])
		if _, e = io.ReadFull(r, buf[8:]); e != nil {
			return rep, fmt.Errorf("truncated frame body at offset %d: %w", byteTotal, e)
		}
		srcHash.Write(buf)
		byteTotal += uint64(size)
		count++
		if count > uint64(len(manifest)) {
			return rep, errors.New("RAW has frames not present in frames.csv")
		}
		var smph *SampleHeader
		var sampleHeader SampleHeader
		f := Frame{Type: typ, Raw: buf}
		if typ == typeADC || typ == typeTach {
			sampleHeader, e = decodeSampleHeader(f)
			if e != nil {
				return rep, e
			}
			if sampleHeader.NonFinite != 0 {
				return rep, fmt.Errorf("non-finite samples in ADC/TACH channel %d", sampleHeader.Channel+1)
			}
			smph = &sampleHeader
		}
		if e = sourceMatch(manifest[count-1], typ, size, smph); e != nil {
			return rep, fmt.Errorf("frame %d: %w", count, e)
		}
		byType[fmt.Sprintf("%08X/%d", typ, size)]++
		switch typ {
		case typeIdentity:
			if count != 1 || size != 264 || gotIdentity || string(buf[24:32]) != "VAST_MVK" {
				return rep, errors.New("expected original 264-byte VAST_MVK identity at start")
			}
			gotIdentity = true
		case typeADC:
			if !calibrated {
				return rep, fmt.Errorf("ADC before valid initial snapshot at frame %d", count)
			}
			ch := sampleHeader.Channel
			if rate[ch] != 0 && rate[ch] != sampleHeader.Rate {
				return rep, fmt.Errorf("ADC%d sample rate changed", ch+1)
			}
			if framesPer[ch] > 0 && sampleHeader.Index != next[ch] {
				return rep, fmt.Errorf("ADC%d sample index gap: got %d expected %d", ch+1, sampleHeader.Index, next[ch])
			}
			if framesPer[ch] == 0 {
				firstIndex[ch] = sampleHeader.Index
				rate[ch] = sampleHeader.Rate
			}
			lastIndex[ch] = sampleHeader.Index
			next[ch] = sampleHeader.Index + 256
			// native Float32 channel payload: every raw value is converted once with the SAME session's verified gain
			dst := make([]byte, 1024)
			for i := 0; i < 256; i++ {
				orig := math.Float32frombits(binary.LittleEndian.Uint32(buf[28+4*i : 32+4*i]))
				v := float32(float64(orig) * float64(gains[ch]))
				if !finiteF32(v) {
					return rep, fmt.Errorf("ADC%d calibrated output overflow", ch+1)
				}
				binary.LittleEndian.PutUint32(dst[4*i:4*i+4], math.Float32bits(v))
			}
			if _, e = outs[ch].Write(dst); e != nil {
				return rep, e
			}
			hstates[ch].Write(dst)
			framesPer[ch]++
			samplesPer[ch] += 256
		case typeTach:
			// headers + samples validated above. Tachometer BIN/TSXML is a separate future stage.
		case typeParam:
			blocks, e := decodeBlocks(buf)
			if e != nil {
				return rep, fmt.Errorf("bad param frame %d: %w", count, e)
			}
			if !calibrated {
				if !gotIdentity || size != 32800 || len(blocks) != 1 || blocks[0].Addr != 0 || blocks[0].Words != 0x4000 {
					return rep, errors.New("initial full 0x4000-word register snapshot required before ADC export")
				}
			}
			for _, b := range blocks {
				image.Put(b)
			}
			if !calibrated {
				full++
				gains, sens, e = makeGain(image)
				if e != nil {
					return rep, e
				}
				serial, e = serialFromRegs(image)
				if e != nil {
					return rep, e
				}
				for ch := 0; ch < 8; ch++ {
					nm := fmt.Sprintf("%s-ADC%d-%s.bin", serial, ch+1, filenameTime(sum.Start, offsetMin))
					path := filepath.Join(stage, nm)
					file, e := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
					if e != nil {
						return rep, e
					}
					outs[ch] = file
					saved = append(saved, nm)
					statusCounts[ch] = make(map[string]int)
					hstates[ch] = hashState{h: sha256.New()}
				}
				calibrated = true
			} else {
				if e = validGainAfterBlocks(image, gains, sens); e != nil {
					return rep, e
				}
			}
			if size == 32800 && calibrated && full == 0 {
				full++
			}
			if size == 4700 {
				if len(blocks) != 8 {
					return rep, errors.New("AUX4700 missing channels")
				}
				for ch, b := range blocks {
					if b.Addr != uint16(0x2000+ch*0x200) || b.Words != 0x122 {
						return rep, errors.New("AUX4700 invalid register map")
					}
				}
				lastAux, e = snapshotFromRegs(image)
				if e != nil {
					return rep, e
				}
				lastAux.AuxFrame = count
				haveAux = true
				auxNum++
				for ch := 0; ch < 8; ch++ {
					key := fmt.Sprintf("0x%08X", lastAux.Data[ch].Status&0xC00)
					statusCounts[ch][key]++
				}
			}
			// Exactly one VALUES update follows each calculated frame in the two live captures.
			if size == 76 {
				if !haveAux {
					return rep, errors.New("values TACH tick before AUX4700")
				}
				if len(blocks) != 2 || blocks[0].Addr != 0x3000 || blocks[1].Addr != 0x3100 {
					return rep, errors.New("unexpected 76B tick register map")
				}
				t := lastAux
				t.TickFrame = count
				t.TickTimeUTC = manifest[count-1].UTC
				if e = addTachAndDSP(&t, image); e != nil {
					return rep, e
				}
				ticks = append(ticks, t)
				tickNum++
				haveAux = false
			}
		case typeAck, typeDenied:
			return rep, fmt.Errorf("unexpected ACK/DENIED in read-only capture at frame %d", count)
		default:
			return rep, fmt.Errorf("unknown message type %08X", typ)
		}
	}
	if byteTotal != sum.RawBytes || hex.EncodeToString(srcHash.Sum(nil)) != strings.ToLower(sum.RawSHA) {
		return rep, errors.New("source raw SHA/length differs from claimed R5/R5.1 summary")
	}
	if count != uint64(len(manifest)) {
		return rep, fmt.Errorf("frames.csv %d entries but RAW %d", len(manifest), count)
	}
	if !calibrated || full != 1 || auxNum == 0 || auxNum != tickNum || haveAux {
		return rep, errors.New("incomplete session identity/full snapshot/AUX/tick count")
	}
	for ch := 0; ch < 8; ch++ {
		if framesPer[ch] == 0 {
			return rep, fmt.Errorf("ADC%d has no samples", ch+1)
		}
		if e = outs[ch].Sync(); e != nil {
			return rep, e
		}
		if e = outs[ch].Close(); e != nil {
			return rep, e
		}
		outs[ch] = nil
	}
	destTime, e := time.Parse(time.RFC3339Nano, sum.End)
	if e != nil {
		return rep, e
	}
	destTime = destTime.In(time.FixedZone("operator offset", offsetMin*60))
	gen := make(map[string]string)
	for ch := 0; ch < 8; ch++ {
		name := saved[ch]
		xml, e := tsxml(name, ch, serial, rate[ch], gains[ch], samplesPer[ch], destTime)
		if e != nil {
			return rep, e
		}
		xmlName := name + ".tsxml"
		if e = os.WriteFile(filepath.Join(stage, xmlName), xml, 0600); e != nil {
			return rep, e
		}
		gen[name] = hstates[ch].Hex()
		gen[xmlName] = hashBytes(xml)
		rep.Channels[ch] = ChannelReport{ADC: ch + 1, Gain: gains[ch], Sensitivity: sens[ch], Rate: rate[ch], FirstIndex: firstIndex[ch], LastIndex: lastIndex[ch], Frames: framesPer[ch], Samples: samplesPer[ch], Bytes: samplesPer[ch] * 4, SHA: gen[name], StatusCounts: statusCounts[ch], Filename: name}
	}
	valuesRows := buildValuesRows(ticks, offsetMin)
	vcsv, e := legacyCSV(valuesRows)
	if e != nil {
		return rep, e
	}
	if e = os.WriteFile(filepath.Join(stage, "VALUES_ALL_ADC_RECONSTRUCTED.csv"), vcsv, 0600); e != nil {
		return rep, e
	}
	gen["VALUES_ALL_ADC_RECONSTRUCTED.csv"] = hashBytes(vcsv)
	tableRows := buildTableRows(ticks[len(ticks)-1])
	tcsv, e := legacyCSV(tableRows)
	if e != nil {
		return rep, e
	}
	if e = os.WriteFile(filepath.Join(stage, "TABLE_LAST_AUX_RECONSTRUCTED.csv"), tcsv, 0600); e != nil {
		return rep, e
	}
	gen["TABLE_LAST_AUX_RECONSTRUCTED.csv"] = hashBytes(tcsv)
	timeline := make([]map[string]interface{}, 0, len(ticks))
	for i, s := range ticks {
		timeline = append(timeline, map[string]interface{}{"update": i + 1, "aux_frame": s.AuxFrame, "tick_frame": s.TickFrame, "tick_received_utc": s.TickTimeUTC})
	}
	jb, _ := json.MarshalIndent(timeline, "", "  ")
	jb = append(jb, '\n')
	if e = os.WriteFile(filepath.Join(stage, "TIMELINE.json"), jb, 0600); e != nil {
		return rep, e
	}
	gen["TIMELINE.json"] = hashBytes(jb)
	rep.Version = "Stage108 Native R6.1 embedded read-only session exporter 0.1"
	rep.SourceRawSHA = sum.RawSHA
	rep.SourceRawBytes = byteTotal
	rep.SourceVersion = sum.Version
	rep.StartUTC = sum.Start
	rep.EndUTC = sum.End
	rep.Serial = serial
	rep.FrameCount = count
	rep.FrameTypes = byType
	rep.FullSnapshots = full
	rep.AUX = auxNum
	rep.ValuesTicks = tickNum
	rep.ValuesColumns = len(valuesRows[0])
	rep.ValuesRows = len(valuesRows) - 2
	rep.TableRows = len(tableRows)
	rep.ClockOffset = formatOffset(offsetMin)
	rep.Provenance = []string{"Exporter processes only saved local RAW/frames/summary; it never opens a network socket or sends commands.", "INPUT VALIDATED: R5/R5.1 raw SHA256, every frame vs frames.csv, first full 16384-word register snapshot.", "BIN: calibrated raw Float32 * per-channel current-session Float32 gain; equality with MVKView BIN of these same sessions NOT available.", "TSXML: exact observed field schema, but capture PC end time and host timezone are reconstructed, NOT original MVKView recording control metadata.", "VALUES/TABLE: source field labels from original MVKView CSV; register values from session AUX4700; numeric formatting/status text approximated, not claimed byte-for-byte.", "TIMELINE: R5/R5.1 TCP Read host timestamps from frames.csv, not DSP timestamp or synchronized sample-time clock.", "ADC7/ADC8 may have sensor status 0x400 in supplied live samples; retain numeric BIN for forensic use but do NOT describe as valid healthy sensors.", "Failure policy: one malformed frame / sample discontinuity / changing gain / wrong provenance => no completed export directory."}
	if rep.IgnoredTerminalBytes > 0 {
		rep.Provenance = append(rep.Provenance, fmt.Sprintf("Exactly %d bytes of a monitor-declared partial terminal frame excluded from BIN/CSV; retained unchanged in source RAW and SHA256.", rep.IgnoredTerminalBytes))
	}
	rep.GeneratedFiles = gen
	rb, e := json.MarshalIndent(rep, "", "  ")
	if e != nil {
		return rep, e
	}
	rb = append(rb, '\n')
	if e = os.WriteFile(filepath.Join(stage, "EXPORT_AUDIT.json"), rb, 0600); e != nil {
		return rep, e
	}
	txt := fmt.Sprintf("Stage107 / R6 reconstructed offline export\r\nSource: %s (%d bytes)\r\nSerial: %s\r\nADC: 8, AUX updates: %d, VALUES rows: %d\r\nBIN is calibrated float32. CSV timestamps originate from PC receive time, not DSP sample time.\r\nOriginal MVKView byte-for-byte parity is NOT proved.\r\n", sum.RawSHA, sum.RawBytes, serial, auxNum, len(ticks))
	tb, e := cp1251(txt)
	if e != nil {
		return rep, e
	}
	if e = os.WriteFile(filepath.Join(stage, "README_RU.txt"), tb, 0600); e != nil {
		return rep, e
	}
	if e = os.Rename(stage, dest); e != nil {
		return rep, fmt.Errorf("atomic publish failed: %w", e)
	}
	return rep, nil
}

type hashState struct {
	h io.Writer
}

func (h *hashState) Write(b []byte) {
	if h.h == nil {
		panic("nil hash writer")
	}
	_, _ = h.h.Write(b)
}
func (h hashState) Hex() string { // sha256.Hash implements Sum; assert only internal generated digest
	x, ok := h.h.(interface{ Sum([]byte) []byte })
	if !ok {
		panic("missing hash sum")
	}
	return hex.EncodeToString(x.Sum(nil))
}
func hashBytes(b []byte) string { x := sha256.Sum256(b); return hex.EncodeToString(x[:]) }
func formatOffset(min int) string {
	sign := "+"
	if min < 0 {
		sign = "-"
		min = -min
	}
	return fmt.Sprintf("%s%02d:%02d", sign, min/60, min%60)
}
func filenameTime(st string, offset int) string {
	t, e := time.Parse(time.RFC3339Nano, st)
	if e != nil {
		panic(e)
	}
	return t.In(time.FixedZone("operator offset", offset*60)).Format("2006-01-02--15-04-05")
}
