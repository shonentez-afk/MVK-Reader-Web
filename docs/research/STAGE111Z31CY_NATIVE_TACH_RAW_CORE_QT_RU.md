# Stage111Z31CY — original 10-channel incoming RAW and safe TACH1/TACH2 evidence

Date: 2026-11-16. Based on operator-provided local IDP + Projects.7z and
previously source-checked Native R6.1 Go protocol. Do not upload original
operator captures, IDP, DFM, runtime fonts/images, instrument IPs or secrets.

## Discovered source/core gap

Delphi TMVKThread in _Unit125.pas contains 10 channel masks, WriteData,
WriteValues, channel storage, and records of two original tachometers.
Incoming typeTach 0xFF8001AC is exactly 284 bytes: 8-byte envelope,
5 little-endian uint32 words and 64 Float32 values. Channel indexes
8/9 are Native TACH1/2, distinct from ADC indexes 0..7 and ADC
packets of 1052 bytes with 256 Float32.

The existing Go R6.1 Framer, Monitor and offline exporter already
authenticated TACH headers/rates and kept full incoming.raw, but
the exporter deliberately ignored the TACH sample payload in its
`case typeTach:` branch. Consequently, no TACH source files
were available to the otherwise source-correct 10-row PageFile.
Firmware calibration, tachometer RPM units, original TACH BIN/TSXML
format and write control masks are NOT proven by that fact.

## Stage111Z31CY implementation, Core and UI together

1. Go `tach_raw_export.go` copies EXACT incoming 64xFloat32
payload bytes (no gain/resampling/interpolation) into uniquely named
TACH1_NATIVE_UNCALIBRATED.f32 and TACH2_NATIVE_UNCALIBRATED.f32.
Every file has an SHA256 under the SAME source raw SHA
and an additional TACH_RAW_SOURCE_AUDIT.json with frame counts,
sample count/rate, first/last indexes, observed discontinuities and
sample-rate changes. No TACH packet => explicit ABSENT state, never
synthetic zero-valued measurements. Incomplete/failed sessions leave
original incoming.raw unchanged and do not publish ready exports.

2. Go native `exporter.go` incorporates optional TACH hashes and
source audit into the SAME atomic export manifest; it still exports
the original eight SHA-calibrated ADC BIN/TSXML files and VALUES/AUX
without modifications to their bytes. Nothing in this change
connects to device TCP, sends a payload or toggles source WriteData,
WriteValues or SetRate.

3. Python `native_r6_tach_evidence.py` verifies exactly two original
TACH channel identities, source RAW SHA, each .f32 size/hash, 64-sample
frame counts, rates, gap/rate-change flags and the "uncalibrated"
provenance. Legacy 19-file Native archives remain valid; extra TACH
files without a bound audit fail CLOSED. OfflineSession and the
Qt ZIP packer validate the sidecar before displaying or exporting it.

4. `OriginalPageFileSelection` admits only independently
SHA-checked, contiguous constant-rate TACH sources. The local
PageFile export can copy either/both 64-sample TACH raw streams
and their provenance JSON byte-for-byte, separately from ADC BIN/
TSXML and source DSP/VALUES. It never invents source TACH TSXML,
physical calibration, source timestamp or RPM.

5. Real Qt PageFile now labels TACH1/TACH2 with actual raw Float32
sample counts and verified Fs (and marks them explicitly NON-
CALIBRATED), enables checkboxes only if the source is contiguous,
and blocks export on gaps. Source PageStatus TACH modes 13/14
display independently verified input-stream evidence in the note
without overwriting any source DSP cells or drawing fake RPM
graphs. Windows Qt and core tests include DPI100/150 receipts.

## Safety and parity limits

- Original native instrument TMVKThread.WriteData and WriteValues
  stage semantics, rate command queue and device packet writes are
  NOT implemented. A compatible full RAW capture remains opt-in
  and read-only and cannot have channel masks arbitrarily changed.
- The TACH .f32 is intentionally an additional NATIVE evidence
  format, NOT a real original MVKView .bin/.tsxml and NOT calibrated
  tachometer speed. The Go/Qt chain makes this distinction visible.
- A TACH frame sequence gap or sample-rate change is preserved in
  raw forensic evidence but disables verified continuous local export.
- Numeric parity with real original MVKView and physical device TACH
  channels is not proven without same-run operator E2E evidence.

## Needed next major block

Original 10-channel source file recording state machine with masks,
WriteData/WriteValues Begin/Stop, exact five original rates and device
command queue recovery from IDP, and same-data E2E physical validation.
