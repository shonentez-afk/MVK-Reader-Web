# Stage13.7: ADC4 strictly paired 1s/2s/4s window evaluation (2026-10-27)

## Actual computation
Script `adc4_stage13_7_paired.py` recomputed 3 chosen (duration, lag) candidates directly from the calibrated ADC4 BIN `MVK00000050-ADC4-2026-10-27--11-18-10.bin` against same-session `VALUES-2026-10-27--11-18-09.csv`. Same **39 rows, IDs 19..57** for all three candidates; first 19 train/inspection, final 20 held out. Proposed offsets from earlier separate-frame selection: (1s,-0.25s), (2s,+0.5s), (4s,+1.5s), all relative to filename-inferred epoch. No coefficients fitted here. None of the offsets is physical timestamp proof; they are effective alignment hypotheses. **Important: selected offsets came from Stage13.6 using distinct eligible row sets, so this is a paired evaluation of already selected candidates, not joint reselection.**

## Heldout median absolute relative errors (20 identical rows)
| Quantity/range | 1s/-0.25s | 2s/+0.5s | 4s/+1.5s |
|---|---:|---:|---:|
| Acceleration 10-3000 | 0.95% | 1.76% | 1.57% |
| Velocity 10-3000 | 0.85% | 1.09% | 0.94% |
| Displacement 10-3000 | 2.33% | 2.42% | 2.46% |
| Acceleration 0.8-300 | 1.87% | 2.51% | 2.21% |
| Velocity 0.8-300 | 1.47% | 1.05% | 0.74% |
| Displacement 0.8-300 | **318.19%** | **103.54%** | **62.12%** |
| Displacement 0.8-150 | **318.32%** | **103.57%** | **62.16%** |

All 18 quantity/range pairs were computed per window. The strong window sensitivity of 0.8Hz displacement is consistent with a low-frequency drift/leakage/integration problem in the simple periodogram proxy; cannot claim actual manufacturer's DSP wrong. Shared-row evaluation rules out an earlier comparison confound (different retained rows). One-second timing remains best in broad acceleration within this tested set; not a proof of factory integration duration.

## Third-octaves
Calculated 43 nominal rectangular frequency-bin accelerations on the 39 common rows for the 1s/-0.25s candidate. This is a diagnostic comparison only: actual octave-band filter skirts/windowing not yet reconstructed.

## Reproducible artifacts (conversation runtime)
`/mnt/data/mvk_stage13/adc4_stage13_7_paired.py`,
`adc4_13_7_paired_frames.csv`,
`adc4_13_7_paired_summary.csv`,
`adc4_13_7_octaves.csv`,
`adc4_13_7_meta.json`.
Research branch only; production v0.3.40 unchanged.

## Next gates
1. Jointly select (duration, shift) using identical train rows for every combination and report one heldout comparison per duration. Do not use holdout to choose parameters.
2. Inspect low-frequency PSD and per-bin contributions to 0.8-300 displacement; run anti-drift/highpass and spectral leakage diagnostics using ADC4 without fitting against heldout values.
3. Diagnose 31.5/100Hz third-octave differences; only then generalize to remaining channels.
