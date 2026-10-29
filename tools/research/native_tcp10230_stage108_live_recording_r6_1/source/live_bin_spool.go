package main

import (
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"hash"
	"io"
	"math"
	"os"
	"path/filepath"
)

// LiveBinSpool writes calibrated ADC samples as they arrive over Ethernet,
// but NEVER publishes them as completed BIN files. The temporary channel files
// are compared to an independent re-decode from the fully validated RAW stream
// before the atomic final output directory is published.
// The stager itself has no network/socket code.
type LiveBinSpool struct {
	dir         string
	begun       bool
	closed      bool
	gain        [8]float32
	sensitivity [8]float32
	rate        [8]uint32
	next        [8]uint32
	samples     [8]uint64
	files       [8]*os.File
	digest      [8]hash.Hash
}

func newLiveBinSpool(runDir string) (*LiveBinSpool, error) {
	p := filepath.Join(runDir, ".stage108_live_calibrated_pending")
	if err := os.Mkdir(p, 0700); err != nil {
		return nil, err
	}
	return &LiveBinSpool{dir: p}, nil
}

func (s *LiveBinSpool) start(img *RegisterImage) error {
	if s.begun {
		return errors.New("calibration snapshot repeated")
	}
	var err error
	s.gain, s.sensitivity, err = makeGain(img)
	if err != nil {
		return err
	}
	for ch := 0; ch < 8; ch++ {
		p := filepath.Join(s.dir, fmt.Sprintf("ADC%d.bin.partial", ch+1))
		f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			return e
		}
		s.files[ch] = f
		s.digest[ch] = sha256.New()
	}
	s.begun = true
	return nil
}

func (s *LiveBinSpool) paramFrame(f Frame, blocks []RegBlock, img *RegisterImage) error {
	if s.closed {
		return errors.New("live bin spool already closed")
	}
	if !s.begun {
		if len(f.Raw) == 32800 && len(blocks) == 1 && blocks[0].Addr == 0 && blocks[0].Words == registerWords {
			return s.start(img)
		}
		return nil
	}
	return validGainAfterBlocks(img, s.gain, s.sensitivity)
}

func (s *LiveBinSpool) adcFrame(f Frame, h SampleHeader) error {
	if s.closed {
		return errors.New("live bin spool already closed")
	}
	if !s.begun {
		return errors.New("ADC received before initial full register image")
	}
	if h.Channel >= 8 || h.Samples != 256 || h.NonFinite != 0 || h.Rate == 0 {
		return fmt.Errorf("invalid live ADC header: ch=%d samples=%d nonfinite=%d rate=%d", h.Channel, h.Samples, h.NonFinite, h.Rate)
	}
	ch := h.Channel
	if s.samples[ch] != 0 && (h.Index != s.next[ch] || h.Rate != s.rate[ch]) {
		return fmt.Errorf("ADC%d live gap/rate change at index=%d; expected=%d", ch+1, h.Index, s.next[ch])
	}
	if s.samples[ch] == 0 {
		s.rate[ch] = h.Rate
	}
	var bytesOut [1024]byte
	for i := 0; i < 256; i++ {
		original := math.Float32frombits(binary.LittleEndian.Uint32(f.Raw[28+i*4 : 32+i*4]))
		scaled := float32(float64(original) * float64(s.gain[ch]))
		if !finiteF32(scaled) {
			return fmt.Errorf("ADC%d calibrated sample is non-finite", ch+1)
		}
		binary.LittleEndian.PutUint32(bytesOut[4*i:4*i+4], math.Float32bits(scaled))
	}
	n, err := s.files[ch].Write(bytesOut[:])
	if err != nil {
		return err
	}
	if n != len(bytesOut) {
		return errors.New("short live BIN spool write")
	}
	_, _ = s.digest[ch].Write(bytesOut[:])
	s.samples[ch] += 256
	s.next[ch] = h.Index + 256
	return nil
}

func (s *LiveBinSpool) Close() error {
	if s == nil || s.closed {
		return nil
	}
	s.closed = true
	var first error
	for ch := 0; ch < 8; ch++ {
		f := s.files[ch]
		if f == nil {
			continue
		}
		if err := f.Sync(); err != nil && first == nil {
			first = err
		}
		if err := f.Close(); err != nil && first == nil {
			first = err
		}
		s.files[ch] = nil
	}
	return first
}

func (s *LiveBinSpool) verifyAgainstExport(r ExportReport) error {
	if s == nil {
		return nil
	}
	if !s.begun {
		return errors.New("no live BIN spool established despite completed export")
	}
	if !s.closed {
		return errors.New("live BIN spool must be closed before verify")
	}
	for ch := 0; ch < 8; ch++ {
		if s.digest[ch] == nil || s.samples[ch] != r.Channels[ch].Samples || s.rate[ch] != r.Channels[ch].Rate {
			return fmt.Errorf("ADC%d live spool count/rate mismatch", ch+1)
		}
		got := fmt.Sprintf("%x", s.digest[ch].Sum(nil))
		if got != r.Channels[ch].SHA {
			return fmt.Errorf("ADC%d in-memory live spool hash differs from independent complete RAW replay", ch+1)
		}
		// Rehash ACTUAL on-disk partial bytes: comparison of cached digests
		// alone would miss accidental corruption in the temporary spool file.
		p := filepath.Join(s.dir, fmt.Sprintf("ADC%d.bin.partial", ch+1))
		f, err := os.Open(p)
		if err != nil {
			return err
		}
		h := sha256.New()
		size, copyErr := io.Copy(h, f)
		closeErr := f.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
		if uint64(size) != s.samples[ch]*4 || fmt.Sprintf("%x", h.Sum(nil)) != got {
			return fmt.Errorf("ADC%d physical temporary BIN file differs from expected bytes/hash", ch+1)
		}
	}
	return nil
}

func (s *LiveBinSpool) Cleanup() error {
	if s == nil {
		return nil
	}
	if err := s.Close(); err != nil {
		return err
	}
	return os.RemoveAll(s.dir)
}
