# Stage111Z31CX: original Mode2 PageFile and checked offline export

Date: 2026-11-16. Based on private operator IDP and original archive;
no source binaries, DFM images, address credentials or captures are committed.

## The source gap
The original _Unit128.pas bTaskConnectClick enters Mode2 and reveals
PageFile BEFORE TMVKThread.Create. Source DFM has left tcFileChannels
(10 flags) and TWO right tcFileActions modes: 43 SPEC and 73 VALUES
and the 207-logical-pixel pnFileAdc panel. At 0084E914 and 0084E988
the original handlers copy checkbox flags into real TMVKThread
WriteData / WriteValues state.

Previously the compatible Qt cleared all three lists when entering
Mode2 and left PageFile empty until a completed offline ZIP arrived.
This was a visible and functional Core/Qt mismatch.

## Restored in the compatible application
- Pure immutable OriginalLiveFilePlan with 10/43/73 boolean selections,
  strict input validation, identity binding, foreign-run rejection.
- All original checklists become visible immediately on the first
  Mode2 click, before any TCP connection.
- Passive Native R6.1 status updates the eight ADC and two TACH rows
  with REAL observed sample counters and sample rates. A failed status
  removes the old counters without erasing the operator selection.
- The selection persists through Native capture. Only the actual
  archiveReady(path) signal, AFTER independent SHA-checked import,
  maps the flags to verified LOCAL PageFile export. Aborted capture
  and manually opened unrelated archives never inherit old selections.
- DPI 100/150 native Qt and offscreen QA collect synthetic source-mode
  screenshots, while preserving the original two action tabs and pnFileAdc.

## Explicit limits
This is functional selection for subsequent LOCAL output, not a claim
of original TMVKThread live writing. The approved read-only Native Go
receiver captures the entire RAW stream regardless of these checkboxes.
TACH raw records do not exist in the proven Native ZIP and are reported
as unsupported instead of invented. SPEC and VALUES checkboxes are
operator intent only; live device DSP is not fabricated.
Do not enable original source instrument writes or SetRate until their
complete byte contract and operator authorization are verified.

## Next major functional block
Original 10-channel storage buffer/writer, exact source packet framing,
rate command queue, real read-timeout/retry, simultaneous PageStatus /
PageAdc / PageSpectrum / PageFile and operator-approved on-device E2E.
