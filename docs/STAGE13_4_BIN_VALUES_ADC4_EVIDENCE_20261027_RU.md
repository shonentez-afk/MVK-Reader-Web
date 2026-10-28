# Stage 13.4 — BIN/VALUES cross-check, ADC4-first (27 October 2026)

## Supplied evidence
Newly uploaded `BIN_VALUES_VERIFY_dev83_20261027.md`, `bin_values_verify.py`, and `bin_values_verify_dev83_20261027.json`, relating to RunUp device83 `RunUp27-10-2026 08-54-11` (8 ADC BIN), 47 timestamped VALUES CSV rows at 0.5s and six TABLE CSV snapshots. The underlying BIN/VALUES/TABLE files were NOT reprocessed in this step; audit checked the provided code/JSON and calculations reported therein. Do not imply fresh full-data recomputation.

The source comparison uses each row's **instrument-generated 43 third-octave acceleration values** to reconstruct the same row's instrument fixed-band RMS, with the earlier frozen upper-edge empirical weights. This is not the same as predicting device values from raw BIN; the band outputs and target RMS originate from the same instrument and may share underlying DSP. It is an excellent internal algebraic consistency test, but **not an independent full-chain raw-to-DSP validation**. The earlier weights were originally fitted on TABLE aggregates of the same RunUp session, so the 47 VALUES rows are an out-of-fit-target check, NOT independent-session validation.

## Verified numerical aggregates
- 47 rows ×8 channels×6 ranges = 2256 acceleration fixed-band comparisons; device83 **ADC4** has 282 comparisons, median absolute error **0.188352%**, p95 **1.961038%**, maximum **4.113422%**, all 282 within 5%.
- Accel, all channels, 10–3000: median 2.148916%, 367/376 within 5%.
- Accel, all channels, 2–1000: median 0.265249%, 376/376 within 5%.
- 0.8–150 acceleration: median 2.213556%, 242/376 within 5%; important unresolved lower edge.
- User-defined 'Польз. 1' 100–10000 Hz: RMS acceleration from band powers median error **0.007235%**; velocity from frequency-center conversion **0.814675%**; displacement from frequency-center conversion **2.520569%**.
- Important caution: JSON `polz1.by_q.ВС/ВП` **naively sums acceleration units without conversion** and reports enormous errors ~286.6% and ~378.8%. Those are wrong for VS/VP by construction; the correct converted result is in `sv_fp_mechanism.polz1_ВС_conv` and `polz1_ВП_conv`. Preserve both explicitly with their method labels; do not present contradictory numbers without explanation.
- The fixed VS/VP range models made from third-octave energy sums are poor; proper frequency-domain weighted integration and low-frequency anti-drift/filtering are separate outstanding tasks.

## ADC4-first actionable program
1. Use this VALUES data as an instrument-to-instrument algebraic oracle for each of the 47 times: validate all six acceleration fixed bands and User 1, for healthy ADC4. Read status of associated measurement when available.
2. For complete raw-to-output test, synchronize **the corresponding ADC4 BIN from RunUp at 08:54:11** with matching 47 VALUES rows. Do NOT substitute unrelated ADC4 PCAP from 15-second LAB07 captures.
3. For low frequency VS/VP: compare differential energy `RMS(2–1000)^2 - RMS(10–1000)^2` and `RMS(0.8–300)^2 - RMS(2–1000)^2` on same rows; treat the second cautiously because upper edges differ and will NOT cancel. Estimate bandpass / integration transfer function using BIN if available, on held-out times. Do not force octave sum where continuous PSD is needed.
4. Check instrument manual Appendix1 P1.1–P1.4 against fixed and user-defined integration definitions; avoid conflating 42 fitted bands with 43 transmitted fields.
5. Then generalize fixed verified operations to remaining healthy channels, retain bad-sensor flags and stress tests.
Production v0.3.40 unchanged.

## Engineering conclusion
This evidence **substantially strengthens** the reconstruction of acceleration fixed-band algebra and user-defined-band energy summation for device83 ADC4, but does **not** yet resolve large low-frequency displacement error found in the separate LAB07 ADC4 PCAP analyses. Keep these as separate validation layers, with provenance.
