package main

import (
	"encoding/binary"
	"encoding/hex"
	"math"
)

// Compact projection of the source form's ADC configuration cell lists.
// A socket reset discards the forensic image but does not reset these cells
// or the storage objects. Keep only the 2 Range and 16 Units words per ADC:
// they must never feed Status0, PageStatus, VALUES, or the RAW verifier.
const sourceOriginalADCUnitsWords = 16
const sourceOriginalADCConfigWords = 2 + sourceOriginalADCUnitsWords

type sourceOriginalADCConfigChannel struct {
	words [sourceOriginalADCConfigWords * 2]byte
	valid [sourceOriginalADCConfigWords]bool
}
type sourceOriginalADCConfig [8]sourceOriginalADCConfigChannel

func sourceOriginalConfigWord(ch int) int { return 0x10e + ch*0x100 }

func (m *Monitor) storeSourcePARAMDescriptor(b RegBlock) {
	m.image.Put(b)
	if m.sourceOriginalRXGate == nil {
		return
	}
	start, end := int(b.Addr), int(b.Addr)+int(b.Words)
	for i := range m.sourceOriginalADCConfig {
		first := sourceOriginalConfigWord(i)
		lo, hi := max(first, start), min(first+sourceOriginalADCConfigWords, end)
		if lo >= hi {
			continue
		}
		c := &m.sourceOriginalADCConfig[i]
		copy(c.words[2*(lo-first):2*(hi-first)], b.Payload[2*(lo-start):2*(hi-start)])
		for word := lo; word < hi; word++ {
			c.valid[word-first] = true
		}
	}
}

func (config *sourceOriginalADCConfig) rangeState(ch int) sourceOriginalRangeState {
	c := &config[ch]
	s := sourceOriginalRangeState{Single: 1, Origin: "UNOBSERVED_REGISTER_PROVISIONAL_ONE", RegisterWord: sourceOriginalConfigWord(ch), Usable: true}
	if c.valid[0] && c.valid[1] {
		s.RegisterRawLE = hex.EncodeToString(c.words[:4])
		v := math.Float32frombits(binary.LittleEndian.Uint32(c.words[:4]))
		switch {
		case v == 0:
			s.Origin = "REGISTER_ZERO_FALLBACK_ONE"
		case finiteF32(v) && v > 0:
			s.Single = v
			s.Origin = "REGISTER_FLOAT32"
		default:
			s.Single = 0
			s.Origin = "INVALID_REGISTER_NO_CALCULATION"
			s.Usable = false
		}
	}
	for _, valid := range c.valid[2:] {
		if !valid {
			return s
		}
	}
	s.UnitsRawLE = hex.EncodeToString(c.words[4:])
	return s
}
