package main

import (
    "context"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func TestGracefulStopRequestWithoutHardware(t *testing.T) {
    dir := t.TempDir()
    path := filepath.Join(dir, stopRequestName)
    if err := validateStopRequestPath(path); err != nil {
        t.Fatal(err)
    }
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    go watchStopRequest(ctx, path, cancel)
    if err := os.WriteFile(path, []byte("STOP\n"), 0600); err != nil {
        t.Fatal(err)
    }
    select {
    case <-ctx.Done():
    case <-time.After(3 * time.Second):
        t.Fatal("stop request did not cancel context")
    }
    if err := validateStopRequestPath(path); err == nil {
        t.Fatal("a stale pre-existing stop file must be rejected")
    }
}

func TestInvalidStopRequestPathsRefused(t *testing.T) {
    if validateStopRequestPath(stopRequestName) == nil {
        t.Fatal("relative stop requests must be rejected")
    }
    if validateStopRequestPath(filepath.Join(t.TempDir(), "arbitrary.stop")) == nil {
        t.Fatal("arbitrary names must be rejected")
    }
}
