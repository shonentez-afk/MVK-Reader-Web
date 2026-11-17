package main

// Source _Unit125.pas TMVKThread.Execute (IDP 00807A98) runs until
// Terminated. These TCP tests use ONLY a local loopback fake server.
import (
    "context"
    "net"
    "path/filepath"
    "testing"
    "time"
)

func TestOriginalMode2UnboundedLoopbackStopsOnlyOnOperatorRequest(t *testing.T) {
    ln, err := net.Listen("tcp4", "127.0.0.1:0")
    if err != nil { t.Fatal(err) }
    defer ln.Close()
    accepted := make(chan struct{})
    release := make(chan struct{})
    defer close(release)
    go func() {
        c, e := ln.Accept()
        if e != nil { return }
        defer c.Close()
        close(accepted)
        <-release
    }()
    m, err := NewMonitor(filepath.Join(t.TempDir(),"TEST_source_unbounded"),"LIVE_READ_ONLY","127.0.0.1")
    if err != nil { t.Fatal(err) }
    defer m.CloseFiles()
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    type result struct { reason string; err error }
    finished := make(chan result,1)
    go func() {
        reason, e := liveCaptureAddress(ctx,m,ln.Addr().String(),0,65536)
        finished <- result{reason,e}
    }()
    select {
    case <-accepted:
    case <-time.After(3*time.Second): t.Fatal("loopback TCP not established")
    }
    select {
    case got:=<-finished: t.Fatalf("0-second source capture terminated on its own: %+v",got)
    case <-time.After(180*time.Millisecond):
    }
    cancel()
    select {
    case got:=<-finished:
        if got.reason!="STOPPED_BY_USER" || got.err!=nil {
            t.Fatalf("source explicit stop: %+v",got)
        }
    case <-time.After(4*time.Second):
        t.Fatal("source loop did not respect graceful stop while TCP idle")
    }
    if !m.summary.ReadOnly { t.Fatal("no hardware commands allowed") }
}

func TestSourceRetryWaitBoundedVsUnboundedDeadlineContract(t *testing.T) {
    // An explicit zero duration must not expire before its first
    // 260ms original retry. Bounded mode is preserved in separate tests.
    if sourceRetryWait(25)!=260*time.Millisecond {
        t.Fatal("original Task2 reconnect timing changed")
    }
}
