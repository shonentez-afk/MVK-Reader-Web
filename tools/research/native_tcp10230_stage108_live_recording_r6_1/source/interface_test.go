package main

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"net"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestNetworkOrderInterfaceIndex(t *testing.T) {
	cases := []struct{ index, want int }{
		{1, 0x01000000},
		{17, 0x11000000},
		{256, 0x00010000},
		{0x10000, 0x00000100},
	}
	for _, tt := range cases {
		got, err := networkOrderIndex(tt.index)
		if err != nil || got != tt.want {
			t.Errorf("index %d -> %x, %v; expected %x", tt.index, got, err, tt.want)
		}
	}
	for _, bad := range []int{0, -1, 0x1000000} {
		if _, err := networkOrderIndex(bad); err == nil {
			t.Errorf("accepted bad interface index %d", bad)
		}
	}
}

func TestNoUnrequestedInterfaceFallback(t *testing.T) {
	if _, err := newInterfaceDialer(&LocalNIC{Name: "Ethernet", Index: 0, IP: net.IPv4(10, 0, 0, 2)}); err == nil {
		t.Fatal("invalid NIC index was accepted")
	}
	if _, err := newInterfaceDialer(&LocalNIC{Name: "Ethernet", Index: 5}); err == nil {
		t.Fatal("missing NIC IPv4 was accepted")
	}
}

func TestExplicitNICSelectionAndSourceIP(t *testing.T) {
	items := []LocalNIC{
		{Name: "Wi-Fi", Index: 1, IP: net.IPv4(10, 4, 5, 1)},
		{Name: "Ethernet", Index: 2, IP: net.IPv4(192, 168, 1, 100)},
	}
	r := bufio.NewReader(strings.NewReader("2\n"))
	nic, err := chooseNIC(r, items)
	if err != nil || nic.Index != 2 || !nic.IP.Equal(net.IPv4(192, 168, 1, 100)) {
		t.Fatalf("bad interactive NIC: %+v %v", nic, err)
	}
	source, err := findNICForLocalIPv4("192.168.1.100", items)
	if err != nil || source.Index != 2 {
		t.Fatalf("bad cli NIC selection %+v %v", source, err)
	}
	if _, err := findNICForLocalIPv4("192.168.1.101", items); err == nil {
		t.Fatal("accepted nonlocal IPv4, would silently route")
	}
	if _, err := chooseNIC(bufio.NewReader(strings.NewReader("0\n")), items); err == nil {
		t.Fatal("accepted bad interactive selection")
	}
}

func TestReadOnlyConnectedSocketRecordsSelectedSource(t *testing.T) {
	// Windows-specific binding by IP_UNICAST_IF must be live-tested on Windows;
	// this test proves common source-binding and no app packets on local Linux.
	if runtime.GOOS == "windows" {
		t.Skip("local Linux test; Windows option requires on-device QA")
	}
	lo, err := net.InterfaceByName("lo")
	if err != nil {
		t.Skip("no loopback test adapter")
	}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
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
		if _, e = c.Write(makeIdentity()); e != nil {
			accepted <- e
			return
		}
		_ = c.SetReadDeadline(time.Now().Add(1000 * time.Millisecond))
		var b [1]byte
		n, e := c.Read(b[:])
		if n != 0 {
			accepted <- errors.New("app data sent unexpectedly")
			return
		}
		if e != nil {
			var ne net.Error
			if errors.As(e, &ne) && ne.Timeout() {
				accepted <- nil
				return
			}
		}
		accepted <- nil
	}()
	nic := &LocalNIC{Name: lo.Name, Index: lo.Index, IP: net.IPv4(127, 0, 0, 1), Prefix: 8}
	mon, err := NewMonitor(filepath.Join(t.TempDir(), "capture"), "LIVE_READ_ONLY", "127.0.0.1")
	if err != nil {
		t.Fatal(err)
	}
	reason, err := liveCaptureAddressOnNIC(context.Background(), mon, listener.Addr().String(), 2, 1024*1024, nic)
	if err != nil {
		t.Fatal(err)
	}
	result, _, err := mon.Finalize(reason)
	if err != nil {
		t.Fatal(err)
	}
	if result.IdentityFrames != 1 || result.SelectedInterfaceIndex != lo.Index || result.SelectedLocalIPv4 != "127.0.0.1" || !strings.HasPrefix(result.SocketLocalAddr, "127.0.0.1:") {
		t.Fatalf("bad bound session report: %+v", result)
	}
	select {
	case e := <-accepted:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("TCP server didn't complete")
	}
}

func TestNoAccidentalTCPReadInReplay(t *testing.T) {
	m, err := NewMonitor(filepath.Join(t.TempDir(), "replay"), "OFFLINE_REPLAY", "")
	if err != nil {
		t.Fatal(err)
	}
	data := bytes.NewReader(makeIdentity())
	// Read-only framing is independent of live sockets.
	buf := make([]byte, 264)
	_, _ = data.Read(buf)
	if err := m.ProcessChunk(buf, time.Now()); err != nil {
		t.Fatal(err)
	}
	s, _, err := m.Finalize("TEST_DONE")
	if err != nil || s.IdentityFrames != 1 || s.SelectedLocalIPv4 != "" {
		t.Fatalf("bad offline report %+v %v", s, err)
	}
}
