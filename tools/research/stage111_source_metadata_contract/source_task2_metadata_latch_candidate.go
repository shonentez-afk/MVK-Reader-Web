package main

// Standalone, passive source-contract candidate. Not wired into Monitor.
// Input order is accepted descriptor/chunk order, not a fabricated whole-frame
// image. Unknown register words are not treated as observed zero values.
import (
	"encoding/binary"
	"errors"
	"math"
)

const metadataWords = 0x4000

var impulseAddresses = [2]int{0x30fe, 0x31fe}

type sourceMetadataValue struct {
	RangeBits                      uint32 // raw ConfigADC Range (effective factor below)
	Range                          float32
	RangeKnown, RangeCurrentSocket bool
	Units                          string
	UnitsKnown, UnitsCurrentSocket bool
	FromDescriptor                 bool
}

type sourceImpulseValue struct {
	Value uint32
	Known bool
}

type sourceMetadataLatchCandidate struct {
	data            [metadataWords * 2]byte
	known           [metadataWords]bool
	epochOfWord     [metadataWords]uint64
	epoch           uint64
	firstDescriptor bool
	channel         [8]sourceMetadataValue
	last            [2]byte
}

func newSourceMetadataLatchCandidate() *sourceMetadataLatchCandidate {
	s := &sourceMetadataLatchCandidate{}
	for i := range s.channel {
		s.channel[i] = sourceMetadataValue{RangeBits: 0x3f800000, Range: 1, RangeKnown: true, UnitsKnown: true}
	}
	return s
}

// Reconnect creates a new TCP epoch, not a new TMVKThread or channel storage.
// Until the next first descriptor, previous metadata/latch/last byte persist.
func (s *sourceMetadataLatchCandidate) newSocket() {
	s.epoch++
	s.firstDescriptor = false
}

func (s *sourceMetadataLatchCandidate) put(addr int, payload []byte, local bool) {
	copy(s.data[addr*2:], payload)
	for i := addr; i < addr+len(payload)/2; i++ {
		s.known[i] = true
		if local {
			s.epochOfWord[i] = 0
		} else {
			s.epochOfWord[i] = s.epoch
		}
	}
}
func (s *sourceMetadataLatchCandidate) dword(addr int) sourceImpulseValue {
	if !s.known[addr] || !s.known[addr+1] {
		return sourceImpulseValue{}
	}
	return sourceImpulseValue{binary.LittleEndian.Uint32(s.data[addr*2:]), true}
}
func (s *sourceMetadataLatchCandidate) putImpulse(i int, v uint32) {
	var b [4]byte
	binary.LittleEndian.PutUint32(b[:], v)
	s.put(impulseAddresses[i], b[:], true)
}

// ConfigADC uses channel base 0x100+ch*0x100, Float32 at +0x0e and
// type9 text at +0x10 (32 bytes, stop at NUL, zero-extended byte chars).
// A known +/-zero range becomes 1. Unknown bytes remain unknown. A known
// nonfinite value keeps its raw bits; numeric processing refuses it.
func (s *sourceMetadataLatchCandidate) latchMetadata() {
	for i := range s.channel {
		base := 0x100 + i*0x100
		m := sourceMetadataValue{FromDescriptor: true}
		addr := base + 0x0e
		r := s.dword(addr)
		m.RangeBits, m.RangeKnown = r.Value, r.Known
		if r.Known {
			m.Range = math.Float32frombits(r.Value)
			if m.Range == 0 {
				m.Range = 1
			}
			m.RangeCurrentSocket = s.epochOfWord[addr] == s.epoch && s.epochOfWord[addr+1] == s.epoch
		}
		current := true
		chars := make([]rune, 0, 32)
		for j := 0; j < 32; j++ {
			w := base + 0x10 + j/2
			if !s.known[w] {
				break
			}
			current = current && s.epochOfWord[w] == s.epoch
			b := s.data[(base+0x10)*2+j]
			if b == 0 {
				m.UnitsKnown = true
				break
			}
			chars = append(chars, rune(b))
			if j == 31 {
				m.UnitsKnown = true
			}
		}
		if m.UnitsKnown {
			m.Units = string(chars)
			m.UnitsCurrentSocket = current
		}
		s.channel[i] = m
	}
}

