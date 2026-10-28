# Stage 81d — FFT backend and log output (2026-10-28)

Evidence: original `Projects.7z/_Unit115.pas`, offline. Static inspection supports **15/15 marker checks**; this proves code shape, not runtime output.

## FFT core
`TDSXFastFourier.fft` (0x007CC3F8) calls `sub_007CC198` with single-precision angle constant `+2π`; `ifft` calls it with `-2π` and divides both complex output components by N. `sub_007CC198` checks power-of-two sample count >= 2, uses bit-reversal `sub_007CC17C`, copies complex input to output in permuted order, then executes iterative radix-2 Danielson–Lanczos butterfly stages, doubling stage size. FFT input and output are interleaved float32 complex arrays; forward transform has no apparent 1/N normalization. Because the spectrum path keeps `Re²+Im²`, the sign convention does not affect the final spectrum for real input; exact float32 rounding does depend on recurrence order.

## Log mode 0
`GetSpectrum` at 0x007D15DD prepares `2*fn(Nbins)` (`0x007D15F2`), then for positive power `P` computes `10*(fn(P)-2*fn(Nbins))` (`0x007D1624–0x007D162C`). If `fn` is the expected base-10 logarithm this is `10log10(P/Nbins²)`. For non-positive `P` the code stores float32 bit pattern `0xC3340000` = **-180.0**, not a mathematically defined log. The external helper `0x00447DB8` is not defined by this unit and its exact semantics still require inspection; logarithm base 10 remains a *strong inference*, not independently proved here. Also `Nbins` is the internal output count `N/2`, not automatically FFT length N.

## Cautions / next steps
- Inspect original helper `0x00447DB8` or dynamic imports for log base, and align band limits, DC exclusion, Nyquist policy.
- Build deterministic float32 radix-2 test with synthetic signals, then **real** BIN/TSXML and same MVKView spectrum. Synthetic tests are not a surrogate for real evidence.
- Verify whether previous documentation about `GetSpectrum` mode 1 is correct: the code uses `FRange/Nbins * sqrt(P/2)`; mode 0 has a separate dB scaling and no visible FRange multiplication in this path. Do not infer calibration from log mode alone.
- Do not touch v0.3.40, use network or device, or research firmware.

Verifier: `python tools/research/stage81d_verify_fft_backend.py _Unit115.pas`.
