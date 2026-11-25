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
	SourceInitialRetryAttempts uint64 `json:"source_initial_retry_attempts,omitempty"`
	SourceTCPConnectionCount uint64 `json:"source_tcp_connection_count,omitempty"`
	SourceTCPMultiSocket bool `json:"source_tcp_multi_socket,omitempty"`
	SourceTCPReconnectAfterRAW uint64 `json:"source_tcp_reconnects_after_raw,omitempty"`
	SourceTCPAbandonedTailBytes uint64 `json:"source_tcp_abandoned_tail_bytes,omitempty"`
	SourceTCPSegmentManifestSHA256 string `json:"source_tcp_segments_manifest_sha256,omitempty"`
	SourceTCPSegmentCopiesVerified bool `json:"source_tcp_segment_copies_verified,omitempty"`
	SourceRateTransition bool `json:"source_rate_transition_during_live,omitempty"`
	SourceSetRateApproved bool `json:"source_setrate_tx_approved,omitempty"`
	SourceSetRateCount uint64 `json:"source_setrate_sent_commands,omitempty"`
	SourceSetRateBytes uint64 `json:"source_setrate_sent_bytes,omitempty"`
	SourceSetRateLastRate uint32 `json:"source_setrate_last_rate_hz,omitempty"`
	SourceRateACKAfter uint64 `json:"source_rate_ack_temporal,omitempty"`
	SourceRateDeniedAfter uint64 `json:"source_rate_denied_temporal,omitempty"`
	StartedUTC             string            `json:"started_utc"`
	EndedUTC               string            `json:"ended_utc"`
	DurationSeconds        float64           `json:"duration_seconds"`
	EndReason              string            `json:"end_reason"`
	Result                 string            `json:"result"`
	RawBytes               uint64            `json:"raw_bytes"`
	RawSHA256              string            `json:"raw_sha256"`
	FrameMarksSHA256       string            `json:"source_frame_marks_sha256,omitempty"`
	FrameMarkCount         uint64            `json:"source_frame_marks_count,omitempty"`
    SourceLiveWriteDataAuditSHA256 string `json:"source_live_write_data_audit_sha256,omitempty"`
    SourceLiveWriteDataWindows uint64 `json:"source_live_write_data_windows,omitempty"`
    SourceLiveWriteDataPacketRecords uint64 `json:"source_live_write_data_packet_records,omitempty"`
    SourceLiveValuesAuditSHA256 string `json:"source_live_values_audit_sha256,omitempty"`
    SourceLiveValuesWindows uint64 `json:"source_live_values_windows,omitempty"`
    SourceLiveValuesEventRecords uint64 `json:"source_live_values_event_records,omitempty"`
	Chunks                 uint64            `json:"tcp_read_chunks"`
	TotalFrames            uint64            `json:"frames_decoded"`
	FrameCounts            map[string]uint64 `json:"frame_counts"`
	IdentityFrames         uint64            `json:"identity_frames"`
	FullSnapshots          uint64            `json:"full_register_snapshots"`
	RegisterUpdates        uint64            `json:"register_update_frames"`
	SourceNonemptyParameters uint64          `json:"source_rx_nonempty_parameter_frames"`
    SourceEmptyParamFrames uint64 `json:"source_rx_empty_parameter_frames,omitempty"`
    SourceFrozenParamFrames uint64 `json:"source_original_param_frames_skipped_frozen,omitempty"`
    SourceFrozenParamBlocks uint64 `json:"source_original_param_blocks_skipped_frozen,omitempty"`
    SourceFrozenAux4700 uint64 `json:"source_original_aux4700_skipped_frozen,omitempty"`
    SourceFrozenValuesTicks uint64 `json:"source_original_values_3100_skipped_frozen,omitempty"`
    SourceOriginalParamGateSHA256 string `json:"source_original_param_gate_sha256,omitempty"`
    SourceOriginalParamGateRecords uint64 `json:"source_original_param_gate_records,omitempty"`
    SourceLocalTachGateSHA256 string `json:"source_local_tach_gate_sha256,omitempty"`
    SourceLocalTachGateRecords uint64 `json:"source_local_tach_gate_records,omitempty"`
	RegisterBlocks         uint64            `json:"register_blocks"`
	Aux4700                uint64            `json:"aux4700_updates"`
	ValuesTicks            uint64            `json:"values_ticks_address_3100"`
	ACK                    uint64            `json:"ack_observed_no_command_issued"`
	Denials                uint64            `json:"denied_responses"`
	Channels               []ChannelStats    `json:"channels"`
	InvalidFrames          uint64            `json:"invalid_application_frames"`
    SourceTask2ProtocolExceptions uint64 `json:"source_task2_protocol_exceptions,omitempty"`
    SourceTask2LastProtocolError string `json:"source_task2_last_protocol_error,omitempty"`
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
	sourceOriginalStorage *sourceOriginalStorageRing // 8 Float32 + 2 byte rings, each 2^21
	sourceOriginalADCConfig sourceOriginalADCConfig // accepted Range/Units words, form lifetime (not socket)
    sourceOriginalRXGate *sourceOriginalReceiveGate // original rate/freeze storage gate, NEVER TCP RX stop
    sourceOriginalTask2Stage *sourceOriginalTask2Lifecycle // independent Task2 Stage0/1/3 and DENIED original receive status
    sourceParamGate *sourceOriginalParamGateJournal // original PARAM freeze decisions per actual source TCP frame
    sourceTach *sourceLocalTachJournal // separate local TACH projection, never mutates wire image
	sourceLongWindowLastID string // one on-demand read per unique local request ID
	sourceLongWindowLastError string // suppress duplicate optional IPC warnings
	frameMarks  *frameMarkController // local-only source button marks; never device commands
    sourceLiveDataWriter *sourceLiveDataWriter // original rate/freeze/ADC1-gated live file writing
    sourceLiveValuesWriter *sourceLiveValuesWriter // original PARAM 0x3100-triggered WriteValues
	sourceTask2TX *sourceLiveTask2TX // opt-in original SetRate on SAME socket, never service tasks
	sourceTask0ConfigRead bool // separate original bConfigDownload Task=0, passive
	sourceTCP *sourceTCPLedger
	sourceAfterRAWReconnect bool
	sourceLastRetryReason string // exact Go transport class, not a Delphi message
	sourceLastRetryWaitMS int64 // source (Round(PauseValue)+1)*10ms
	sourceOperatorRateChan <-chan string
	sourceRateTransitionDetected bool // valid RAW but no single-rate BIN parity
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
	m := &Monitor{dir: dir, f: &Framer{}, sum: sha256.New(), start: time.Now(),
		sourceOriginalStorage:newSourceOriginalStorageRing()}
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
    // FORENSIC reconstructed BIN and original Float32 ring are now
    // separate by type: LiveBinSpool no longer holds any original ring
    // pointer and cannot overwrite live ProcessBufferChunk(FRange=1).
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
	// At the first complete application frame in this TCP chunk,
	// apply any queued LOCAL operator source marks before consuming it.
	if len(frames) > 0 && m.frameMarks != nil {
		m.frameMarks.poll(m, at)
        // Apply operator toggles BEFORE processing the first complete
        // application frame, exactly where the original source thread
        // checks WriteData/WriteValues flags prior to its ReadUInt32.
        if m.sourceLiveDataWriter!=nil {
            if e:=m.sourceLiveDataWriter.applyFrameMarks(m);e!=nil {
                return fmt.Errorf("original source WriteData mark: %w",e)
            }
        }
        if m.sourceLiveValuesWriter!=nil {
            if e:=m.sourceLiveValuesWriter.applyFrameMarks(m);e!=nil {
                return fmt.Errorf("original source WriteValues mark: %w",e)
            }
        }
	}
	for frameIndex, f := range frames {
        // A control accepted while Read was blocked must be applied before
        // the completed frame reaches the original Fs/Freeze admission gate.
        // Keep the sole receive goroutine in charge, and preserve the raw
        // write above. This only queues any separately approved RATE; it
        // does not add a socket write or permit device commands.
        if e := m.drainSourceOperatorRates(m.sourceOperatorRateChan); e != nil {
            return e
        }
        // Original reads ONE application frame at a time. Coalesced
        // TCP frames still need one FIFO dispatch between packets.
        if frameIndex>0 && m.sourceTask2TX!=nil {
            if e:=m.sourceTask2TX.sendNext(m);e!=nil {return e}
        }
		if e := m.consume(f, at); e != nil {
            if m.sourceOriginalTask2Stage!=nil &&
               m.sourceOriginalTask2Stage.connected {
                // The real Delphi Task2 thread unwinds this socket on
                // malformed application packets, not an endless RAW-only
                // receive loop. Local disk errors are a separate cause.
                if errors.Is(e,errMalformed) {
                    return m.sourceTask2InvalidPacket(
                        fmt.Errorf("type=%08X: %w",f.Type,e))
                }
                return fmt.Errorf("source Task2 local writer: %w",e)
            }
			m.summary.InvalidFrames++
			m.warn(fmt.Sprintf("frame type=%08X: %v; further data kept raw only", f.Type, e))
			m.captureOnly = true
			m.summary.CaptureOnly = true
			break
		}
        var stageErr error
        if m.sourceOriginalTask2Stage!=nil {
            stageErr=m.sourceOriginalTask2Stage.afterReceivedFrame(m,f)
        }
        // A DENIED response must still be counted by the optional
        // outgoing-command evidence BEFORE aborting Task2. Never
        // interpret a temporal ACK as proof of a matching SetRate.
		if m.sourceTask2TX != nil {
			if e := m.sourceTask2TX.afterReceivedFrame(m,f); e != nil {
				return e // transport / DENIED, not a malformed RAW frame
			}
        }
        if stageErr!=nil {return stageErr}
	}
    if parseErr!=nil && m.sourceOriginalTask2Stage!=nil &&
       m.sourceOriginalTask2Stage.connected {
        // Valid frames preceding the malformed header were already
        // consumed. Delphi dequeues the next FIFO before reading that
        // bad header, even when OS TCP coalesced both packets.
        if len(frames)>0 && m.sourceTask2TX!=nil {
            if e:=m.sourceTask2TX.sendNext(m);e!=nil{return e}
        }
        return m.sourceTask2InvalidPacket(parseErr)
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
		// Task2 has no transaction ID. A reply on TCP socket B cannot
		// corroborate a completed SetRate that was sent only on socket A.
		if m.sourceTask2TX!=nil && m.sourceTask2TX.sentInSocket>0 {
			m.note("operation ACK after SetRate on current source TCP socket; unpaired, no transaction ID")
		} else {
			m.warn("unsolicited operation ACK: no SetRate sent on current source TCP socket")
		}
	case typeDenied:
		m.summary.Denials++
		if m.sourceTask2TX!=nil && m.sourceTask2TX.sentInSocket>0 {
			m.warn("operation DENIED after SetRate on current source TCP socket; unpaired, aborting attempt")
		} else {
			m.warn("device DENIED on current source TCP socket without a source SetRate send")
		}
	case typeADC, typeTach:
        // _Unit125:008081E0 skips zero-length source packets without
        // changing TMvkChannelStorage or receiving data counters.
        if sample.Samples==0 {
            m.note("empty source sample packet (header only); original ring unchanged")
            break
        }
		c := &m.summary.Channels[sample.Channel]
		c.Frames++
		c.Samples += uint64(sample.Samples)
		c.rates[sample.Rate] = true
		c.NonFiniteSamples += uint64(sample.NonFinite)
		if c.seen && c.lastIndex != sample.Index {
			// Source TMVKThread stores 8 ADC + 2 TACH channels. Its 64-sample
			// tachometer packets also carry a sample index: a TACH gap must
			// reach the SAME live evidence/error indicator as an ADC gap.
			c.SequenceDiscontinuities++
			label := fmt.Sprintf("ADC%d", sample.Channel+1)
			if typ == typeTach { label = fmt.Sprintf("TACH%d", sample.Channel-7) }
			if c.SequenceDiscontinuities <= 3 {
				m.warn(fmt.Sprintf("%s sample sequence discontinuity: expected %d, got %d", label, c.lastIndex, sample.Index))
			}
		}
		c.lastIndex = sample.Index + uint32(sample.Samples)
		c.seen = true
		if sample.NonFinite > 0 && c.NonFiniteSamples <= uint64(sample.NonFinite) {
			m.warn(fmt.Sprintf("channel %d contains non-finite ADC/TACH values", sample.Channel+1))
		}
        // Source _Unit125:0080822F..0080824B: ALL TCP bytes were
        // received to RAW first. Source channel storage is written only
        // when the packet rate matches SetRate's in-memory selection and
        // FreezeUpdate is false. No device TX is inferred or performed.
        sourceStoreAllowed:=m.sourceOriginalRXGate==nil ||
            m.sourceOriginalRXGate.allowedFrame(*sample,c.Samples)
        if !sourceStoreAllowed && m.sourceOriginalStorage!=nil {
            // Freeze/rate-excluded wire data cannot make old samples fresh.
            // Preserve RAW and internal accounting; fence only the UI window.
            m.sourceOriginalStorage.channels[sample.Channel].cutDisplayHistory()
        }
        if typ==typeTach && m.sourceParamGate!=nil && m.sourceOriginalRXGate!=nil {
            if e:=m.ensureSourceLocalTach();e!=nil{return e}
            if e:=m.sourceTach.onSample(m,f,*sample,sourceStoreAllowed);e!=nil{return e}
        }
        // Only a second ADMITTED rate, not discarded wrong-Fs wire data,
        // proves a rate change. Preserve the homogeneous export ban even if
        // the optional LiveBinSpool was not requested for this capture.
        if m.sourceTask2TX!=nil && sourceStoreAllowed &&
            m.sourceOriginalStorage!=nil &&
            m.sourceOriginalStorage.channels[sample.Channel].seen &&
            m.sourceOriginalStorage.channels[sample.Channel].sampleRate!=sample.Rate &&
            !m.sourceRateTransitionDetected {
            m.sourceRateTransitionDetected=true
            m.summary.SourceRateTransition=true
            m.warn("Original SetRate changed source Fs during capture: RAW retained, single-rate BIN export unavailable")
            if m.liveBin!=nil {m.liveBin.preview=nil}
        }
        var physicalChunk []byte
		// Original channel 8/9 store the 256 raw payload BYTES, not
        // 64 Float32 samples; FRxPos is byte count for TACH in Delphi.
        if typ==typeTach && sourceStoreAllowed &&
            m.sourceOriginalStorage!=nil {
            if e:=m.sourceOriginalStorage.appendFrame(*sample,f.Raw[28:],sourceStorageTachBytes);e!=nil{return e}
        }
		if typ == typeADC && m.liveBin != nil && !m.summary.SourceTCPMultiSocket {
            // Freeze excludes samples from the original ring and WriteData,
            // not the separate calibrated forensic archive made from the
            // full wire stream. Otherwise the first ADC after unfreeze
            // falsely looks like a broken wire sequence to the spool.
            // Stop exposing its fallback preview once the two paths diverge.
            archiveOnlyFrozen := m.sourceOriginalRXGate != nil &&
                m.sourceOriginalRXGate.frozen && m.sourceOriginalRXGate.rate == sample.Rate
            if archiveOnlyFrozen {
                m.liveBin.preview = nil
            }
            // Do not change the existing safeguards for wrong-Fs data,
            // pre-PARAM data, or the verified physical Source ring.
			if (sourceStoreAllowed || archiveOnlyFrozen) && !m.sourceRateTransitionDetected && m.liveBin.begun {
                // Original TMVKThread accepts pre-PARAM source ADC into
                // its channel storage with default FRange=1.0. The
                // OPTIONAL forensic calibrated BIN needs a complete
                // verified PARAM gain image and may not certify early
                // samples. Do not misclassify valid TCP as malformed.
				if e := m.liveBin.adcFrame(f, *sample);e!=nil{return e}
            }
        }
        // Original _Unit125 00808284/0080828C calls ProcessBufferChunk
        // with ApplyRange=true for every admitted ADC. Constructor=1,
        // then Stage0->1 latches the independent per-channel config range.
        // The physical companion receives this SAME processed chunk.
        // The forensic wire file remains separate and immutable.
        if typ==typeADC && sourceStoreAllowed && m.sourceOriginalStorage!=nil {
            domain:=sourceStorageUnscaledADC
            scale:=sourceOriginalLiveFRange
            if m.sourceOriginalRXGate!=nil {
                scale,domain=m.sourceOriginalStorage.channels[sample.Channel].liveRange()
            }
            aligned,e:=sourceApplyOriginalFRange(f.Raw[28:],scale)
            if e!=nil{return e}
            if e=m.sourceOriginalStorage.appendFrame(
                *sample,aligned,domain);e!=nil{return e}
            state:=m.sourceOriginalStorage.channels[sample.Channel].rangeState
            // If a writer is re-opened after reconnect, retain its RAW
            // evidence but do not label bytes physical based on old config.
            rangeCurrent:=!m.summary.SourceTCPMultiSocket ||
                state!=nil && state.SocketAttempt==m.summary.SourceTCPConnectionCount
            if m.sourceLiveDataWriter!=nil && rangeCurrent && sourcePhysicalRangeKnown(state) &&
                sample.NonFinite==0 && sourcePhysicalFinite(aligned) {
                physicalChunk=aligned
            }
        }
        if m.sourceLiveDataWriter!=nil {
            if e:=m.sourceLiveDataWriter.onSample(
                m,*sample,f.Raw[28:],sourceStoreAllowed,physicalChunk);e!=nil {return e}
        }
	case typeParam:
        if m.sourceParamGate!=nil && m.sourceOriginalRXGate!=nil {
            if e:=m.ensureSourceLocalTach();e!=nil{return e}
        }
        sourceFrozen:=m.sourceOriginalRXGate!=nil && m.sourceOriginalRXGate.frozen
        // A SHA-anchored local ledger records the REAL operator Freeze
        // state per PARAM frame. RAW replay alone cannot recover it.
        if m.sourceParamGate!=nil {
            if e:=m.sourceParamGate.onParam(m,f,blocks,sourceFrozen);e!=nil{return e}
        }
        // Source _Unit125:0080844B..0080844F consumes a zero-record
        // PARAM and returns to Read. Stage0 stays Stage0. The raw bytes
        // and frame are still counted, not misclassified as a fault.
        if len(blocks)==0 {
            m.summary.SourceEmptyParamFrames++
            m.note("source zero-record PARAM: accepted, no register or Stage change")
            break
        }
        // The original stage transition at 00808617 is based on a
        // NONEMPTY PARAM, even when its registers were skipped due to
        // FreezeUpdate. Keep this received-frame count independent of
        // which register changes actually reached the original storage.
        m.summary.SourceNonemptyParameters++
        // _Unit125.pas:0080850C..008085E1: while FreezeUpdate=1, the
        // original STILL reads each PARAM register word from TCP, but
        // skips register-image changes, AUX and the WriteValues trigger
        // at 0x3100. Stage0 still reads the retained ADC config below.
        // Do not substitute stale DSP readings or emit a VALUES event
        // just because RAW contains 0x3100.
        // The immutable forensic incoming.raw retains those exact bytes.
        if sourceFrozen {
            // Nonempty frozen PARAM still transitions Stage0; image is unchanged.
            m.latchSourceOriginalRanges()
            m.summary.SourceFrozenParamFrames++
            m.summary.SourceFrozenParamBlocks+=uint64(len(blocks))
            if len(f.Raw)==4700 {m.summary.SourceFrozenAux4700++}
            for _,b:=range blocks {
                if b.Addr==0x3100 {m.summary.SourceFrozenValuesTicks++}
            }
            m.note("original FreezeUpdate: received PARAM preserved in RAW; local register/DSP/VALUES update skipped")
            break
        }
        // The Delphi receive loop processes each descriptor in order.
        // WriteValues sees this trigger's inclusive register prefix and
        // both current local TACH DWORDs before the following reset.
        for index, b := range blocks {
            m.storeSourcePARAMDescriptor(b)
            if m.sourceTach != nil {
                m.sourceTach.state.onBlock(b)
            }
            m.summary.RegisterBlocks++
            // Source 00808617..00808682 is inside the descriptor loop.
            m.latchSourceOriginalRanges()
            if b.Addr != 0x3100 {
                continue
            }
            m.summary.ValuesTicks++
            var localTach *sourceLocalTachState
            if m.sourceTach != nil {
                localTach = &m.sourceTach.state
            }
            if m.sourceLiveValuesWriter != nil {
                if e := m.sourceLiveValuesWriter.onParamDescriptor(m, blocks, index, at, localTach); e != nil {
                    return e
                }
            }
            if localTach != nil {
                localTach.resetTick()
            }
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
	if s:=m.sourceTask2TX;s!=nil {
		result.SourceSetRateApproved=s.enabled
		result.SourceSetRateCount=s.sentCommands
		result.SourceSetRateBytes=s.sentBytes
		result.SourceSetRateLastRate=s.lastSentRate
		result.SourceRateACKAfter=s.ackAfterTX
		result.SourceRateDeniedAfter=s.deniedAfterTX
	}
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
    if m.sourceLiveDataWriter!=nil {m.sourceLiveDataWriter.cleanup()}
    if m.sourceLiveValuesWriter!=nil {m.sourceLiveValuesWriter.cleanup()}
    if m.sourceParamGate!=nil {m.sourceParamGate.cleanup()}
    if m.sourceTach!=nil {m.sourceTach.cleanup()}
	return first
}
func (m *Monitor) Finalize(reason string) (Summary, string, error) {
	if !m.closed {
		m.summary.EndReason = reason
        // Continue decoding a fresh approved TCP socket after a fault,
        // but NEVER certify the aggregate measurement after any bad
        // source packet. Fail closed only at the finalization boundary.
        if m.summary.SourceTask2ProtocolExceptions>0 {
            m.captureOnly=true
            m.warn(fmt.Sprintf("%d original Task2 packet exceptions; RAW preserved, no combined certified BIN",
                m.summary.SourceTask2ProtocolExceptions))
        }
		m.summary.EndedUTC = time.Now().UTC().Format(time.RFC3339Nano)
		m.summary.DurationSeconds = time.Since(m.start).Seconds()
		m.summary.CaptureOnly = m.captureOnly
		m.summary.TailBytes = len(m.f.Tail)
		m.summary.RawSHA256 = hex.EncodeToString(m.sum.Sum(nil))
        if m.sourceLiveDataWriter!=nil {
            if e:=m.sourceLiveDataWriter.finalize(m);e!=nil {
                // Preserve incoming.raw even if LOCAL original writer fails;
                // a bad audit must never masquerade as an accepted session.
                m.warn("source WriteData file/audit failure: "+e.Error())
                m.captureOnly=true
                m.summary.CaptureOnly=true
            }
        }
        if m.sourceLiveValuesWriter!=nil {
            if e:=m.sourceLiveValuesWriter.finalize(m);e!=nil {
                m.warn("source WriteValues event/audit failure: "+e.Error())
                m.captureOnly=true
                m.summary.CaptureOnly=true
            }
        }
        if m.sourceParamGate!=nil {
            if e:=m.sourceParamGate.finalize(m);e!=nil {
                m.warn("source PARAM Freeze ledger unavailable: "+e.Error())
                m.captureOnly=true
                m.summary.CaptureOnly=true
            }
        }
        if m.sourceTach!=nil {
            if e:=m.sourceTach.finalize(m);e!=nil {
                m.warn("source local TACH journal unavailable: "+e.Error())
                m.captureOnly=true
                m.summary.CaptureOnly=true
            }
        }
		if m.frameMarks != nil {
			if markErr := m.frameMarks.finalize(m); markErr != nil {
				m.warn("Local frame mark audit unavailable: " + markErr.Error())
			}
		}
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
            if m.summary.SourceFrozenAux4700>0 {
                m.warn(fmt.Sprintf("%d original AUX4700 PARAM frames were received only under FreezeUpdate: RAW preserved, DSP not updated",m.summary.SourceFrozenAux4700))
            } else {
                m.warn("no AUX4700 frames observed during this capture")
            }
		}
		if e := m.CloseFiles(); e != nil {
			return m.Snapshot(), "", e
		}
		if m.sourceTCP!=nil {
			if e:=m.sourceTCP.writeVerifiedArtifacts(m);e!=nil {
				return m.Snapshot(),"",fmt.Errorf("source TCP session RAW evidence: %w",e)
			}
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
	if s.ReadOnly {fmt.Fprint(&b,"Нет исходящих прикладных байт.\n\n")} else {
		fmt.Fprintf(&b,"Source SetRate с разрешения оператора: команд=%d, байт=%d.\n\n",s.SourceSetRateCount,s.SourceSetRateBytes)
	}
	if s.SourceTCPConnectionCount>1 {fmt.Fprintf(&b,"ВНИМАНИЕ: %d независимых TCP-сессий; %d повторов после RAW. Для каждой — отдельный SHA256 RAW. Единый BIN запрещён.\n",s.SourceTCPConnectionCount,s.SourceTCPReconnectAfterRAW)}
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
