# Stage 13.2 — ADC4 reference-channel-first validation, 27 Oct 2026

## Decision
User changed priority: stop focusing on ADC6. Establish a complete repeatable reference from **healthy ADC4**, validate on device83 and device84 first, then transfer method to all ADCs with sensor-state exclusions. No coefficient tuning until independent controls pass.

## Actually executed on original LAB07 captures
- Inputs: `83 первый(1).pcapng` and `84 отдельно(1).pcapng`.
- Used existing `cap_parse.py` and calibration from each 33064-byte VAST_MVK initial header, ADC4 1052-byte frames / 256 float32 samples, 4700-byte calculated frames with instrument values, 43 third-octave entries and ADC4 status.
- Per reported frame compared **trailing 1, 2 and 4-second Hann PSD** (no offset), with BOTH frozen MVK-LAB06 empirical P1.4 edge and independent HP3×LP3 normative frequency response on **identical ADC samples and reference frames**.
- Device83 and device84 ADC4 status=0, TCP gaps absent and ADC counters continuous.
- All six available calculated acceleration fixed bands inspected; all 43 nominal third-octave acceleration bands separately examined with rectangular diagnostic spectral bins (NOT factory class-2 filters).
- Results and reproducible local files: `/mnt/data/mvk_stage13/adc4_reference_audit.py`, `adc4_fixed_band_frames.csv`, `adc4_third_octave_frames.csv`, `adc4_summary.csv`, `adc4_meta.json`.

## Results (median absolute percent error, trailing 1-second window, frozen empirical P1.4)
| Fixed band | Device83 ADC4 | Device84 ADC4 |
|---|---:|---:|
|10–3000|1.01%|1.41%|
|10–2000|0.83%|1.48%|
|10–1000|1.30%|1.21%|
|2–1000|1.30%|1.21%|
|0.8–300|3.34%|1.93%|
|0.8–150|1.35%|5.14%|

On 10–3000, with 1/2/4s trailing windows: device83 1.01% / 1.98% / 2.67%; device84 1.41% / 5.18% / 7.45%. Normative HP3×LP3 corresponding 1s errors: 1.03% / 1.37%. Both models have virtually identical accuracy on this control channel, so its data cannot yet identify the precise proprietary upper edge coefficients. Fixed edges near upper cutoff need a deliberately informative non-ADC4 spectrum later.

Third-octave 43-slot mapping comparison for values over 0.01 m/s²: median relative error of naive rectangular-bin reconstruction ~5.04% device83, ~5.68% device84. Distinct narrowband outliers (e.g. device83 31.5 Hz) show an important remaining challenge: actual class-2 bandpass filter characteristics, leakage, window synchronization and word mapping. Treat 0.63 Hz as genuine 43rd transmitted slot; not a status word.

## Evidence boundaries
A one-second *trailing* window is the best of only the three candidates under zero lag in this run. This **does not establish the device DSP integration window**; a truly independent holdout lag/window selection on all six bands and third octaves is the next step. Earlier 13.1 holdout on device84 ADC4 selected 1s/0 lag and achieved 1.12% on 10–3000, consistent with current findings. A comparison with full-record PSD, BIN timestamps and separate CSV TABLE measurements must retain temporal provenance. Not claiming 43-band reconstruction complete or metrological acceptance.

## Next controlled gates
1. Focus ADC4 dev83 and dev84: compare device 43 octave energies, per-frame signals and raw counter-to-4700 mapping across a **common sample/window set**, select settings on first half and verify on holdout; inspect harmonics at 31.5 Hz and boundaries.
2. Verify ADC4 binary export against matching time-stamped CSV from same device, with explicit time-window matching (do not mix separate runs).
3. Once the ADC4 reference path is stable across channels, use it to test remaining healthy ADCs, then abnormal-status ADCs with quality flags.
4. Compare 3 quantities (acceleration, velocity, displacement), all six fixed bands, third octaves, wideband and event peaks; keep tests and protocol provenance in GitHub.
Frozen production v0.3.40 unchanged. No device connections or new recordings requested.
