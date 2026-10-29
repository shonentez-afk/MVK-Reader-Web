package main

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func makeSample(typ uint32, channel, rate, index uint32) []byte {
	size, n := 1052, 256
	if typ == typeTach {
		size, n = 284, 64
	}
	b := make([]byte, size)
	binary.LittleEndian.PutUint32(b[0:], typ)
	binary.LittleEndian.PutUint32(b[4:], uint32(size))
	binary.LittleEndian.PutUint32(b[12:], index)
	binary.LittleEndian.PutUint32(b[20:], channel)
	binary.LittleEndian.PutUint32(b[24:], rate)
	for j := 0; j < n; j++ {
		binary.LittleEndian.PutUint32(b[28+4*j:], 0x3e000000)
	}
	return b
}
func makeParam(parts []RegBlock) []byte {
	size := 28
	for _, p := range parts {
		size += 4 + len(p.Payload)
	}
	buf := make([]byte, size)
	binary.LittleEndian.PutUint32(buf[0:], typeParam)
	binary.LittleEndian.PutUint32(buf[4:], uint32(size))
	binary.LittleEndian.PutUint32(buf[24:], uint32(len(parts)))
	pos := 28
	for _, p := range parts {
		desc := uint32(p.Words)<<16 | uint32(p.Addr)
		binary.LittleEndian.PutUint32(buf[pos:], desc)
		pos += 4
		copy(buf[pos:], p.Payload)
		pos += len(p.Payload)
	}
	return buf
}
func makeAux() []byte {
	parts := make([]RegBlock, 8)
	for ch := 0; ch < 8; ch++ {
		payload := make([]byte, 580)
		for i := 0; i < 144; i++ {
			// Distinct values and float32 bits; first band for ADC4 = 3.0
			binary.LittleEndian.PutUint32(payload[4+i*4:], 0x3f800000+uint32(ch*0x80000+i))
		}
		binary.LittleEndian.PutUint32(payload[576:], uint32(ch*16))
		parts[ch] = RegBlock{Addr: uint16(0x2000 + ch*0x200), Words: 0x122, Payload: payload}
	}
	return makeParam(parts)
}
func makeIdentity() []byte {
	b := make([]byte, 264)
	binary.LittleEndian.PutUint32(b[:4], typeIdentity)
	binary.LittleEndian.PutUint32(b[4:8], 264)
	return b
}
func runTestMonitor(t *testing.T, data []byte, split int) (Summary, string) {
	t.Helper()
	m, err := NewMonitor(filepath.Join(t.TempDir(), "test"), "OFFLINE_REPLAY", "")
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < len(data); i += split {
		end := i + split
		if end > len(data) {
			end = len(data)
		}
		if err := m.ProcessChunk(data[i:end], time.Now()); err != nil {
			t.Fatal(err)
		}
	}
	res, z, e := m.Finalize("TEST_DONE")
	if e != nil {
		t.Fatal(e)
	}
	return res, z
}

