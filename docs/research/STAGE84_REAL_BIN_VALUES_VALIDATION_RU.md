# Stage84: real BIN vs VALUES validation (2026-10-29)

Real recording MVK43 ADC1/3/6, 2,124,800 float32 samples/channel, Fs 65,536 Hz. Matching VALUES CSV was decoded in Windows-1251 with | delimiter: 63 half-second records per channel. Processing: subtract global mean, scipy.signal.butter order 3 bandpass 10–3000 Hz with sosfilt, RMS consecutive 32768-sample segments, zero sample offset, no fitted coefficients.

| Channel | Median absolute relative error | Median signed error | Pearson correlation |
|---|---:|---:|---:|
| ADC1 | 1.14355% | -0.99087% | 0.78256 |
| ADC3 | 0.82586% | -0.38707% | 0.98659 |
| ADC6 | 1.54392% | -1.42312% | 0.99038 |

These are the first genuinely reproducible comparisons of raw BIN data to actual device VALUES. They do NOT prove bitwise equivalence: device filter design unknown, cycle alignment uncertain; ADC1 cyclewise correlation requires investigation. This test covers acceleration 10–3000 Hz only; no actual graphical FFT export comparison yet. Offline, no device access. Reproducible script and full results provided as downloadable Stage84 validation package in conversation; raw recordings not uploaded to GitHub. Stable v0.3.40 unchanged.
