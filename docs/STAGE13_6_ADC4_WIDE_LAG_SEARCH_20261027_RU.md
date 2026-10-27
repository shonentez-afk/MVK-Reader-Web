# Stage 13.6 — ADC4 BIN/VALUES wide lag scan, 2026-10-27

## Operator correction and experiment
Operator verified that ADC BIN and VALUES were initiated separately, approximately 1–2s apart. TABLE is manually requested and must not be used as frame-synchronous ground truth. Prior filename-derived epoch +0.111s is merely a coordinate origin and is not measured synchronization. Rescanned 11:18 device83 ADC4 BIN against matching 69-row VALUES.

Actual input: `MVK00000050-ADC4-2026-10-27--11-18-10.bin` (2212096 physical-units float32 acceleration samples, Fs65536) and `VALUES-2026-10-27--11-18-09.csv` (69 half-second rows). Model: Hann periodogram, fixed frozen LAB06 upper-edge acceleration RMS 10–3000Hz. Candidate relative endpoint shifts -5 to +5s, increments 0.25s, for trailing windows 1, 2 and 4 seconds. For **each duration**, all 41 candidate shifts evaluated on the EXACT SAME eligible VALUES row IDs; first contiguous half selected shift by median absolute % error, second contiguous half held out (not optimized).

| Window | Common frames / train / holdout | Chosen shift relative to former +0.111s origin | Train median abs % | Holdout median abs % |
|---|---|---:|---:|---:|
| 1 s | 45 / 22 / 23 | -0.25 s | 0.768% | **0.917%** |
| 2 s | 43 / 21 / 22 | +0.50 s | 0.914% | 1.851% |
| 4 s | 39 / 19 / 20 | +1.50 s | 1.340% | 1.570% |

Unshifted 1s (same 45 eligible frames) 1.197% train / 1.681% holdout. In 1s grid, other prominent train candidates: +3.00s 1.638% train / 2.620% holdout; +0.25s 1.741% / 3.597%; -0.50s 1.825% / 2.122%. Thus -0.25s is not just nearest to original guess: the control half also prefers it among the candidates. **But** it is still a relative effective matching offset, NOT established physical start time of either file or native DSP latency; no dedicated clock pulse or instrumental timestamp link.

**Critical comparison caveat**: each duration has a slightly different set of common eligible rows and held-out count (45/43/39), so the 1/2/4s comparison is descriptive, NOT a perfectly paired holdout between durations. The within-duration shift ranking IS frame-balanced. Need a single shared subset of 39 rows to compare all three lengths fairly, and inspect spectral shape/time variation; do not declare the factory DSP integrates exactly 1s.

Full grid 123 candidates captured locally in `/mnt/data/mvk_stage13/adc4_lag_search_grid.csv`, analysis scripts `adc4_lag_search_fast.py` and `adc4_lag_search_long.py`. Inputs were actually reprocessed from the original files in current runtime; no table timing was used and no coefficients were refitted. Main production v0.3.40 unchanged.

## Next gate
1. Select durations jointly on same frame set; report strict train/held-out performance, parameter sensitivity, absolute instrument-value stability.
2. Apply chosen timing to all 18 ADC4 fixed-band outputs (6 ranges x VU/VS/VP), look at LF 0.8-300/150 displacement *after* alignment.
3. Validate 43 octave bands on same aligned frames and check 31.5/100Hz outliers, exact filter response.
4. Only after ADC4 path is established expand to other healthy ADCs.
