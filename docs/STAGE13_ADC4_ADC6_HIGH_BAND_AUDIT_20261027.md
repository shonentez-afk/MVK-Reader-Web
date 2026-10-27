# MVK Stage 13: deep spectral audit of reference channels ADC4 and ADC6 (2026-10-27)

## Source / identity
- Binary capture: `RunUp27-10-2026 08-54-11.zip`, internal device `MVK00000050`, IP `10.13.42.83` (the suffix .83 is the IP last octet, **NOT** serial number).
- Production machine was **running** at recording time. Detector ADC1 has short-circuit; ADC5 has open circuit and LF interference. Exclude 1 and 5 from reference validation; ADC4+ADC6 selected by operator.
- No private raw captures are committed to GitHub.

## Reproducible method
Read each ADC4/6 .bin as LE float32 acceleration m/s², fs=65536 samples/s, N=1,518,848, 23.17578125 s. Remove mean (detrend DC), SciPy `signal.periodogram(window='boxcar', scaling='density')`; integrate one-sided PSD with exact Δf across [lo,hi) to yield RMS. Perform full-record calculation and eleven non-overlapping 2-second windows; residual 1.17578 seconds excluded from window statistics but included in full-record estimate. This rectangular FFT-band approximation is **NOT** the MVKView filtering pipeline.

## Spectral RMS by frequency band, m/s²
| Band Hz | ADC4 | ADC6 |
|---|---:|---:|
| 10–1000 | 4.063953 | 1.689353 |
| 1000–2000 | 1.589349 | 0.931287 |
| 2000–3000 | 0.670915 | 1.908244 |
| 10–2000 | 4.363685 | 1.929043 |
| 10–3000 | 4.414960 | 2.713411 |

Fraction of 10–3000 Hz *squared-RMS energy* from 1000–3000 Hz: ADC4 **15.27%**, ADC6 **61.24%**. Sum of squared individual RMS values matches combined band, verifying this computation's internal energy accounting.

## Stability across 11 2-second windows
- ADC4 10–3000: min 4.29677, median 4.41433, max 4.48990 m/s²; CV 1.18%.
- ADC6 10–3000: min 2.64308, median 2.72085, max 2.76533 m/s²; CV 1.10%.
- ADC6 2000–3000: min 1.81435, median 1.91394, max 1.98204; CV 2.12%.
- ADC6 1000–2000: min 0.92091, median 0.92693, max 0.94864; CV 0.85%.

Therefore a single transient spike is not a supported explanation of the **persistent** discrepancy.

## Prior MVKView comparison (medians of six TABLE CSV snapshots)
- ADC4 10–3000 acceleration: our 4.41496 vs MVKView 4.380; **+0.81%**.
- ADC6 10–3000 acceleration: our 2.71341 vs MVKView 3.3945; **−20.06%**.
- ADC6 10–2000 acceleration: our 1.92904 vs MVKView 2.18; **−11.51%**.
- ADC6 10–1000 acceleration: our 1.68935 vs MVKView 1.656; **+2.04%**.

Interpretation: mismatch increases with inclusion of frequencies >1000 Hz. Potential differences in filter response, units/definitions, window alignment, algorithms remain **hypotheses**. This is NOT a metrological pass/fail and is not yet an exact synchronized comparison.

## Evidence and status for new chat
- Local evidence bundle `MVK83_ADC4_6_DEEP_AUDIT_20261027.zip`: `REPORT_RU.md`, `DEEP_METRICS.json`, `WINDOW_BANDS_2S.csv`, complete SHA256 of each analyzed channel binary.
- Existing previous bundle `MVK83_ADC4_6_COMPARISON_20261027.zip`, prior table CSVs and .bin in `RunUp27-10-2026 08-54-11.zip`; separate .84 stopped equipment dataset `RunUp27-10-2026 09-06-30.zip` with ADC7/8 cable break.
- Stage13 is a planned isolated validation laboratory; frozen production v0.3.40.
- Next: review exact time alignment, inspect ADC6 1–3kHz spectral peak topology using Welch Hann; evaluate edge/transition effects without parameter fitting, then define acceptance tests with fixed tolerances.
- GitHub issues #1-#6, #10 for lossless AUX data, FFT, persistence, field evidence, 16-channel triage.
