# Stage87 real archived BIN vs VALUES — 2026-10-29

True MVK43 ADC1/3/6 BIN data and same-session VALUES 63 cycles. PCAPNG belong to a DIFFERENT session, excluded. Method: 65536Hz, 32768 samples/cycle, no lag fitting, subtract global DC, scipy Butterworth order3 10..3000,10..2000,10..1000Hz, RMS acceleration; band-limited per-cycle FFT integration for velocity mm/s and displacement um. No calibration fitting.

| ADC | Hz | acceleration median abs err % | velocity % | displacement % |
|---|---|---:|---:|---:|
| 1 | 10..3000 | 1.14 | 1.42 | 1.99 |
| 1 | 10..2000 | 0.43 | 1.40 | 1.98 |
| 1 | 10..1000 | 0.51 | 1.41 | 1.92 |
| 3 | 10..3000 | 0.83 | 1.37 | 8.56 |
| 3 | 10..2000 | 0.83 | 1.36 | 8.63 |
| 3 | 10..1000 | 0.97 | 1.33 | 6.99 |
| 6 | 10..3000 | 1.54 | 1.23 | 1.41 |
| 6 | 10..2000 | 2.95 | 0.97 | 1.37 |
| 6 | 10..1000 | 0.95 | 0.98 | 1.36 |

Crucial limitations: independently activated BIN and VALUES, so zero-offset is not physically synchronized. Butterworth approximates unknown original filters. Some correlations are low: ADC6 velocity 10..3000 corr 0.438; ADC3 displacement 10..3000 corr 0.264. Thus amplitude agreement does not prove cycle-by-cycle equivalence. Reproducible script, JSON and Russian report supplied in conversation as `stage87_validation_package.zip`. No raw industrial data in GitHub. Next isolate ADC3 displacement discrepancy and extend 43 bands. Stable v0.3.40 untouched; offline only.
