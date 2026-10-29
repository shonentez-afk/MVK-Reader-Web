package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"time"
)

// Stage108 intentionally separates network acquisition from deterministic,
// checksum-verified local conversion. Capture -> close/flush -> export atomically.
// No Modbus, parameter writes, frequency-setting, or device transmit path exists.
const reconstructedDirName = "BIN_TSXML_VALUES_TABLE_RECONSTRUCTED"

type IntegratedExportStatus struct {
	Version               string `json:"version"`
	State                 string `json:"state"`
	CaptureResult         string `json:"capture_result"`
	CaptureEndReason      string `json:"capture_end_reason"`
	OriginalRawSHA256     string `json:"source_raw_sha256"`
	UTCOffset             string `json:"utc_offset"`
	OutputDir             string `json:"output_directory,omitempty"`
	TerminalBytesExcluded int    `json:"incomplete_terminal_frame_bytes_excluded"`
	ADCFiles              int    `json:"adc_bin_files"`
	StreamingBINVerified  bool   `json:"during_capture_bin_spool_verified"`
	CleanupWarning        string `json:"cleanup_warning,omitempty"`
	ValuesRows            int    `json:"values_rows"`
	AUXUpdates            uint64 `json:"aux4700_updates"`
	Error                 string `json:"error,omitempty"`
	Limitation            string `json:"limitation"`
}

func capturePCOffset(now time.Time) (int, error) {
	_, offsetSeconds := now.Zone()
	if offsetSeconds%60 != 0 || offsetSeconds < -12*3600 || offsetSeconds > 14*3600 {
		return 0, errors.New("system clock offset invalid for MVK CSV: use -offset +/-HH:MM")
	}
	return offsetSeconds / 60, nil
}

// An explicit timezone is important if offline replay is performed on a PC in a
// different timezone from the original R5/R5.1 host.
func parseOffset(value string, now time.Time) (int, error) {
	if value == "auto" {
		return capturePCOffset(now)
	}
	m := regexp.MustCompile(`^([+-])([0-9]{2}):([0-9]{2})$`).FindStringSubmatch(value)
	if m == nil {
		return 0, errors.New("UTC offset must be auto or +/-HH:MM")
	}
	hh, _ := strconv.Atoi(m[2])
	mm, _ := strconv.Atoi(m[3])
	if mm >= 60 || hh > 14 || (hh == 14 && mm > 0) || (m[1] == "-" && (hh > 12 || (hh == 12 && mm > 0))) {
		return 0, errors.New("UTC offset outside -12:00..+14:00")
	}
	mins := hh*60 + mm
	if m[1] == "-" {
		mins = -mins
	}
	return mins, nil
}

func isSafeCaptureForExport(s Summary) error {
	if s.CaptureOnly || s.InvalidFrames != 0 || s.RawBytes == 0 {
		return errors.New("invalid/no-data capture: preserve RAW, no reconstructed outputs")
	}
	switch s.EndReason {
	case "DURATION_REACHED", "SIZE_LIMIT_REACHED", "STOPPED_BY_USER", "REPLAY_EOF":
	default:
		return fmt.Errorf("capture stopped unexpectedly (%s), export blocked", s.EndReason)
	}
	if s.TailBytes < 0 || s.TailBytes >= maxFrameSize {
		return fmt.Errorf("invalid final frame tail %d", s.TailBytes)
	}
	if s.TailBytes != 0 && s.Result != "VALID_FRAMES_WITH_INCOMPLETE_LAST_FRAME" {
		return errors.New("monitor declares tail but did not mark incomplete final frame")
	}
	if s.TailBytes == 0 && s.Result != "VALID_FRAMES" {
		return errors.New("monitor did not validate complete application framing")
	}
	return nil
}

