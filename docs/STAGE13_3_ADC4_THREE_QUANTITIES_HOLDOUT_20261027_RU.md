# Stage13.3 — ADC4 full three-quantity verification (2026-10-27)

## Purpose and fixed provenance
User instructs ADC4-first systematic restoration, not ADC6-first. Directly analyzed original 15-second captures `83 первый(1).pcapng` and `84 отдельно(1).pcapng` with known `cap_parse.py`, calibrated raw ADC4 float32 samples and the corresponding 4700 calculated words. No model refit, no target-dependent calibration, no production edit.

Each 4700 frame was paired to the *preceding 1 second of transmitted ADC4 samples*, Hann detrended PSD, fs=65536 Hz. Evaluated all six fixed bands for three quantities:
- acceleration RMS (m/s2);
- velocity RMS, frequency integration factor (1000/(2pi f))^2 for power, mm/s;
- displacement RMS, factor (1e6/(2pi f)^2)^2 for power, micrometers.
Compared frozen MVK-LAB06 empirical edge-energy weights to an independent rectangular-band diagnostic integrator on identical windows. Also checked 43 third-octave acceleration values (0.63...10000 Hz) using rectangular nominal frequency bins, **not certified factory class 2 windows**. Matched each calculated frame's actual 144-word channel record and status. First 15 4700 frames = train/inspection, second 15 frames = held-out assessment; no fitting on either subset in this run. All ADC4 sensor statuses OK, ADC sample counters continuous, no TCP gaps.

## Held-out results — 10–3000 Hz, frozen P1.4, median absolute percentage error
| Quantity | Device83 ADC4 | Device84 ADC4 |
|--|--:|--:|
| Vibration acceleration | 1.016% | 1.123% |
| Vibration velocity | 0.772% | 1.465% |
| Vibration displacement | 1.450% | 1.369% |

At 10–3000, device84 rectangular acceleration integration has 2.413% error versus 1.123% with the frozen P1.4 edge weights on identical heldout frames; device83 rectangular is 1.053% versus P1.4 1.016%. Velocity/displacement models differ little between rectangular and weighted at this band on ADC4; this validates overall frequency-integration behavior but does not uniquely identify manufacturer's exact weight windows.

Third-octave acceleration, nominal 43 bands and instrument level >0.01 m/s2, heldout median relative absolute error:
- Device83: 4.890%, n=417 samples across frames/bands.
- Device84: 5.870%, n=453.
Outliers at individual narrowband bins remain. Hypotheses: genuine class-2 slopes, Hann spectral leakage, window duration and temporal alignment, and provisional center-to-wire field mapping. All 43 transmitted values retained, including 0.63 Hz.

## Files actually generated in run (local/user attachments, not yet committed byte-for-byte)
`/mnt/data/mvk_stage13/adc4_three_quantity_audit.py`, `adc4_3quantity_frames.csv`, `adc4_3quantity_summary.csv`, `adc4_3quantity_meta.json`. The numeric audit executed successfully on the two PCAPNG. Do not report these local CSV as GitHub-file contents until committed; this document is a complete summary of the test, with transparent dataset and method.

## Mandatory next steps (ADC4 reference first)
1. Analyse **all six bands across all three quantities** in heldout frames; identify where LF velocity/displacement reconstruction fails due to DC/slow drift and low-fs filtering. Do not claim 1-second window is the factory DSP setting.
2. Test third-octave weights/class-2 candidate shapes on *heldout* ADC4, not merely improve in-sample band-fitting. Resolve extreme narrowband bins and 42/43 distinction only with byte-level provenance.
3. Reconcile synchronized ADC4 BIN and MVKView CSV only if the same measurement session and clock range can be demonstrated.
4. Then expand fixed, transparent method to other **healthy** channels with status 0; keep pathological ADC6 as later stress test.
5. Keep frozen production v0.3.40 untouched.

## Critical low-frequency finding from all six bands
At 0.8-300 Hz the heldout displacement median absolute errors are **241.55% (device83 ADC4)** and **196.54% (device84 ADC4)**. At 0.8-150 Hz they are **241.61% and 197.40%** respectively. These large discrepancies are NOT masked by the good 10-3000 results; they show the simple 1/f^2 integration of raw full-rate PSD is not a substitute for the manufacturer's low-frequency decimated/filtered displacement DSP. At 2-1000 displacement errors are 7.53% (83) and 0.84% (84). For 0.8-300 velocity, errors are 1.39% and 1.23%. Priority: identify LF displacement filtering / suppress drift, time window and transfer functions on ADC4; do not tune upper edge coefficients to fix this.
