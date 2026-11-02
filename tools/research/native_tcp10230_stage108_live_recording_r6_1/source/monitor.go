package main

import (
	"archive/zip"
	"bufio"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type ChannelStats struct {
	Channel                 int      `json:"channel"`
	Frames                  uint64   `json:"frames"`
	Samples                 uint64   `json:"samples"`
	Rates                   []uint32 `json:"sample_rates_hz"`
	SequenceDiscontinuities uint64   `json:"sequence_discontinuities"`
	NonFiniteSamples        uint64   `json:"nonfinite_samples"`
	lastIndex               uint32
	seen                    bool
	rates                   map[uint32]bool
}

type Summary struct {
	Version                string            `json:"program_version"`
	Mode                   string            `json:"mode"`
	IP                     string            `json:"target_ipv4,omitempty"`
	Port                   int               `json:"port"`
	SelectedInterface      string            `json:"selected_interface,omitempty"`
	SelectedInterfaceIndex int               `json:"selected_interface_index,omitempty"`
	SelectedLocalIPv4      string            `json:"selected_local_ipv4,omitempty"`
	SocketLocalAddr        string            `json:"connected_local_address,omitempty"`
	SocketRemoteAddr       string            `json:"connected_remote_address,omitempty"`
	ReadOnly               bool              `json:"read_only_no_app_payload_sent"`
	StartedUTC             string            `json:"started_utc"`
	EndedUTC               string            `json:"ended_utc"`
	DurationSeconds        float64           `json:"duration_seconds"`
	EndReason              string            `json:"end_reason"`
	Result                 string            `json:"result"`
	RawBytes               uint64            `json:"raw_bytes"`
	RawSHA256              string            `json:"raw_sha256"`
	Chunks                 uint64            `json:"tcp_read_chunks"`
	TotalFrames            uint64            `json:"frames_decoded"`
	FrameCounts            map[string]uint64 `json:"frame_counts"`
	IdentityFrames         uint64            `json:"identity_frames"`
	FullSnapshots          uint64            `json:"full_register_snapshots"`
	RegisterUpdates        uint64            `json:"register_update_frames"`
	RegisterBlocks         uint64            `json:"register_blocks"`
	Aux4700                uint64            `json:"aux4700_updates"`
	ValuesTicks            uint64            `json:"values_ticks_address_3100"`
	ACK                    uint64            `json:"ack_observed_no_command_issued"`
	Denials                uint64            `json:"denied_responses"`
	Channels               []ChannelStats    `json:"channels"`
	InvalidFrames          uint64            `json:"invalid_application_frames"`
	CaptureOnly            bool              `json:"capture_only_after_parser_error"`
	TailBytes              int               `json:"incomplete_final_frame_bytes"`
	Warnings               []string          `json:"warnings"`
	WarningCount           uint64            `json:"warning_count"`
	Files                  map[string]string `json:"files"`
}

type Monitor struct {
	summary     Summary
	start       time.Time
	f           *Framer
	image       RegisterImage
	raw         *os.File
	chunksFile  *os.File
	framesFile  *os.File
	calcFile    *os.File
	eventsFile  *os.File
	chunksBuf   *bufio.Writer
	framesBuf   *bufio.Writer
	calcBuf     *bufio.Writer
	eventsBuf   *bufio.Writer
	csvChunks   *csv.Writer
	csvFrames   *csv.Writer
	sum         hash.Hash
	dir         string
	filenames   []string
	captureOnly bool
	closed      bool
	liveBin     *LiveBinSpool
	// Opt-in Stage111Z26 UI-only telemetry, never part of original RAW/BIN.
	liveProgressEnabled bool
	liveTargetSeconds int
	liveProgressAt time.Time
	liveLastPacket time.Time
	liveLastAUXUTC string
	liveDSPStatus [8]uint32
	liveDSPSeen [8]bool
	livePreviewFailures int // optional file sharing errors; never interrupt RAW
}

func NewMonitor(dir, mode, ip string) (*Monitor, error) {
	if err := os.Mkdir(dir, 0700); err != nil {
		return nil, fmt.Errorf("create run directory: %w", err)
	}
	m := &Monitor{dir: dir, f: &Framer{}, sum: sha256.New(), start: time.Now()}
	m.summary = Summary{Version: "Native Stage108 R6.1 / R5.1 Ethernet receive / embedded Stage107 export 0.1", Mode: mode, IP: ip, Port: instrumentPort,
		ReadOnly: true, StartedUTC: m.start.UTC().Format(time.RFC3339Nano), FrameCounts: map[string]uint64{}, Files: map[string]string{}}
	for i := 0; i < 10; i++ {
		m.summary.Channels = append(m.summary.Channels, ChannelStats{Channel: i + 1, rates: map[uint32]bool{}})
	}
	open := func(name string) (*os.File, error) {
		p := filepath.Join(dir, name)
		f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e == nil {
			m.filenames = append(m.filenames, name)
			m.summary.Files[name] = name
		}
		return f, e
	}
	var err error
	if m.raw, err = open("incoming.raw"); err != nil {
		m.CloseFiles()
		return nil, err
	}
	if m.chunksFile, err = open("chunks.csv"); err != nil {
		m.CloseFiles()
		return nil, err
	}
	if m.framesFile, err = open("frames.csv"); err != nil {
		m.CloseFiles()
		return nil, err
	}
	if m.calcFile, err = open("aux4700.jsonl"); err != nil {
		m.CloseFiles()
		return nil, err
	}
	if m.eventsFile, err = open("events.log"); err != nil {
		m.CloseFiles()
		return nil, err
	}
	m.chunksBuf = bufio.NewWriterSize(m.chunksFile, 128*1024)
	m.framesBuf = bufio.NewWriterSize(m.framesFile, 128*1024)
	m.calcBuf = bufio.NewWriterSize(m.calcFile, 128*1024)
	m.eventsBuf = bufio.NewWriterSize(m.eventsFile, 16*1024)
	m.csvChunks = csv.NewWriter(m.chunksBuf)
	m.csvFrames = csv.NewWriter(m.framesBuf)
	_ = m.csvChunks.Write([]string{"received_utc", "raw_offset_bytes", "bytes"})
	_ = m.csvFrames.Write([]string{"received_utc", "frame_index", "type_hex", "length", "channel", "rate_hz", "sequence_index", "note"})
	m.note("Monitor started; receive-only; no application packets are sent")
	return m, nil
}

// EnableLiveBinSpool must run before any received bytes are passed to ProcessChunk.
// The operator's -export=false leaves the regular R5.1 RAW diagnostic untouched.
func (m *Monitor) EnableLiveBinSpool() error {
	if m.closed || m.summary.RawBytes != 0 || m.liveBin != nil {
		return errors.New("live BIN spool must be enabled exactly once before acquisition")
	}
	stager, err := newLiveBinSpool(m.dir)
	if err != nil {
		return err
	}
	m.liveBin = stager
	m.note("Live calibrated BIN spool enabled: partial files never published before verification")
	return nil
}

func (m *Monitor) warn(msg string) {
	m.summary.WarningCount++
	if len(m.summary.Warnings) < 50 {
		m.summary.Warnings = append(m.summary.Warnings, msg)
	}
	if m.summary.WarningCount <= 250 {
		m.note("WARNING: " + msg)
	}
}
func (m *Monitor) note(s string) {
	if m.eventsBuf != nil {
		fmt.Fprintf(m.eventsBuf, "%s %s\n", time.Now().UTC().Format(time.RFC3339Nano), s)
	}
}
func hexType(t uint32) string { return fmt.Sprintf("0x%08X", t) }
func (m *Monitor) ProcessChunk(chunk []byte, at time.Time) error {
	if m.closed {
		return errors.New("monitor already finalized")
	}
	if len(chunk) == 0 {
		return nil
	}
	prev := m.summary.RawBytes
	n, e := m.raw.Write(chunk)
	if e != nil {
		return e
	}
	if n != len(chunk) {
		return io.ErrShortWrite
	}
	_, _ = m.sum.Write(chunk)
	m.summary.RawBytes += uint64(n)
	if m.liveProgressEnabled { m.liveLastPacket = at }
	m.summary.Chunks++
	if err := m.csvChunks.Write([]string{at.UTC().Format(time.RFC3339Nano), fmt.Sprint(prev), fmt.Sprint(n)}); err != nil {
		return err
	}
	if m.captureOnly {
		return nil
	}
	frames, parseErr := m.f.Feed(chunk)
	for _, f := range frames {
		if e := m.consume(f, at); e != nil {
			m.summary.InvalidFrames++
			m.warn(fmt.Sprintf("frame type=%08X: %v; further data kept raw only", f.Type, e))
			m.captureOnly = true
			m.summary.CaptureOnly = true
			break
		}
	}
	if parseErr != nil && !m.captureOnly {
		m.summary.InvalidFrames++
		m.warn(fmt.Sprintf("application framing: %v; further data kept raw only", parseErr))
		m.captureOnly = true
		m.summary.CaptureOnly = true
	}
	return nil
}
func (m *Monitor) consume(f Frame, at time.Time) error {
	typ := f.Type
	note, ch, rate, seq := "", "", "", ""
	var sample *SampleHeader
	var blocks []RegBlock
	if typ == typeADC || typ == typeTach {
		parsed, e := decodeSampleHeader(f)
		if e != nil {
			return e
		}
		sample = &parsed
		ch = fmt.Sprint(parsed.Channel + 1)
		rate = fmt.Sprint(parsed.Rate)
		seq = fmt.Sprint(parsed.Index)
	}
	if typ == typeParam {
		parsed, e := decodeBlocks(f.Raw)
		if e != nil {
			return e
		}
		blocks = parsed
		if len(f.Raw) == 4700 {
			if len(blocks) != 8 {
				return fmt.Errorf("4700-byte frame has %d channel blocks", len(blocks))
			}
			for i, b := range blocks {
				if int(b.Addr) != 0x2000+i*0x200 || b.Words != 0x122 {
					return fmt.Errorf("4700-byte frame contains unexpected record %d addr=%04X words=%d", i, b.Addr, b.Words)
				}
			}
		}
		note = fmt.Sprintf("blocks=%d", len(blocks))
	}
	if typ == typeAck || typ == typeDenied {
		if len(f.Raw) != 8 {
			return fmt.Errorf("unexpected reply payload")
		}
	}
	if e := m.csvFrames.Write([]string{at.UTC().Format(time.RFC3339Nano), fmt.Sprint(m.summary.TotalFrames + 1), hexType(typ), fmt.Sprint(len(f.Raw)), ch, rate, seq, note}); e != nil {
		return e
	}
	m.summary.TotalFrames++
	m.summary.FrameCounts[fmt.Sprintf("%08X/%d", typ, len(f.Raw))]++
	switch typ {
	case typeIdentity:
		m.summary.IdentityFrames++
		m.note(fmt.Sprintf("identity message length=%d", len(f.Raw)))
	case typeAck:
		m.summary.ACK++
		m.warn("unexpected operation ACK received; this program has issued NO command")
	case typeDenied:
		m.summary.Denials++
		m.warn("device reported operation denied; this program has issued NO command")
	case typeADC, typeTach:
		c := &m.summary.Channels[sample.Channel]
		c.Frames++
		c.Samples += uint64(sample.Samples)
		c.rates[sample.Rate] = true
		c.NonFiniteSamples += uint64(sample.NonFinite)
		if c.seen && c.lastIndex != sample.Index && typ == typeADC {
			c.SequenceDiscontinuities++
			if c.SequenceDiscontinuities <= 3 {
				m.warn(fmt.Sprintf("ADC%d sample sequence discontinuity: expected %d, got %d", sample.Channel+1, c.lastIndex, sample.Index))
			}
		}
		c.lastIndex = sample.Index + uint32(sample.Samples)
		c.seen = true
		if sample.NonFinite > 0 && c.NonFiniteSamples <= uint64(sample.NonFinite) {
			m.warn(fmt.Sprintf("channel %d contains non-finite ADC values", sample.Channel+1))
		}
		if typ == typeADC && m.liveBin != nil {
			if e := m.liveBin.adcFrame(f, *sample); e != nil {
				return e
			}
		}
	case typeParam:
		for _, b := range blocks {
			m.image.Put(b)
			m.summary.RegisterBlocks++
		}
		m.summary.RegisterUpdates++
		if m.liveBin != nil {
			if e := m.liveBin.paramFrame(f, blocks, &m.image); e != nil {
				return e
			}
		}
		if len(blocks) == 1 && blocks[0].Addr == 0 && blocks[0].Words == registerWords {
			m.summary.FullSnapshots++
			m.note("full 32800-byte register image received")
		}
		for _, b := range blocks {
			if b.Addr == 0x3100 {
				m.summary.ValuesTicks++
				break
			}
		}
		if len(f.Raw) == 4700 {
			m.summary.Aux4700++
			for channel := 0; channel < 8; channel++ {
				v, e := decodeCalculated(&m.image, channel, at.UTC().Format(time.RFC3339Nano), m.summary.Aux4700)
				if e != nil {
					return fmt.Errorf("AUX4700 ADC%d: %w", channel+1, e)
				}
				if m.liveProgressEnabled {
					m.liveDSPStatus[channel] = v.Status
					m.liveDSPSeen[channel] = true
				}
				data, e := json.Marshal(v)
				if e != nil {
					return e
				}
				if _, e = m.calcBuf.Write(append(data, '\n')); e != nil {
					return e
				}
			}
			if m.liveProgressEnabled { m.liveLastAUXUTC = at.UTC().Format(time.RFC3339Nano) }
		}
	}
	return nil
}

func (m *Monitor) Snapshot() Summary {
	result := m.summary
	result.Channels = make([]ChannelStats, len(m.summary.Channels))
	for i, c := range m.summary.Channels {
		out := c
		out.Rates = out.Rates[:0]
		for r := range c.rates {
			out.Rates = append(out.Rates, r)
		}
		sort.Slice(out.Rates, func(i, j int) bool { return out.Rates[i] < out.Rates[j] })
		out.rates = nil
		result.Channels[i] = out
	}
	return result
}

func (m *Monitor) CloseFiles() error {
	if m.closed {
		return nil
	}
	m.closed = true
	var first error
	for _, b := range []*bufio.Writer{m.chunksBuf, m.framesBuf, m.calcBuf, m.eventsBuf} {
		if b != nil {
			if e := b.Flush(); e != nil && first == nil {
				first = e
			}
		}
	}
	for _, f := range []*os.File{m.raw, m.chunksFile, m.framesFile, m.calcFile, m.eventsFile} {
		if f != nil {
			if e := f.Close(); e != nil && first == nil {
				first = e
			}
		}
	}
	if m.liveBin != nil {
		if e := m.liveBin.Close(); e != nil && first == nil {
			first = e
		}
	}
	return first
}
func (m *Monitor) Finalize(reason string) (Summary, string, error) {
	if !m.closed {
		m.summary.EndReason = reason
		m.summary.EndedUTC = time.Now().UTC().Format(time.RFC3339Nano)
		m.summary.DurationSeconds = time.Since(m.start).Seconds()
		m.summary.CaptureOnly = m.captureOnly
		m.summary.TailBytes = len(m.f.Tail)
		m.summary.RawSHA256 = hex.EncodeToString(m.sum.Sum(nil))
		switch {
		case m.summary.RawBytes == 0:
			m.summary.Result = "NO_DATA"
		case m.summary.CaptureOnly:
			m.summary.Result = "FRAMING_ERROR_RAW_SAVED"
		case m.summary.TailBytes > 0:
			m.summary.Result = "VALID_FRAMES_WITH_INCOMPLETE_LAST_FRAME"
		default:
			m.summary.Result = "VALID_FRAMES"
		}
		if m.summary.RawBytes == 0 {
			m.warn("TCP may have connected without any application bytes; no handshake was sent")
		}
		if reason == "SIZE_LIMIT_REACHED" {
			m.warn("configured maximum capture size reached; recording stopped intentionally")
		}
		if reason == "REMOTE_DISCONNECTED" {
			m.warn("remote end closed TCP connection; connection state must be checked")
		}
		if m.summary.TailBytes > 0 {
			m.warn(fmt.Sprintf("last application frame incomplete: %d bytes; common if timed capture stops midframe", m.summary.TailBytes))
		}
		if m.summary.Aux4700 == 0 {
			m.warn("no AUX4700 frames observed during this capture")
		}
		if e := m.CloseFiles(); e != nil {
			return m.Snapshot(), "", e
		}
	}
	report := m.Snapshot()
	p := filepath.Join(m.dir, "summary.json")
	b, e := json.MarshalIndent(report, "", "  ")
	if e != nil {
		return report, "", e
	}
	if e = os.WriteFile(p, append(b, '\n'), 0600); e != nil {
		return report, "", e
	}
	m.filenames = append(m.filenames, "summary.json")
	txt := renderSummary(report)
	if e = os.WriteFile(filepath.Join(m.dir, "summary_ru.txt"), []byte(txt), 0600); e != nil {
		return report, "", e
	}
	m.filenames = append(m.filenames, "summary_ru.txt")
	zipPath := filepath.Join(m.dir, "MVK10230_TEST_RESULTS.zip")
	if e = createZip(zipPath, m.dir, m.filenames); e != nil {
		return report, "", e
	}
	return report, zipPath, nil
}
func renderSummary(s Summary) string {
	var b strings.Builder
	fmt.Fprintf(&b, "MVK Reader Web - диагностика TCP/10230 (Native R5)\n")
	fmt.Fprintf(&b, "Только чтение. Команды прибору не отправляются.\n\n")
	fmt.Fprintf(&b, "Режим: %s; IP: %s; порт: %d\n", s.Mode, s.IP, s.Port)
	if s.SelectedLocalIPv4 != "" {
		fmt.Fprintf(&b, "Выбранный интерфейс: %s [index %d] / %s\n", s.SelectedInterface, s.SelectedInterfaceIndex, s.SelectedLocalIPv4)
		fmt.Fprintf(&b, "TCP адреса: %s -> %s\n", s.SocketLocalAddr, s.SocketRemoteAddr)
	}
	fmt.Fprintf(&b, "Начало UTC: %s\nКонец UTC: %s\n", s.StartedUTC, s.EndedUTC)
	fmt.Fprintf(&b, "Результат: %s\nПричина остановки: %s\n", s.Result, s.EndReason)
	fmt.Fprintf(&b, "Байтов получено: %d, чанков: %d, кадров: %d, хвост: %d\n", s.RawBytes, s.Chunks, s.TotalFrames, s.TailBytes)
	fmt.Fprintf(&b, "Идентификация: %d, полный образ регистров: %d, AUX4700: %d, VALUES триггеров: %d\n", s.IdentityFrames, s.FullSnapshots, s.Aux4700, s.ValuesTicks)
	fmt.Fprintf(&b, "Ошибки декодера: %d; недостоверный поток: %v\n", s.InvalidFrames, s.CaptureOnly)
	fmt.Fprintf(&b, "SHA256 входящего потока: %s\n\n", s.RawSHA256)
	b.WriteString("Каналы (TACH представлены как 9/10):\n")
	for _, c := range s.Channels {
		fmt.Fprintf(&b, "Канал %d: кадров=%d, отсчётов=%d, частоты=%v, разрывы последовательности=%d, NaN/Inf=%d\n",
			c.Channel, c.Frames, c.Samples, c.Rates, c.SequenceDiscontinuities, c.NonFiniteSamples)
	}
	b.WriteString("\nПолученные типы кадров:\n")
	keys := make([]string, 0, len(s.FrameCounts))
	for k := range s.FrameCounts {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(&b, "%s : %d\n", k, s.FrameCounts[k])
	}
	b.WriteString("\nПредупреждения:\n")
	for _, w := range s.Warnings {
		b.WriteString("- " + w + "\n")
	}
	if s.WarningCount > uint64(len(s.Warnings)) {
		fmt.Fprintf(&b, "... и ещё %d (см. events.log)\n", s.WarningCount-uint64(len(s.Warnings)))
	}
	b.WriteString("\nВАЖНО: результаты подтверждают только получение и разбор байтов, НЕ точность вычислений\n")
	b.WriteString("и НЕ отсутствие влияния TCP-подключения на работающий прибор. В отчёте нет проверки\n")
	b.WriteString("управления частотой, конфигурацией или записи во Flash. Файлы сырые, НЕ BIN MVKView.\n")
	return b.String()
}
func createZip(zipPath, dir string, names []string) error {
	f, e := os.OpenFile(zipPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	z := zip.NewWriter(f)
	var first error
	for _, name := range names {
		in, e := os.Open(filepath.Join(dir, name))
		if e != nil {
			first = e
			break
		}
		w, e := z.Create(name)
		if e == nil {
			_, e = io.Copy(w, in)
		}
		_ = in.Close()
		if e != nil {
			first = e
			break
		}
	}
	if e := z.Close(); first == nil {
		first = e
	}
	if e := f.Close(); first == nil {
		first = e
	}
	if first != nil {
		_ = os.Remove(zipPath)
	}
	return first
}
