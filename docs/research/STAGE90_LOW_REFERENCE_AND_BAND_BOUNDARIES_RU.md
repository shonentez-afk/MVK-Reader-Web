# Stage90 — low reference levels and boundary errors (2026-10-29)

Independent offline recalculation from Stage89 JSON (129 real MVK43 ADC1/3/6 band comparisons).

Median bandwise absolute relative error, all bands / reference median >=0.001 / >=0.01 m/s2:
ADC1: 6.69% / 3.38% / 3.16%; ADC3: 7.90% / 6.75% / 5.85%; ADC6: 10.49% / 5.51% / 4.78%. Counts after thresholds >=0.001: 33/34/33; >=0.01: 29/27/28 (ADC1/3/6). Diagnostic thresholds do not modify reference data.

Example low denominator: ADC1 0.63 Hz reference 1.491e-6 m/s2 and candidate 3.1468e-4, 22604% relative error. However ADC1 16 Hz 228.2% (reference 0.01969), ADC1 25 Hz 143.9% (0.06873), ADC3 40 Hz 147.2% (0.04722), ADC6 31.5 Hz 141.4% (0.01118) indicate mismatch also at meaningful levels. Transitions 4/5, 25/31.5 and 200/250 Hz differ by channel; a single off-by-one band index is not demonstrated. Cannot yet attribute the cause to exact filter response, edge tones or misalignment.

Reproducible script, source Stage89 JSON and report available to user in stage90_audit_package.zip. Raw BIN/VALUES not committed. Next: inspect actual spectral peaks near 16/25/31.5/40 Hz and compare halves of recording. No network/device connections; stable v0.3.40 unchanged.
