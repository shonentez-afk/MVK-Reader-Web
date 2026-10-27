# Stage 13.4b: independently calculated ADC4 BIN and VALUES, 2026-10-27

This step used actual **matching-session** sources already mounted:
- `MVK00000050-ADC4-2026-10-27--11-18-10.bin` + companion `.bin.tsxml`, 2212096 float32 samples = 33.75390625 seconds, 65536Hz, physical acceleration units.
- `VALUES-2026-10-27--11-18-09.csv`, cp1251, **69 0.5-second rows**, first 11:18:09.889 and last 11:18:43.888, 43 third-octave acceleration columns plus 6 fixed ranges × 3 physical quantities. This is NOT the earlier RunUp 08:54 dataset.
- Executed code locally: `/mnt/data/mvk_stage13/adc4_bin_values_1118.py`, with output `adc4_values_algebra_1118.csv`, `adc4_bin_window_1118.csv` and JSON summary. Source datasets excluded from GitHub due to data footprint / privacy.

## Instrument third-octave to instrument fixed-band acceleration, frozen P1.4 weights, 69 rows
| Range | Median absolute relative error | Max |
|--|--:|--:|
| 10–3000 | 0.128% | 0.165% |
| 10–2000 | 0.166% | 0.286% |
| 10–1000 | 0.196% | 0.819% |
| 2–1000 | 0.193% | 0.818% |
| 0.8–300 | 1.437% | 5.357% |
| 0.8–150 | 0.359% | 1.599% |

These are intra-device algebraic comparisons of third-octave outputs and fixed-band outputs, **not independent DSP validation**. Nonetheless they strongly cross-check the sum-plus-upper-edges formula on a later recording not used to derive frozen weights.

## Raw BIN to 10–3000 acceleration from one-second Hann windows
Full BIN unfiltered RMS (standard deviation) 4.59780 m/s2; full-record rectangular 10–3000 Hann RMS 4.37141 m/s2. No double multiplication by TCP gain on already-calibrated BIN.
With 1s trailing Hann windows and frozen edge weights `w3000=0.4053022408746561`, `s3000=0.10487198698380487`, hypothetical time origin BIN start = first VALUES row time +0.111s (suggested by filenames only, **not instrument-proven**), scanned endpoint time shifts:
| candidate shift (s) | usable values rows | median absolute error 10–3000 |
|--|--:|--:|
| -1.0 | 64 | 3.280% |
| -0.5 | 65 | 1.790% |
| 0.0 | 65 | **1.409%** |
| +0.5 | 65 | 2.966% |
| +1.0 | 65 | 2.988% |

**Caution**: number and identity of eligible frames are not strictly identical across shifts; this initial comparison is diagnostic, not a holdout-selected factory timing result. Absolute epoch and DSP latency remain unresolved. Dataset's BIN `.tsxml` has `From=0`, `To=33753.91ms`, without a proven absolute sample-start clock; filename shows start around 11:18:10 only.

## Next gate: ADC4-first
1. Finish same-record matched 69-row raw BIN to ALL six bands and all three quantities with common rows, train/holdout split, and source timestamps; flag discrepant low-frequency velocity/displacement without tuning weights to evaluation targets.
2. Compare row-wise third-octave histogram vs raw BIN on same windows; examine low-band center conversion, genuine class-2 skirts and decimation.
3. Package reproducible script and smaller fixture hashes into GitHub as research-only, not production `v0.3.40`. Preserve model basis distinctions: instrument's third-octave outputs vs our own PSD bins.
