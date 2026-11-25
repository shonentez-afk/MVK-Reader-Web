package main

import (
	"bytes"
	"context"
	"errors"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSourceFreezeAppliesBeforeAdmissionOfInFlightADC(t *testing.T) {
	m, marks := testLiveWriterMonitor(t)
	if e := m.sourceOriginalRXGate.selectRate(65536); e != nil {
		t.Fatal(e)
	}
	localCommands := make(chan string, 3)
	m.sourceOperatorRateChan = localCommands
	queueMark(t, marks, 1, "data_begin")
	packet0 := sourceLiveWriterSample(typeADC, 0, 65536, 0, 0x3f800000)
	packet1 := sourceLiveWriterSample(typeADC, 0, 65536, 1, 0x40000000)
	packet2 := sourceLiveWriterSample(typeADC, 0, 65536, 2, 0x40400000)
	listener, e := net.Listen("tcp4", "127.0.0.1:0")
	if e != nil {
		t.Fatal(e)
	}
	defer listener.Close()
	accepted := make(chan error, 1)
	go func() {
		c, e := listener.Accept()
		if e != nil {
			accepted <- e
			return
		}
		defer c.Close()
		if _, e = c.Write(append(append([]byte{}, packet0...), packet1[:28]...)); e != nil {
			accepted <- e
			return
		}
		until := time.Now().Add(time.Second)
		for {
			info, e := os.Stat(filepath.Join(m.dir, "incoming.raw"))
			if e == nil && info.Size() >= int64(len(packet0)+28) {
				break
			}
			if time.Now().After(until) {
				accepted <- errors.New("partial frame was not received")
				return
			}
			time.Sleep(2 * time.Millisecond)
		}
		time.Sleep(75 * time.Millisecond) // RX returned to read, waiting for packet1 payload.
		localCommands <- "FREEZE 1"
		time.Sleep(75 * time.Millisecond) // queued while read waits; no bytes yet delivered.
		if _, e = c.Write(packet1[28:]); e != nil {
			accepted <- e
			return
		}
		time.Sleep(75 * time.Millisecond)
		if _, e = c.Write(packet2); e != nil {
			accepted <- e
			return
		}
		accepted <- nil
	}()
	reason, e := liveCaptureAddress(context.Background(), m, listener.Addr().String(), 2, 65536)
	if e != nil {
		t.Fatal(e)
	}
	if e = <-accepted; e != nil {
		t.Fatal(e)
	}
	report, _, e := m.Finalize(reason)
	if e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(m.dir, "SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin")
	data, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	g := m.sourceOriginalRXGate.receipt().Channels[0]
	t.Logf("end=%s RAW=%v written=%X admitted=%d skippedFreeze=%d", reason, report.RawBytes, data, g.StoredGateElements, g.FrozenSkippedElements)
	raw, e := os.ReadFile(filepath.Join(m.dir, "incoming.raw"))
	if e != nil || !bytes.Equal(raw, bytes.Join([][]byte{packet0, packet1, packet2}, nil)) {
		t.Fatalf("Freeze changed the wire capture: %v", e)
	}
	if !bytes.Equal(data, packet0[28:]) || g.StoredGateElements != 1 || g.FrozenSkippedElements != 2 {
		t.Fatal("the operator's Freeze must exclude the in-flight frame from local WriteData")
	}
}

// Freeze leaves the wire archive continuous so the first admitted
// frame after thaw does not abort the real source writer or Stop.
func TestSourceWriteDataFreezeThawAndVerifiedArchiveRemainDistinct(t *testing.T) {
	m, marks := testLiveWriterMonitor(t)
	defer m.CloseFiles()
	if err := m.EnableLiveBinSpool(); err != nil {
		t.Fatal(err)
	}
	m.liveBin.preview = newLivePreviewBuffer()
	if err := m.sourceOriginalRXGate.selectRate(65536); err != nil {
		t.Fatal(err)
	}
	queueMark(t, marks, 1, "data_begin")
	frames := makeFixture()
	now := time.Now()
	var wire bytes.Buffer
	feed := func(i int, frame Frame) {
		t.Helper()
		wire.Write(frame.Raw)
		if err := m.ProcessChunk(frame.Raw, now.Add(time.Duration(i)*time.Millisecond)); err != nil {
			t.Fatal(err)
		}
	}
	for i, frame := range frames {
		m.sourceOriginalRXGate.setFreeze(i == 10) // ADC1 frame at wire index 256.
		feed(i, frame)
	}
	nextADC := syntheticFrame(0, 512, 0.5)
	feed(len(frames), nextADC)
	gate := m.sourceOriginalRXGate.receipt().Channels[0]
	if gate.StoredGateElements != 512 || gate.FrozenSkippedElements != 256 || m.liveBin.preview != nil {
		t.Fatalf("source/forensic paths were not separated: %+v", gate)
	}
	report, _, err := m.Finalize("STOPPED_BY_USER")
	if err != nil {
		t.Fatal(err)
	}
	status, err := completeStage108Export(m.dir, report, nil, true, 0, m.liveBin)
	if err != nil || status.State != "EXPORTED" || !status.StreamingBINVerified {
		t.Fatalf("Stop did not produce independently verified wire archive: %+v: %v", status, err)
	}
	raw, err := os.ReadFile(filepath.Join(m.dir, "incoming.raw"))
	if err != nil || !bytes.Equal(raw, wire.Bytes()) {
		t.Fatalf("RAW changed: %v", err)
	}
	source, err := os.ReadFile(filepath.Join(m.dir, "SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"))
	want := bytes.Join([][]byte{frames[2].Raw[28:], nextADC.Raw[28:]}, nil)
	if err != nil || !bytes.Equal(source, want) {
		t.Fatalf("Source WriteData has a frozen frame or lost thaw data: %v", err)
	}
}
