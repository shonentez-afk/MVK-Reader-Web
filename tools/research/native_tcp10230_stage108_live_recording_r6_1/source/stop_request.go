package main

import (
    "context"
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "time"
)

// An opt-in, local-only stop request for the Windows Qt controller.
// It does not write to the instrument or change the TCP/10230 protocol.
// The existing signal/duration/size behavior is unchanged without -stop-file.
const stopRequestName = ".mvk_stop_requested"

func validateStopRequestPath(path string) error {
    if !filepath.IsAbs(path) || filepath.Base(path) != stopRequestName {
        return fmt.Errorf("must be an absolute path ending in %s", stopRequestName)
    }
    _, err := os.Lstat(path)
    if err == nil {
        return errors.New("stop request file already exists before session")
    }
    if !errors.Is(err, os.ErrNotExist) {
        return err
    }
    return nil
}

func watchStopRequest(ctx context.Context, path string, cancel context.CancelFunc) {
    ticker := time.NewTicker(100 * time.Millisecond)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            info, err := os.Lstat(path)
            if err == nil {
                if !info.Mode().IsRegular() {
                    fmt.Println("Stop-request path is not a regular file: cancel capture safely")
                } else {
                    fmt.Println("Operator requested graceful stop: finalize RAW and verify export")
                }
                cancel()
                return
            }
            if !errors.Is(err, os.ErrNotExist) {
                fmt.Println("Cannot safely check stop request: cancel capture")
                cancel()
                return
            }
        }
    }
}