func writeExportStatus(runDir string, status IntegratedExportStatus) error {
	data, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	p := filepath.Join(runDir, "STAGE108_EXPORT_STATUS.json")
	temporary := p + ".partial"
	f, err := os.OpenFile(temporary, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	if _, err = f.Write(data); err != nil {
		f.Close()
		os.Remove(temporary)
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		os.Remove(temporary)
		return err
	}
	if err = f.Close(); err != nil {
		os.Remove(temporary)
		return err
	}
	if err = os.Rename(temporary, p); err != nil {
		os.Remove(temporary)
		return err
	}
	return nil
}

// Called only AFTER Finalize has completed and closed the original RAW.
// Export is performed in the SAME EXE, not a subprocess, without user
// intervention and without starting a new TCP connection.
func completeStage108Export(runDir string, s Summary, captureError error, enabled bool, offsetMin int, spool *LiveBinSpool) (IntegratedExportStatus, error) {
	status := IntegratedExportStatus{
		Version: "Native Stage108 R6.1 integrated session recorder 0.1",
		State:   "NOT_ATTEMPTED", CaptureResult: s.Result, CaptureEndReason: s.EndReason,
		OriginalRawSHA256: s.RawSHA256, UTCOffset: formatOffset(offsetMin),
		Limitation: "BIN is reconstructed from TCP raw using session gain, not proven byte-identical to an MVKView export of this same session; timestamps are capture-PC receive times.",
	}
	var cause error
	switch {
	case !enabled:
		status.State = "DISABLED"
	case captureError != nil:
		status.State = "REFUSED"
		cause = fmt.Errorf("capture failed: %w", captureError)
	default:
		cause = isSafeCaptureForExport(s)
		if cause != nil {
			status.State = "REFUSED"
		} else {
			// The Stage107 builder publishes only into a hidden intermediate
			// directory first. Compare it to the on-receive live BIN spool;
			// only then publish the user-visible completed export directory.
			pending := filepath.Join(runDir, ".stage108_reconstruction_pending")
			final := filepath.Join(runDir, reconstructedDirName)
			if _, statErr := os.Stat(final); statErr == nil {
				cause = fmt.Errorf("refusing overwrite of existing export directory %s", final)
			} else if !os.IsNotExist(statErr) {
				cause = statErr
			} else {
				var rep ExportReport
				rep, cause = exportWithPolicy(filepath.Join(runDir, "incoming.raw"), filepath.Join(runDir, "frames.csv"), filepath.Join(runDir, "summary.json"), pending, offsetMin, true)
				if cause == nil && spool != nil {
					cause = spool.verifyAgainstExport(rep)
					if cause == nil {
						status.StreamingBINVerified = true
					}
				}
				// Clean partial streaming files before publishing a ready dir.
				// A cleanup failure prevents the completed result from being
				// announced; the original RAW remains available for forensics.
				if spool != nil {
					if spoolErr := spool.Cleanup(); spoolErr != nil && cause == nil {
						cause = spoolErr
					}
				}
				if cause == nil {
					cause = os.Rename(pending, final)
				}
				if cause != nil {
					_ = os.RemoveAll(pending)
				} else {
					status.State = "EXPORTED"
					status.OutputDir = reconstructedDirName
					status.TerminalBytesExcluded = rep.IgnoredTerminalBytes
					status.ADCFiles = len(rep.Channels)
					status.ValuesRows = rep.ValuesRows
					status.AUXUpdates = rep.AUX
				}
			}
			if cause != nil {
				status.State = "FAILED_CLOSED"
			}
		}
	}
	if spool != nil {
		if cleanErr := spool.Cleanup(); cleanErr != nil {
			status.CleanupWarning = cleanErr.Error()
			if cause == nil {
				cause = fmt.Errorf("temporary BIN cleanup: %w", cleanErr)
			}
		}
	}
	if cause != nil {
		status.Error = cause.Error()
	}
	if writeErr := writeExportStatus(runDir, status); writeErr != nil {
		return status, fmt.Errorf("cannot write export audit status: %w (export: %v)", writeErr, cause)
	}
	return status, cause
}
