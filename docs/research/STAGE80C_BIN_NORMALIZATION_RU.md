# Stage 80c — BIN normalization flag, original IDR (2026-10-28)

Source: original `_Unit128.pas` and `_Unit115.pas` extracted locally from `Projects.7z`. Offline static inspection; no industrial files committed.

## Confirmed
- `_Unit128.pas:0x008463DF–0x008463EA`: `[ebp-2C]` is compared with zero (x87 `fldz/fld`), then branch `jae 0x0084651F`; **nonpositive gain leads to fallback setup**, while positive gain can skip it. The exact comparison polarity was checked against the branch context, and should be verified by focused x87 emulation before claiming all NaN/zero edge cases.
- If fallback is needed and type code equals 2 (Byte), gain is set to 1 (`0x008463F0–0x008463F6`). Otherwise `DefaultConfig.txt` is loaded (`0x00846402–0x008464B0`), and gain may be derived from two `TMvkCellList.GetFloatByAddr` calls; a tiny denominator is handled via constant `100` (`0x008464B0–0x00846512`).
- The fallback path sets `ViewedFileIsNormalized=1` at `0x00846516`; existing usable gain takes `ViewedFileIsNormalized=0` at `0x00846522`.
- `_Unit128.pas:0x0084F982` passes that flag to `TMvkChannelStorage.ProcessBufferChunk`.
- `_Unit115.pas:0x007D2398–0x007D23FE` implements ProcessBufferChunk; `FAdcDataType` determines whether size is shifted right by two (float32), and **only for float and ApplyRange=true** does it multiply the ring-buffer samples by `FRange` at `0x007D23D5`. The position `FRxPos` advances by sample count at `0x007D23EA–0x007D23F7`.

## Interpretation and caveats
Interpretation: a positive gain supplied by the archive metadata usually means data have already been scaled and no extra multiplication is requested. A missing/invalid gain enters fallback and activates scaling from configuration (except Byte-specific path). However the meaning of the gain field, the x87 comparisons for NaN and the full context of source initialization require further checking. The existing documented calibration rule `a = raw_float32*K` for certain TCP/BIN pairs should **not** be applied a second time to a scaled archive.

**No full numerical FFT equivalence yet.** Next: trace `GetSpectrum` after `0x007D154B` through its four output modes and FFT backend, identify exact frequency scaling and windows, then compare the same source BIN/TSXML and reference MVKView exported spectrum. No devices, no writes to stable v0.3.40.

Static offline check: `tools/research/stage80c_verify_normalization.py`.
