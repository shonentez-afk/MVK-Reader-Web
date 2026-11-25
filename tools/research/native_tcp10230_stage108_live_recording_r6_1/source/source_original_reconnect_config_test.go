package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"math"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func retainedConfigRange(addr uint16, factor float32) RegBlock {
	p := make([]byte, 4)
	binary.LittleEndian.PutUint32(p, math.Float32bits(factor))
	return RegBlock{Addr: addr, Words: 2, Payload: p}
}

func TestSourceTask2ReconnectRetainsOnlyOriginalADCConfig(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "reconnect-config")
	m, err := NewMonitor(dir, "LIVE_SOURCE_SET_RATE_APPROVED", "127.0.0.1")
	if err != nil {
		t.Fatal(err)
	}
	defer m.CloseFiles()
	m.sourceOriginalRXGate = newSourceOriginalReceiveGate()
	m.sourceOriginalTask2Stage = newSourceOriginalTask2Lifecycle()
	m.sourceTCP = &sourceTCPLedger{}
	m.liveProgressEnabled = true

	var segments [][]byte
	begin := func() {
		t.Helper()
		if e := m.sourceTCP.begin(m); e != nil {
			t.Fatal(e)
		}
		m.sourceOriginalTask2Stage.onConnected(m.summary.SourceNonemptyParameters)
		segments = append(segments, nil)
	}
	feed := func(raw []byte) {
		t.Helper()
		segments[len(segments)-1] = append(segments[len(segments)-1], raw...)
		if e := m.ProcessChunk(raw, time.Now()); e != nil {
			t.Fatal(e)
		}
	}
	finish := func(why string) {
		m.sourceOriginalTask2Stage.onDisconnected(why)
		m.sourceTCP.finish(m, why)
	}
	adc1 := &m.sourceOriginalStorage.channels[0]
	adc2 := &m.sourceOriginalStorage.channels[1]
	units1 := append([]byte{'m', '/', 's', '2'}, make([]byte, 28)...)
	units2 := append([]byte{'m', 'm', '/', 's'}, make([]byte, 28)...)
	adc2Half := []byte{'c', 'm'}
	status := RegBlock{Addr: 0x1006, Words: 2, Payload: make([]byte, 4)}

	begin()
	feed(makeParam([]RegBlock{
		retainedConfigRange(0x010e, 2.5),
		// Same socket: suffix updates shared config, but must not
		// relatch either ADC's live graph before a retry.
		retainedConfigRange(0x010e, 4),
		{Addr: 0x0110, Words: 16, Payload: units1},
		retainedConfigRange(0x020e, 8),
		{Addr: 0x0210, Words: 16, Payload: units2},
		status,
	}))
	if adc1.rangeState == nil || adc1.rangeState.Single != 2.5 ||
		adc1.rangeState.UnitsRawLE != "" || adc2.rangeState.Single != 1 {
		t.Fatal("first descriptor must latch before the rest of the frame")
	}
	feed(makeSample(typeADC, 0, 65536, 0))
	finish("REMOTE_DISCONNECTED")

	begin()
	if adc1.rxPos != 256 || adc1.rangeState.Single != 2.5 {
		t.Fatal("new socket replaced form-owned storage or its pre-latch scale")
	}
	if _, e := m.image.Uint32(0x1006); e == nil {
		t.Fatal("previous socket Status0 leaked into the forensic image")
	}
	m.sourceOriginalRXGate.setFreeze(true)
	feed(makeParam(nil))
	if adc1.rangeState.SocketAttempt != 1 || m.sourceOriginalTask2Stage.stage != 0 {
		t.Fatal("empty PARAM must not relatch or leave Stage0")
	}
	feed(makeParam([]RegBlock{retainedConfigRange(0x010e, 99), status}))
	if adc1.rangeState.Single != 4 || adc1.rangeState.SocketAttempt != 2 ||
		adc1.rangeState.UnitsRawLE != hex.EncodeToString(units1) ||
		adc2.rangeState.Single != 8 || adc2.rangeState.UnitsRawLE != hex.EncodeToString(units2) ||
		m.sourceOriginalTask2Stage.stage != 1 {
		t.Fatalf("frozen first nonempty PARAM lost retained config: ADC1=%+v ADC2=%+v", adc1.rangeState, adc2.rangeState)
	}
	if _, e := m.image.Uint32(0x010e); e == nil ||
		m.sourceOriginalTask2Stage.knownSystem0 {
		t.Fatal("frozen words or retained config leaked into new socket status")
	}
	m.sourceOriginalRXGate.setFreeze(false)
	feed(makeSample(typeADC, 0, 65536, 256))
	got, err := m.sourceOriginalStorage.window(0, 0, 512)
	if err != nil || math.Float32frombits(binary.LittleEndian.Uint32(got[:4])) != .3125 ||
		math.Float32frombits(binary.LittleEndian.Uint32(got[1024:1028])) != .5 {
		t.Fatalf("storage failed to preserve prior scale and apply retry scale only to new samples: %v", err)
	}
	finish("REMOTE_DISCONNECTED")

	begin()
	// A valid 32-bit wire descriptor straddles Range and Units.
	// It retains Range's high word and updates the first Units word;
	// the rest comes from retained config. The following Range write
	// is persisted but excluded from this attempt's initial latch.
	feed(makeParam([]RegBlock{
		{Addr: 0x020f, Words: 2, Payload: append([]byte{0x00, 0x41}, adc2Half...)},
		retainedConfigRange(0x020e, 16),
	}))
	expected2 := append(append([]byte{}, adc2Half...), units2[2:]...)
	if adc2.rangeState.Single != 8 || adc2.rangeState.SocketAttempt != 3 ||
		adc2.rangeState.UnitsRawLE != hex.EncodeToString(expected2) ||
		adc1.rangeState.Single != 4 || adc1.rangeState.UnitsRawLE != hex.EncodeToString(units1) {
		t.Fatalf("first partial descriptor was not merged into shared config: ADC1=%+v ADC2=%+v", adc1.rangeState, adc2.rangeState)
	}
	if m.image.Valid[0x0211] || m.image.Valid[0x1006] || m.image.Valid[0x010e] {
		t.Fatal("retained words must not appear in the new socket forensic image")
	}
	// Independent thresholds and existing safety policy remain unchanged.
	finish("STOPPED_BY_USER")
	report, _, err := m.Finalize("STOPPED_BY_USER")
	if err != nil {
		t.Fatal(err)
	}
	if report.SourceTCPConnectionCount != 3 || !report.SourceTCPMultiSocket ||
		!report.SourceTCPSegmentCopiesVerified || isSafeCaptureForExport(report) == nil {
		t.Fatalf("multi-socket evidence safeguards changed: %+v", report)
	}
	for i, want := range segments {
		got, err := os.ReadFile(filepath.Join(dir, fmt.Sprintf("SOURCE_TCP_SEGMENT_%04d.raw", i+1)))
		if err != nil || !bytes.Equal(got, want) {
			t.Fatalf("socket %d raw changed: %v", i+1, err)
		}
	}
}