func TestFragmentedAux4700AndAllFields(t *testing.T) {
	a := makeAux()
	if len(a) != 4700 {
		t.Fatal(len(a))
	}
	res, z := runTestMonitor(t, append(makeIdentity(), a...), 7)
	if res.IdentityFrames != 1 || res.Aux4700 != 1 || res.TotalFrames != 2 || res.InvalidFrames != 0 || res.TailBytes != 0 {
		t.Fatalf("bad summary: %+v", res)
	}
	if res.Result != "VALID_FRAMES" {
		t.Fatalf("result: %v", res.Result)
	}
	zr, e := zip.OpenReader(z)
	if e != nil {
		t.Fatal(e)
	}
	defer zr.Close()
	found := map[string]bool{}
	for _, f := range zr.File {
		found[f.Name] = true
	}
	for _, name := range []string{"incoming.raw", "chunks.csv", "frames.csv", "aux4700.jsonl", "summary.json", "summary_ru.txt"} {
		if !found[name] {
			t.Errorf("zip missing %s", name)
		}
	}
	raw, e := os.ReadFile(filepath.Join(filepath.Dir(z), "aux4700.jsonl"))
	if e != nil {
		t.Fatal(e)
	}
	lines := bytes.Split(bytes.TrimSpace(raw), []byte("\n"))
	if len(lines) != 8 {
		t.Fatalf("got %d channels, expected 8", len(lines))
	}
	var c CalculatedChannel
	if e = json.Unmarshal(lines[3], &c); e != nil {
		t.Fatal(e)
	}
	if len(c.AccelerationRMS) != 43 || len(c.BandRMS) != 24 || len(c.BandPeak) != 24 || len(c.BandSpan) != 24 || c.Channel != 4 {
		t.Fatalf("calculated fields incorrect %+v", c)
	}
}
func TestFull32800RegisterSnapshot(t *testing.T) {
	frame := makeParam([]RegBlock{{Addr: 0, Words: registerWords, Payload: make([]byte, registerWords*2)}})
	if len(frame) != 32800 {
		t.Fatal(len(frame))
	}
	res, _ := runTestMonitor(t, frame, 201)
	if res.FullSnapshots != 1 || res.RegisterBlocks != 1 || res.RegisterUpdates != 1 || res.CaptureOnly {
		t.Fatalf("snapshot %+v", res)
	}
}
func TestSequenceDiscontinuityRecorded(t *testing.T) {
	stream := append(makeSample(typeADC, 0, 65536, 128), makeSample(typeADC, 0, 65536, 800)...)
	res, _ := runTestMonitor(t, stream, 1030)
	if res.Channels[0].SequenceDiscontinuities != 1 || res.Channels[0].Samples != 512 {
		t.Fatalf("sequence %+v", res.Channels[0])
	}
}
func TestUnknownFrameRetainsOriginalRaw(t *testing.T) {
	bad := make([]byte, 8)
	binary.LittleEndian.PutUint32(bad[:4], 0xDEADBEEF)
	binary.LittleEndian.PutUint32(bad[4:], 8)
	stream := append(makeIdentity(), bad...)
	res, z := runTestMonitor(t, stream, 1000)
	if res.TotalFrames != 1 || !res.CaptureOnly || res.InvalidFrames != 1 {
		t.Fatalf("bad handling %+v", res)
	}
	saved, e := os.ReadFile(filepath.Join(filepath.Dir(z), "incoming.raw"))
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(saved, stream) {
		t.Fatal("raw capture changed during diagnostic")
	}
}
func TestIncompleteAtEndIsMarked(t *testing.T) {
	res, _ := runTestMonitor(t, makeAux()[:983], 13)
	if res.TailBytes != 983 || res.Result != "VALID_FRAMES_WITH_INCOMPLETE_LAST_FRAME" {
		t.Fatalf("incomplete not marked %+v", res)
	}
}
func TestNoDataIsReported(t *testing.T) {
	res, _ := runTestMonitor(t, nil, 4)
	if res.Result != "NO_DATA" || res.TotalFrames != 0 {
		t.Fatalf("no data %+v", res)
	}
}
func TestBadParamDescriptorRemainsRaw(t *testing.T) {
	bad := makeParam([]RegBlock{{Addr: 0x3fff, Words: 2, Payload: make([]byte, 4)}})
	res, _ := runTestMonitor(t, bad, 2048)
	if !res.CaptureOnly || res.InvalidFrames != 1 {
		t.Fatalf("bad register handling %+v", res)
	}
}
func TestLiveConnectionSendsNoApplicationBytes(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	payload := append(makeIdentity(), makeAux()...)
	result := make(chan error, 1)
	go func() {
		c, e := ln.Accept()
		if e != nil {
			result <- e
			return
		}
		defer c.Close()
		if _, e = c.Write(payload[:3]); e != nil {
			result <- e
			return
		}
		if _, e = c.Write(payload[3:]); e != nil {
			result <- e
			return
		}
		_ = c.SetReadDeadline(time.Now().Add(600 * time.Millisecond))
		buf := make([]byte, 256)
		n, e := c.Read(buf)
		if n != 0 {
			result <- errorsNew("client unexpectedly transmitted application bytes")
			return
		}
		if e != nil && !strings.Contains(e.Error(), "timeout") && e != io.EOF {
			result <- e
			return
		}
		result <- nil
	}()
	m, e := NewMonitor(filepath.Join(t.TempDir(), "live"), "LIVE_READ_ONLY", "127.0.0.1")
	if e != nil {
		t.Fatal(e)
	}
	reason, e := liveCaptureAddress(context.Background(), m, ln.Addr().String(), 2, 32*1024*1024)
	if e != nil {
		t.Fatal(e)
	}
	res, _, e := m.Finalize(reason)
	if e != nil {
		t.Fatal(e)
	}
	if res.IdentityFrames != 1 || res.Aux4700 != 1 || res.TotalFrames != 2 {
		t.Fatalf("live local server summary %+v", res)
	}
	select {
	case err := <-result:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("no fake server completion")
	}
}
func errorsNew(s string) error { return &localError{s} }

type localError struct{ s string }

func (e *localError) Error() string { return e.s }
