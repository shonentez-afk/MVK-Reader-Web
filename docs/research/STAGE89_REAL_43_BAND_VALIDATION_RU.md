# Stage89 — 43 real archived spectral bands, 2026-10-29

Original MVK43 ADC1/3/6 BIN+TSXML and 63 VALUES cycles were processed OFFLINE. PCAPNG are a different session and were excluded. Per channel: subtract global mean, polyphase downsampling to 512/64/16 Hz, third-order Butterworth bandpass per 43 third-octave center frequencies (0.63..10000 Hz; edges fc*10^(+/-1/20)), 0.5-sec RMS windows, zero fitted time offset.

## Median of per-band median absolute relative errors (%)
| Band indices | ADC1 | ADC3 | ADC6 |
|---|---:|---:|---:|
| 1–9 | 40.61 | 47.25 | 73.69 |
| 10–17 | 33.72 | 29.91 | 25.38 |
| 18–26 | 4.35 | 20.61 | 8.64 |
| 27–43 | 2.57 | 2.85 | 3.86 |

129 channel x band comparisons. Very small low-frequency reference values can cause extremely large relative errors; this metric is not a broadband error. Approximate Butterworth + polyphase resampling is NOT the original instrument DSP.

## Low-frequency displacement contribution 10–20 Hz (diagnostic, not actual device report)
Median derived displacement RMS in first 10 versus last 10 half-second windows: ADC1 34.77 to 34.75 um; ADC3 1.38 to 1.50 um; ADC6 1.99 to 1.97 um. Thus ADC3 10–20 Hz contribution does not show simple monotonic decay: transient hypothesis still OPEN.

Full computed 129-row JSON, the two independent offline scripts and a Russian report delivered in conversation as stage89_validation_package.zip. Raw captures have NOT been committed. Next Stage90: edge-band tones, thresholds for low-reference relative error, startup buffer masks, and exact original DSP filter structure. No device connections. Stable v0.3.40 untouched.