# Stage 13.5: ADC4 11:18 BIN-to-VALUES holdout, 2026-10-27

Directly recomputed 18 fixed-band outputs and 43 third-octave outputs from actual same-session ADC4 BIN and VALUES files:
- BIN `MVK00000050-ADC4-2026-10-27--11-18-10.bin`, 2212096 float32 65536Hz acceleration samples, calibrated units.
- VALUES `VALUES-2026-10-27--11-18-09.csv`, 69 rows spaced about 0.5 seconds.
- Research script local `adc4_full_bin_values_1118.py`. No frozen coefficients changed.
- Hann-periodogram over one-second trailing signal; frozen MVK-LAB06 acceleration upper-edge weights used as same test weight on acceleration PSD, velocity PSD converted via (1000 / (2pi f))^2, displacement PSD converted via (1e6 / (2pi f)^2)^2. THIS IS A DIAGNOSTIC PROXY, NOT CLAIMED BIT-EXACT MANUFACTURER DSP.
- Hypothesized origin: BIN first sample 0.111s after first VALUES row, inferred only from filenames; absolute epoch still unproven.
- Candidate shift set [-1,-0.5,0,+0.5,+1]s; only 61 rows eligible for ALL shifts; first 30 train select shift using only acceleration RMS 10-3000; last 31 held out and used for ALL 18 outputs. Selected shift 0 seconds (relative to assumed origin).

## Holdout median absolute percentage error (31 common frames)
|band Hz|Acceleration|Velocity|Displacement|
|---|---:|---:|---:|
|10-3000|1.855%|0.689%|1.948%|
|10-2000|1.866%|0.699%|1.948%|
|10-1000|2.327%|0.685%|1.948%|
|2-1000|2.326%|1.039%|12.179%|
|0.8-300|3.126%|1.383%|368.103%|
|0.8-150|1.870%|1.339%|368.260%|

## All 43 thirds (same 1s 0-offset, evaluation subset)
851 comparisons where instrument third-octave RMS >0.01 m/s2, median absolute relative error 5.934%. Significant outlier nominal 31.5Hz ~83% median error, nominal 100Hz ~73%; need inspect 43 word mapping, spectral narrow peaks and actual filter bank/window before claiming accurate reconstruction.

## Interpretation
ADC4 broad acceleration/velocity are close; displacement below 2Hz is grossly wrong and must use separate proper LF processing (anti-drift, decimated signal path and long-duration filter/warm-up) rather than w/s upper-edge tuning. This supports Stage13.3 ADC4 same problem from a different recording. Three-quantity results are not a proof exact DSP transfer; notably applying same upper-edge acceleration coefficients to VS/VP is a diagnostic assumption.

Reproducible local artifacts: `/mnt/data/mvk_stage13/adc4_full_bin_values_1118.py`, `adc4_bin_values_18rows_frames.csv`, `adc4_bin_values_18rows_holdout.csv`, `adc4_bin_values_43_octaves.csv`, `adc4_bin_values_18rows_meta.json`. Raw data and tables not committed as GitHub source blobs. Main v0.3.40 unchanged.
