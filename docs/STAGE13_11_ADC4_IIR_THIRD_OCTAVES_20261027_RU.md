# Stage 13.11 ADC4: actual time-domain third-octave IIR experiment (2026-10-27)

## Actual execution
Original device83 calibrated ADC4 BIN from 11:18:10, matched 69-row VALUES export from 11:18:09 (independent startup; absolute clock remains unknown). Script `adc4_stage13_11_iir.py` executed locally. Raw Fs=65536Hz downsampled with anti-aliasing polyphase by 32 to Fs=2048Hz. For center frequencies 31.5 and 100Hz, exact base-2 nominal center `1000*2**(round(3*log2(nom/1000))/3)`; one-third-octave corners `fc*2**(+/-1/6)`. Digital scipy.signal.butter order 2,3,4,6,8 with SOS bandpass; compare causal sosfilt and zero-phase sosfiltfilt. Full-signal filtering, 1s trailing RMS windows, candidate offsets -0.25,0,+0.25s (relative to filename-inferred origin). Same 39 rows 19..57, first 19 select model per center, second 20 holdout. No fitted gain, no post hoc filter coefficients or holdout tuning.

## Best models by training median abs percentage error
| Center | Selected (order, mode, offset) | Train median absolute % | Holdout median absolute % |
|--|--|--:|--:|
| 31.5 Hz | 4, causal, +0.25s | 2.102% | **2.528%** |
| 100 Hz | 4, causal, -0.25s | 2.854% | **2.978%** |

For comparison prior STAGE13.10 rectangular spectral-bin models had ~83.64% / ~73.84% holdout error at 31.5/100 Hz. Note that stage13.10 used 34 later rows, not exactly the same 20 heldout rows; this makes percentage improvement indicative, not a perfectly paired direct comparison.

Independent train-selected outcome on 31.5Hz shifted +0.25s; if shift -0.25s were chosen retrospectively, heldout would give 2.242%, but *do not report that as the selected holdout result*. Both channels select the same order-4 causal bandpass shape. Other variations e.g. 100Hz order4/causal/0s give 3.49% holdout. A causal bandpass of Butterworth order N in scipy becomes a 2N-order transfer function overall; describe as scipy order=4, not necessarily manufacturer 4th-order overall.

## What is and is not established
This is strong evidence for a continuous time-domain IIR bank with finite skirts, as opposed to instantaneous brick FFT passbands on these two tones. It is **not proof of exact proprietary filter order**, IEC compliance, physically timestamped delay, or all-43-band agreement. Device-specific gain/calibration, time averaging and exact center definitions still require independent validation.
Do not apply arbitrary data-driven separate offset for each frequency in released code. Next step impose SINGLE shared BIN-to-VALUES offset chosen by an independent wideband anchor, then evaluate all 43 third-octave bands across both devices with no channel-by-channel lag fitting. At frequencies <5Hz remain diagnostic-only, as requested by operator. Separately verify window RMS method and additional factory averaging.

## Files produced and verified in current container
`/mnt/data/mvk_stage13/adc4_stage13_11_iir.py`,
`adc4_stage13_11_iir_frames.csv` (2340 model/row comparisons),
`adc4_stage13_11_iir_summary.csv` (60 aggregate candidate rows).
All input BIN and VALUES loaded and computed; production v0.3.40 unmodified.
