# Stage 62 — Archive FRange selection in original MVKView

Static IDR analysis of `_Unit128.pas` around 0x00846008 (12/12 checks): BIN companion TSXML property `InternalChannelGain` is read and converted to floating point (0x0084620D, 0x00846237); accepted gain bypasses fallback. If unsuitable, Byte type selects 1.0; float32 processing can use `DefaultConfig.txt`, reading ADC calibration from 0x20 and sensor sensitivity from channel 0x02; fallback `FRange=ADC_cal/sensitivity`, with special fallback 100.0 for invalid small sensitivity. Final assignment `TMvkChannelStorage.FRange` at 0x0084655E.

In contrast, live Stage52 thread reads channel config 0x0E directly. The original BIN was written after in-place scaling; do not blindly multiply BIN by TSXML gain again. Error and dialog paths for corrupt TSXML not exhaustively traced. Full local evidence: MVKVIEW_STAGE62_ARCHIVE_GAIN_20261028.zip. Stable v0.3.40 untouched.
