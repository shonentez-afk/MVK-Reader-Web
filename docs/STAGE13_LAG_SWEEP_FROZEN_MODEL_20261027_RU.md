# Stage13 lag sweep: frozen MVK-LAB06 vs ADC/4700, 2026-10-27

## Goal and constraints
Verify if a temporal shift alone resolves empirical P1.4 discrepancy. Existing frozen `instrument_reconstructed_v3.py` retained, no coefficient/gamma fitting; compare output to 4700 acceleration RMS 10-3000 from saved TCP/10230. Input: VAST_MVK per-channel gain, ADC frames, device-calculated 4700. This is **position-based** stream alignment, not proven device-DSP sample-window correspondence.

## Executed runs
- On realtime 83 and realtime 84, scanned lags `[-2,-1.5,-1,-0.5,0,+0.5,+1,+1.5,+2]` seconds for ADC 4,5,6,8, every 5th 4700 frame. Median errors logged. Full third recording in this sweep exceeded resource limit and was stopped.
- On recording84, performed reduced independent sweep `[-1,0,+1]` sec ADC 5 and 6, 64 comparison rows.
- All four captures were previously decoded; recording83 has known 847-byte TCP gap and is not accepted as reference.
- Comparisons at different lags can contain differing number of eligible frames; avoid choosing a winner based solely on aggregate median without fixed common timestamp subset.

## Core findings: model relative to device, median signed error %
| Dataset, ADC | -1 sec | 0 sec | +1 sec |
|---|---:|---:|---:|
| Realtime84 ADC6 | -12.63 | -11.84 | -12.04 |
| Recording84 ADC6 | -7.67 | -8.02 | -9.49 |
| Recording84 ADC5 | -5.19 | -6.17 | -6.00 |

For realtime84 ADC4, median absolute percentage error 0 sec = 5.48%, +0.5 sec = 1.11%; this indicates window alignment can matter substantially for some channels, **not** that +0.5s is proven DSP latency. ADC6 remains 8–13% low under tested shifts; lag alone does not resolve the frozen model's discrepancy on #84.

## Important conclusions
1. Do not refit upper-edge coefficients from same #84 frames and report them as independent validation.
2. Do not claim precise DSP delay until 4700 counter mapping and window boundary semantics are established.
3. Strong priority: compare per-frame header/counters, TCP frame order and interpolation/time-shift against exact *same* 4700 frame ID; report stable-subset metrics and cross-validate lag (select on first half, assess second half).
4. Device84 model mismatch potentially involves averaging window, calibration, nonstationarity, or filter-window shape. No one explanation proven.
5. Preserve normative Butterworth model as independent baseline. Production v0.3.40 unchanged.

Local reproducibility: /mnt/data/mvk_stage13/lag_sweep.py (experiment), /mnt/data/mvk_stage13/lag_sweep_fast.py (restricted), /mnt/data/mvk_stage13/lag_sweep.log, /mnt/data/mvk_stage13/lag_sweep_fast.log. These local analysis files are not committed via this GitHub note.
