package main

import (
	"encoding/binary"
	"math"
	"testing"
)

func metaDword(v uint32) []byte  { b := make([]byte, 4); binary.LittleEndian.PutUint32(b, v); return b }
func metaFloat(v float32) []byte { return metaDword(math.Float32bits(v)) }
func mustMetaParam(t *testing.T, s *sourceMetadataLatchCandidate, addr int, payload []byte, frozen bool) *[2]sourceImpulseValue {
	t.Helper()
	r, e := s.param(addr, payload, frozen)
	if e != nil {
		t.Fatal(e)
	}
	return r
}
func mustMetaTach(t *testing.T, s *sourceMetadataLatchCandidate, i int, p []byte, accepted bool) {
	t.Helper()
	if e := s.tach(i, p, accepted); e != nil {
		t.Fatal(e)
	}
}
func assertMetaImpulse(t *testing.T, s *sourceMetadataLatchCandidate, i int, v uint32, known bool) {
	t.Helper()
	if a := s.dword(impulseAddresses[i]); a != (sourceImpulseValue{v, known}) {
		t.Fatalf("impulse %d got %+v want %d/%t", i, a, v, known)
	}
}
func TestSourceMetadataFirstDescriptorAndReconnect(t *testing.T) {
	s := newSourceMetadataLatchCandidate()
	s.newSocket()
	if v, e := s.adcValue(0, 2); e != nil || v != 2 {
		t.Fatal("constructor range", v, e)
	}
	// First descriptor carries range and a short NUL-terminated unit string.
	mustMetaParam(t, s, 0x10e, append(metaFloat(4), []byte{'m', '/', 's', 0}...), false)
	m := s.channel[0]
	if !m.FromDescriptor || !m.RangeKnown || !m.RangeCurrentSocket || m.Range != 4 || !m.UnitsKnown || !m.UnitsCurrentSocket || m.Units != "m/s" {
		t.Fatalf("metadata %+v", m)
	}
	if v, e := s.adcValue(0, 2); e != nil || v != 8 {
		t.Fatal("nonunit scaling", v, e)
	}
	// Later descriptor in SAME packet/epoch does not alter storage metadata.
	mustMetaParam(t, s, 0x10e, metaFloat(9), false)
	if s.channel[0].Range != 4 {
		t.Fatal("suffix changed latched range")
	}
	if s.channel[1].RangeKnown {
		t.Fatal("missing channel invented")
	}
	if _, e := s.adcValue(1, 2); e == nil {
		t.Fatal("unknown range accepted")
	}
	s.newSocket()
	if s.channel[0].Range != 4 {
		t.Fatal("reconnect prematurely reset storage")
	}
	// Frozen first descriptor is still a Stage0->1 transition using retained image.
	mustMetaParam(t, s, 0x10e, metaFloat(12), true)
	m = s.channel[0]
	if m.Range != 9 || m.RangeCurrentSocket || m.UnitsCurrentSocket {
		t.Fatalf("frozen metadata %+v", m)
	}
	mustMetaParam(t, s, 0x10e, metaFloat(12), false)
	if s.channel[0].Range != 9 {
		t.Fatal("later unfreeze relatched")
	}
	s.newSocket()
	mustMetaParam(t, s, 0x10e, metaFloat(0), false)
	if m = s.channel[0]; m.Range != 1 || m.RangeBits != 0 || !m.RangeCurrentSocket {
		t.Fatalf("zero fallback %+v", m)
	}
}
func TestSourceMetadataRangesAndUnits(t *testing.T) {
	for _, tc := range []struct {
		name  string
		bits  uint32
		want  float32
		valid bool
	}{
		{"negative_zero", 0x80000000, 1, true}, {"negative_finite", math.Float32bits(-2), -2, true},
		{"infinite", 0x7f800000, 0, false}, {"nan", 0x7fc00000, 0, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := newSourceMetadataLatchCandidate()
			s.newSocket()
			mustMetaParam(t, s, 0x80e, metaDword(tc.bits), false)
			if m := s.channel[7]; !m.RangeKnown || m.RangeBits != tc.bits {
				t.Fatal(m)
			}
			v, e := s.adcValue(7, 2)
			if (e == nil) != tc.valid || tc.valid && v != 2*tc.want {
				t.Fatal(v, e)
			}
		})
	}
	for _, tc := range []struct {
		name  string
		raw   []byte
		text  string
		known bool
	}{
		{"partial_no_nul", []byte{'a', 'b', 'c', 'd'}, "", false},
		{"nul_terminated", []byte{'a', 0, 'x', 'y'}, "a", true},
		{"byte_chars", []byte{0xb0, 'C', 0, 0}, "\u00b0C", true},
		{"all_32", []byte("12345678901234567890123456789012"), "12345678901234567890123456789012", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := newSourceMetadataLatchCandidate()
			s.newSocket()
			mustMetaParam(t, s, 0x110, tc.raw, false)
			m := s.channel[0]
			if m.Units != tc.text || m.UnitsKnown != tc.known || m.UnitsCurrentSocket != tc.known {
				t.Fatal(m)
			}
		})
	}
}
func TestSourceMetadataImpulseTriggerFreezeAndReconnect(t *testing.T) {
	s := newSourceMetadataLatchCandidate()
	s.newSocket()
	assertMetaImpulse(t, s, 0, 0, false)
	assertMetaImpulse(t, s, 1, 0, false)
	mustMetaTach(t, s, 0, []byte{0, 1, 0}, true)
	mustMetaTach(t, s, 1, []byte{9}, false)
	assertMetaImpulse(t, s, 0, 1, true)
	assertMetaImpulse(t, s, 1, 0, false)
	if tick := mustMetaParam(t, s, 0x3100, metaDword(7), true); tick != nil {
		t.Fatal("frozen trigger")
	}
	assertMetaImpulse(t, s, 0, 1, true)
	tick := mustMetaParam(t, s, 0x3100, metaDword(7), false)
	if tick == nil || (*tick)[0] != (sourceImpulseValue{1, true}) || (*tick)[1].Known {
		t.Fatal(tick)
	}
	assertMetaImpulse(t, s, 0, 0, true)
	assertMetaImpulse(t, s, 1, 0, true)
	mustMetaTach(t, s, 0, []byte{0}, true)
	assertMetaImpulse(t, s, 0, 0, true)
	mustMetaTach(t, s, 1, []byte{2, 2}, true)
	s.newSocket()
	assertMetaImpulse(t, s, 1, 1, true)
	// Reconnect does not clear last byte; trigger reset does not clear it either.
	tick = mustMetaParam(t, s, 0x3100, metaDword(8), false)
	if (*tick)[1].Value != 1 {
		t.Fatal(tick)
	}
	mustMetaTach(t, s, 1, []byte{2}, true)
	assertMetaImpulse(t, s, 1, 0, true)
	// A real register descriptor can overwrite the latch; suffix occurs after reset.
	mustMetaParam(t, s, 0x31fe, metaDword(42), false)
	assertMetaImpulse(t, s, 1, 42, true)
	tick = mustMetaParam(t, s, 0x3100, metaDword(9), false)
	if (*tick)[1].Value != 42 {
		t.Fatal(tick)
	}
	assertMetaImpulse(t, s, 1, 0, true)
}
func TestSourceMetadataImpulseExhaustive(t *testing.T) {
	// Independent adjacent-byte transition oracle; compare all 3^4 byte sequences,
	// prior levels, pre-existing latches and admitted/rejected gate decisions.
	for prev := 0; prev < 3; prev++ {
		for prior := 0; prior < 2; prior++ {
			for encoded := 0; encoded < 81; encoded++ {
				for _, accept := range []bool{false, true} {
					s := newSourceMetadataLatchCandidate()
					s.newSocket()
					s.last[0] = byte(prev)
					s.putImpulse(0, uint32(prior))
					b := make([]byte, 4)
					n := encoded
					for i := range b {
						b[i] = byte(n % 3)
						n /= 3
					}
					want := uint32(prior)
					last := byte(prev)
					if accept {
						for _, v := range b {
							if last != v {
								want = 1
							}
							last = v
						}
					}
					mustMetaTach(t, s, 0, b, accept)
					assertMetaImpulse(t, s, 0, want, true)
					if s.last[0] != last {
						t.Fatal("last byte mismatch")
					}
				}
			}
		}
	}
}
func TestSourceMetadataRejectInvalidWithoutMutation(t *testing.T) {
	s := newSourceMetadataLatchCandidate()
	s.newSocket()
	for _, addr := range []int{-1, 0x4000, 0x3fff} {
		if _, e := s.param(addr, metaDword(1), false); e == nil {
			t.Fatal("invalid addr", addr)
		}
	}
	for _, p := range [][]byte{nil, {1, 2}, {1, 2, 3}} {
		if _, e := s.param(0x10e, p, false); e == nil {
			t.Fatal("invalid payload")
		}
	}
	if s.firstDescriptor || s.channel[0].Range != 1 {
		t.Fatal("invalid input mutated metadata")
	}
}

func TestSourceMetadataPlainFilteredAndSpectrumDomains(t *testing.T) {
	s := newSourceMetadataLatchCandidate()
	s.newSocket()
	mustMetaParam(t, s, 0x10e, metaFloat(4), false)
	stored, e := s.adcValue(0, 2)
	if e != nil || stored != 8 {
		t.Fatal(stored, e)
	}
	plain, e := s.adcWindowInput(0, stored, false)
	if e != nil || plain != 8 {
		t.Fatal(plain, e)
	}
	norm, e := s.adcWindowInput(0, stored, true)
	if e != nil || norm != 2 {
		t.Fatal(norm, e)
	}
	// Synthetic identity filter: restoration multiplies once, not twice.
	restored, e := s.adcValue(0, norm)
	if e != nil || restored != 8 {
		t.Fatal(restored, e)
	}
	s.newSocket()
	mustMetaParam(t, s, 0x10e, metaFloat(2), false)
	norm, e = s.adcWindowInput(0, stored, true)
	if e != nil || norm != 4 {
		t.Fatal(norm, e)
	}
	plain, e = s.adcWindowInput(0, stored, false)
	if e != nil || plain != 8 {
		t.Fatal("old sample retroactively rescaled", plain, e)
	}
}