// One validated PARAM descriptor. Freeze skips register mutation/VALUES,
// but does NOT skip the first-descriptor stage transition. A trigger observes
// both latches BEFORE clearing them (even with no open VALUES file).
// The caller must retain whole-frame validation and error/duplicate policy.
func (s *sourceMetadataLatchCandidate) param(addr int, payload []byte, frozen bool) (*[2]sourceImpulseValue, error) {
	if s.epoch == 0 || addr < 0 || addr >= metadataWords || len(payload) == 0 || len(payload)%4 != 0 || len(payload)/2 > metadataWords-addr {
		return nil, errors.New("invalid metadata candidate descriptor")
	}
	var tick *[2]sourceImpulseValue
	if !frozen {
		s.put(addr, payload, false)
		if addr == 0x3100 {
			snapshot := [2]sourceImpulseValue{s.dword(impulseAddresses[0]), s.dword(impulseAddresses[1])}
			tick = &snapshot
			s.putImpulse(0, 0)
			s.putImpulse(1, 0)
		}
	}
	if !s.firstDescriptor {
		s.latchMetadata()
		s.firstDescriptor = true
	}
	return tick, nil
}

// TACH type 2 uses actual payload bytes. This is a latched change indicator,
// NOT RPM, pulse count, or a Float32 interpretation of the wire bytes.
// accepted is supplied by the real selected-rate/Freeze/storage gate.
func (s *sourceMetadataLatchCandidate) tach(i int, payload []byte, accepted bool) error {
	if s.epoch == 0 || i < 0 || i >= 2 {
		return errors.New("invalid TACH candidate channel")
	}
	if !accepted || len(payload) == 0 {
		return nil
	}
	old := s.last[i]
	for _, b := range payload {
		if b != old {
			s.putImpulse(i, 1)
			break
		}
	}
	s.last[i] = payload[len(payload)-1]
	return nil
}

// Numerical candidate for normal finite values only; do not attest x87
// exceptional behavior or window parity. Raw wire / archive bytes untouched.
func (s *sourceMetadataLatchCandidate) adcValue(i int, wire float32) (float32, error) {
	if i < 0 || i >= 8 {
		return 0, errors.New("invalid ADC candidate channel")
	}
	m := s.channel[i]
	if !m.RangeKnown || math.IsNaN(float64(m.Range)) || math.IsInf(float64(m.Range), 0) || math.IsNaN(float64(wire)) || math.IsInf(float64(wire), 0) {
		return 0, errors.New("unknown or nonfinite source factor/input")
	}
	v := float32(float64(wire) * float64(m.Range))
	if math.IsInf(float64(v), 0) {
		return 0, errors.New("source product overflows Float32")
	}
	return v, nil
}

// Plain GetSignal copies the stored physical sample. Filtered GetSignal
// and GetSpectrum divide by the CURRENT storage factor, not the factor
// used when an older sample was written. This candidate makes that domain
// change explicit; it is not a full FIR/FFT implementation.
func (s *sourceMetadataLatchCandidate) adcWindowInput(i int, stored float32, normalize bool) (float32, error) {
	if i < 0 || i >= 8 || math.IsNaN(float64(stored)) || math.IsInf(float64(stored), 0) {
		return 0, errors.New("invalid ADC window sample")
	}
	if !normalize {
		return stored, nil
	}
	m := s.channel[i]
	if !m.RangeKnown || m.Range == 0 || math.IsNaN(float64(m.Range)) || math.IsInf(float64(m.Range), 0) {
		return 0, errors.New("unknown or nonfinite source window factor")
	}
	v := float32(float64(stored) / float64(m.Range))
	if math.IsInf(float64(v), 0) {
		return 0, errors.New("source normalization overflows Float32")
	}
	return v, nil
}