// Use the production retry, socket ledger, framer and ring on two real
// loopback TCP connections (no physical device or SetRate permission).
func TestSourceTask2PassiveWireRetryKeepsADCConfig(t *testing.T) {
	listener, err := net.ListenTCP("tcp4", &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if err := listener.SetDeadline(time.Now().Add(5 * time.Second)); err != nil {
		t.Fatal(err)
	}
	units := append([]byte("mm/s"), make([]byte, 28)...)
	first := makeParam([]RegBlock{
		retainedConfigRange(0x010e, 4),
		{Addr: 0x0110, Words: 16, Payload: units},
	})
	// The new socket has no ADC config at all. In the original it
	// still scales the post-Stage0 sample by 4 using retained config.
	second := append(makeParam([]RegBlock{retainedConfigRange(0x1006, 0)}),
		makeSample(typeADC, 0, 65536, 0)...)
	sent := make(chan error, 1)
	go func() {
		for _, packet := range [][]byte{first, second} {
			conn, err := listener.AcceptTCP()
			if err != nil {
				sent <- err
				return
			}
			_ = conn.SetWriteDeadline(time.Now().Add(time.Second))
			n, err := conn.Write(packet)
			_ = conn.Close()
			if err != nil || n != len(packet) {
				sent <- fmt.Errorf("loopback write %d/%d: %v", n, len(packet), err)
				return
			}
		}
		sent <- nil
	}()
	m, err := NewMonitor(filepath.Join(t.TempDir(), "passive-wire-retry"),
		"LIVE_TASK2_PASSIVE_RECONNECT_APPROVED", "127.0.0.1")
	if err != nil {
		t.Fatal(err)
	}
	defer m.CloseFiles()
	m.sourceOriginalRXGate = newSourceOriginalReceiveGate()
	m.sourceOriginalTask2Stage = newSourceOriginalTask2Lifecycle()
	m.sourceTCP = &sourceTCPLedger{}
	m.sourceAfterRAWReconnect = true
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	reason, err := sourceTask2CaptureAddressRetry(ctx, m, listener.Addr().String(),
		0, uint64(len(first)+len(second)), nil)
	if err != nil || reason != "SIZE_LIMIT_REACHED" {
		t.Fatalf("passive retry ended %s: %v", reason, err)
	}
	if e := <-sent; e != nil {
		t.Fatal(e)
	}
	r := m.sourceOriginalStorage.channels[0].rangeState
	got, err := m.sourceOriginalStorage.window(0, 0, 256)
	if err != nil || r == nil || r.Single != 4 || r.SocketAttempt != 2 ||
		r.UnitsRawLE != hex.EncodeToString(units) ||
		math.Float32frombits(binary.LittleEndian.Uint32(got[:4])) != .5 {
		t.Fatalf("wrong storage bytes or range after actual passive retry: range=%+v err=%v", r, err)
	}
	report, _, err := m.Finalize(reason)
	if err != nil || report.SourceTCPConnectionCount != 2 ||
		report.SourceSetRateBytes != 0 || !report.ReadOnly || !report.SourceTCPSegmentCopiesVerified ||
		isSafeCaptureForExport(report) == nil {
		t.Fatalf("retry leaked SetRate or certified combined source: reason=%s err=%v", reason, err)
	}
}
