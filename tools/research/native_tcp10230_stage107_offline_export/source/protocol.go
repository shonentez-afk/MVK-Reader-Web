package main

import (
	"encoding/binary"
	"errors"
	"fmt"
	"math"
)

// Device message layout follows confirmed Native R4/Stage100 IDR and PCAP checks.
// This package is receive-only. It does not contain network command encoders.
const (
	instrumentPort        = 10230
	typeIdentity   uint32 = 0x00000001
	typeADC        uint32 = 0xFF800ADC
	typeTach       uint32 = 0xFF8001AC
	typeParam      uint32 = 0xFF800C0D
	typeAck        uint32 = 0x00010FF0
	typeDenied     uint32 = 0x00010FFF
	maxFrameSize          = 0x20000
	registerWords         = 0x4000
)

var acceptedRates = map[uint32]bool{512: true, 2048: true, 8192: true, 32768: true, 65536: true}
var errMalformed = errors.New("invalid MVK10230 application frame")

type Frame struct {
	Type uint32
	Raw  []byte
}

type Framer struct{ Tail []byte }

// Feed only reassembles; on any malformed envelope it stops instead of trying
// to resynchronize and falsely present untrusted bytes as valid measurements.
func (f *Framer) Feed(chunk []byte) ([]Frame, error) {
	f.Tail = append(f.Tail, chunk...)
	result := make([]Frame, 0, 4)
	for len(f.Tail) >= 8 {
		typ := binary.LittleEndian.Uint32(f.Tail[:4])
		n := binary.LittleEndian.Uint32(f.Tail[4:8])
		if n < 8 || n%4 != 0 || n > maxFrameSize {
			return result, fmt.Errorf("%w: size=%d type=%08X", errMalformed, n, typ)
		}
		switch typ {
		case typeADC:
			if n != 1052 {
				return result, fmt.Errorf("%w: ADC size=%d", errMalformed, n)
			}
		case typeTach:
			if n != 284 {
				return result, fmt.Errorf("%w: TACH size=%d", errMalformed, n)
			}
		case typeParam:
			if n < 32 {
				return result, fmt.Errorf("%w: PARAM size=%d", errMalformed, n)
			}
		case typeAck, typeDenied:
			if n != 8 {
				return result, fmt.Errorf("%w: reply size=%d", errMalformed, n)
			}
		case typeIdentity:
			// Identity size is variable in the original protocol.
		default:
			return result, fmt.Errorf("%w: unknown type=%08X size=%d", errMalformed, typ, n)
		}
		if len(f.Tail) < int(n) {
			break
		}
		raw := append([]byte(nil), f.Tail[:n]...)
		result = append(result, Frame{Type: typ, Raw: raw})
		f.Tail = f.Tail[n:]
	}
	return result, nil
}

type RegBlock struct {
	Addr    uint16
	Words   uint16
	Payload []byte
}

