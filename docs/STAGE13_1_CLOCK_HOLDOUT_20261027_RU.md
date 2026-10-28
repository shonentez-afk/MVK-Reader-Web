# Stage 13.1 — common-frame counter alignment and holdout experiment (2026-10-27)

## Actually executed
On both user-provided 15-second PCAPNG (83 first and 84 separate), ran local script `stage13_1_holdout.py` with source SHA256 `e6158e772aca5ed0b78e44663a91b47be7fa561df0999b1ebb2237f2d2300305`. It imports the supplied `cap_parse.py`, reconstructs calibrated ADC, reads 4700 frames and compares the empirical fixed LAB06 upper-edge P1.4 formula with 10–3000 Hz acceleration frames. Frozen energy weights 3150: 0.4053022408746561 and 4000: 0.10487198698380487, **no fitting or evaluation gamma**.

All candidate windows use the **same eligible calculated frame IDs** per device and channel. Durations tested: 1, 2, 4 s; endpoint offsets: -1, -0.5, 0, +0.5, +1 s relative to ADC samples already transmitted at each 4700. First half (9 frames) chooses the lowest median absolute percentage error; remaining 9 frames are held out. Analysis used device83 ADC 4,6,8; device84 ADC 2,4,5,6. Sensor status must be zero. The candidate selection is an exploratory estimate, **not proven factory DSP latency**. 0.5s duration was intentionally excluded here because it would differ from original 2s spectral resolution/estimator; no acceptance claim about 0.5s integration.

## Counter clock relationship
Calc header +20 ticks progress exactly 130 per report. ADC sample-count progress 32768 per report (Fs 65536): exact 2Hz output. The per-channel invariant
`transmitted_samples(ch, frame) - (calc_tick(frame)-first_calc_tick)*32768/130`
is constant across the 30 reports:
- Device83 ADC1..8: 3072 samples.
- Device84 ADC1,2: 16128 samples; ADC3..8: 16384 samples.
The 256-sample discrepancy is just the ADC packet interleaving phase. **These constants are relative capture phases, not actual DSP latency**. The absolute epochs of the counters are not established.

## Held-out evaluation: percent median absolute error
| device ADC | train-chosen duration, lag (s) | held-out median abs % | unshifted 2s median abs % on same held-out frames |
|---|---|---:|---:|
| 83 ADC4 | 2, +0.5 | 0.506 | 1.097 |
| 83 ADC6 | 1, -1 | 1.395 | 2.076 |
| 83 ADC8 | 1, +1 | 8.632 | 9.098 |
| 84 ADC2 | 2, -1 | 6.986 | 6.041 |
| 84 ADC4 | 1, 0 | 1.123 | 5.369 |
| 84 ADC5 | 4, +1 | 4.417 | 4.421 |
| 84 ADC6 | 1, -1 | **14.389** | **10.398** |

Thus a shift/window change helps specific channels (#84 ADC4), but #84 ADC6 remains badly wrong on withheld frames; not solved by lag correction. The best offset varies by channel and should not be read as hardware channel latency.

## Parser fix and remaining work
`cap_parse.device_streams` has a metadata-only bug: `dst=key[2]` (source TCP port) rather than `dst=key[1]` (destination IPv4 address). A corrected local copy `cap_parse_fixed.py` was compiled; SHA256 `4ca247e854adcdf2d21d4a861a7100b83f7cc9c78295dda82089a5d9bd592d06`. The parser counts/PSDs were otherwise unchanged. Do not conflate this patch with decoded header clock mapping.

The executed CSV `stage13_1_windows.csv` and `stage13_1_summary.csv`, the script and clock JSON exist in the conversation runtime (under `/mnt/data/mvk_stage13/`), **not yet committed as complete artifacts**. Subsequent improvement must compare proper normative HP3/LP3 and LAB06 on identical heldout windows and, separately, examine #84 ADC6 3.8–4.2kHz spill/alias response. Full 4700 DSP integration window still unknown. Frozen production v0.3.40 untouched.
