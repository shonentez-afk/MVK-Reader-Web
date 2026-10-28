# Stage 59 — session alignment audit

Offline review confirmed PCAPNG runs and TABLE/VALUES CSV are from different calendar days; value-nearest comparison from Stage58 was **not** synchronized validation.

Captured .83 on 2026-10-26 07:23:48–07:24:03; .84 on 2026-10-26 07:25:20–07:25:35. TABLE/VALUES .83 on 2026-10-27 and .84 on 2026-10-28. Each capture had 30 AUX4700 blocks. VALUES .83: 74 columns (timestamp plus 73 for ADC4), 69 rows. VALUES .84: 220 columns (timestamp plus 73 each for ADC1,3,6), 63 rows. First 43 columns of each group correspond structurally to 1/12 octave bands 0.63–10000 Hz; numeric temporal alignment requires simultaneous capture.

Local full report, script, results and VALUES_COLUMN_MAP.csv: MVKVIEW_STAGE59_SESSION_ALIGNMENT_20261028.zip. Stable v0.3.40 not modified.