func decodeBlocks(raw []byte) ([]RegBlock, error) {
	if len(raw) < 32 || binary.LittleEndian.Uint32(raw[:4]) != typeParam {
		return nil, fmt.Errorf("%w: not parameter message", errMalformed)
	}
	count := binary.LittleEndian.Uint32(raw[24:28])
	if count > 4096 {
		return nil, fmt.Errorf("%w: excessive records=%d", errMalformed, count)
	}
	pos := 28
	blocks := make([]RegBlock, 0, minInt(int(count), 16))
	for i := uint32(0); i < count; i++ {
		if pos+4 > len(raw) {
			return nil, fmt.Errorf("%w: truncated record descriptor", errMalformed)
		}
		desc := binary.LittleEndian.Uint32(raw[pos : pos+4])
		pos += 4
		a, w := uint16(desc&0xffff), uint16(desc>>16)
		if w == 0 || w%2 != 0 || int(a)+int(w) > registerWords || pos+int(w)*2 > len(raw) {
			return nil, fmt.Errorf("%w: descriptor address=%04X words=%d", errMalformed, a, w)
		}
		blocks = append(blocks, RegBlock{a, w, raw[pos : pos+int(w)*2]})
		pos += int(w) * 2
	}
	if pos != len(raw) {
		return nil, fmt.Errorf("%w: trailing parameter bytes=%d", errMalformed, len(raw)-pos)
	}
	return blocks, nil
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ADC/TACH header is 8-byte envelope + 5 uint32 + little endian float32 samples.
type SampleHeader struct {
	Channel   int
	Rate      uint32
	Index     uint32
	NonFinite uint32
	Samples   int
}

func decodeSampleHeader(f Frame) (SampleHeader, error) {
	if f.Type != typeADC && f.Type != typeTach {
		return SampleHeader{}, fmt.Errorf("%w: not ADC or TACH", errMalformed)
	}
	required, samples := 1052, 256
	if f.Type == typeTach {
		required, samples = 284, 64
	}
	if len(f.Raw) != required {
		return SampleHeader{}, fmt.Errorf("%w: incorrect sample length", errMalformed)
	}
	channel := binary.LittleEndian.Uint32(f.Raw[20:24])
	rate := binary.LittleEndian.Uint32(f.Raw[24:28])
	if (f.Type == typeADC && channel >= 8) || (f.Type == typeTach && (channel < 8 || channel > 9)) || !acceptedRates[rate] {
		return SampleHeader{}, fmt.Errorf("%w: sample channel/rate=%d/%d", errMalformed, channel, rate)
	}
	var nonFinite uint32
	for offset := 28; offset < len(f.Raw); offset += 4 {
		bits := binary.LittleEndian.Uint32(f.Raw[offset : offset+4])
		if bits&0x7f800000 == 0x7f800000 {
			nonFinite++
		}
	}
	return SampleHeader{int(channel), rate, binary.LittleEndian.Uint32(f.Raw[12:16]), nonFinite, samples}, nil
}

type RegisterImage struct {
	Data  [registerWords * 2]byte
	Valid [registerWords]bool
}

func (r *RegisterImage) Put(b RegBlock) {
	a, z := int(b.Addr), int(b.Addr)+int(b.Words)
	copy(r.Data[a*2:z*2], b.Payload)
	for i := a; i < z; i++ {
		r.Valid[i] = true
	}
}
func (r *RegisterImage) Float32(wordAddr int) (float64, error) {
	if wordAddr < 0 || wordAddr+1 >= registerWords || !r.Valid[wordAddr] || !r.Valid[wordAddr+1] {
		return 0, errors.New("missing measurement registers")
	}
	return float64(math.Float32frombits(binary.LittleEndian.Uint32(r.Data[wordAddr*2 : (wordAddr+2)*2]))), nil
}
func (r *RegisterImage) Uint32(wordAddr int) (uint32, error) {
	if wordAddr < 0 || wordAddr+1 >= registerWords || !r.Valid[wordAddr] || !r.Valid[wordAddr+1] {
		return 0, errors.New("missing measurement registers")
	}
	return binary.LittleEndian.Uint32(r.Data[wordAddr*2 : (wordAddr+2)*2]), nil
}

var spectrumBandHz = []float64{.63, .8, 1, 1.25, 1.6, 2, 2.5, 3.15, 4, 5, 6.3, 8, 10, 12.5, 16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000}

type CalculatedChannel struct {
	TimeUTC         string          `json:"time_utc"`
	Update          uint64          `json:"update"`
	Channel         int             `json:"adc"`
	BandsHz         []float64       `json:"third_octave_hz"`
	AccelerationRMS []any           `json:"third_octave_acceleration_rms"`
	BandRMS         []any           `json:"band_rms"`
	BandPeak        []any           `json:"band_peak_equiv"`
	BandSpan        []any           `json:"band_span_equiv"`
	Status          uint32          `json:"status_raw"`
	StatusHex       string          `json:"status_hex"`
	NotReady        map[string]bool `json:"not_ready"`
	NonFinite       int             `json:"nonfinite_fields"`
}

func jsonFloat(v float64) any {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return nil
	}
	return v
}
func decodeCalculated(r *RegisterImage, channel int, timestamp string, update uint64) (CalculatedChannel, error) {
	base := 0x2000 + 0x200*channel
	out := CalculatedChannel{TimeUTC: timestamp, Update: update, Channel: channel + 1, BandsHz: spectrumBandHz,
		AccelerationRMS: make([]any, 43), BandRMS: make([]any, 24), BandPeak: make([]any, 24), BandSpan: make([]any, 24)}
	for i := 0; i < 43; i++ {
		v, e := r.Float32(base + 2 + 2*i)
		if e != nil {
			return out, e
		}
		out.AccelerationRMS[i] = jsonFloat(v)
		if out.AccelerationRMS[i] == nil {
			out.NonFinite++
		}
	}
	for i := 0; i < 24; i++ {
		v, e := r.Float32(base + 0x60 + 2*i)
		if e != nil {
			return out, e
		}
		out.BandRMS[i] = jsonFloat(v)
		if out.BandRMS[i] == nil {
			out.NonFinite++
		}
	}
	for i := 0; i < 24; i++ {
		v, e := r.Float32(base + 0xA0 + 2*i)
		if e != nil {
			return out, e
		}
		out.BandPeak[i] = jsonFloat(v)
		if out.BandPeak[i] == nil {
			out.NonFinite++
		}
	}
	for i := 0; i < 24; i++ {
		v, e := r.Float32(base + 0xE0 + 2*i)
		if e != nil {
			return out, e
		}
		out.BandSpan[i] = jsonFloat(v)
		if out.BandSpan[i] == nil {
			out.NonFinite++
		}
	}
	status, e := r.Uint32(base + 0x120)
	if e != nil {
		return out, e
	}
	out.Status = status
	out.StatusHex = fmt.Sprintf("0x%08X", status)
	out.NotReady = map[string]bool{"fs16": status&16 != 0, "fs64": status&32 != 0, "fs512": status&64 != 0}
	return out, nil
}
