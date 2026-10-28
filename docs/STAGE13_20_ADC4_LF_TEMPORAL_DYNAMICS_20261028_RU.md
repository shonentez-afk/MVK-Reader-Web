# Stage 13.20 — ADC4 low-frequency temporal diagnostics (2026-10-28)

This is a **new executed diagnostic** on the previously generated Stage13.19 frame-by-frame comparisons. No MVKView executable was available in the active working folder. Original PCAPNG and decoder scripts are available, but this stage does not claim analysis of MVKView machine code.

## Method
From Stage13.19 CSV for each device ADC4 frames k16..29, compare AUX4700 displacement word62 (0.8..300Hz) to frozen 4s trailing Hann periodogram with 0.9765625Hz cutoff. On untouched k23..29 (7 comparisons), compute model median absolute percentage; naive one-frame persistence predictor using *the previous AUX reading* (not available to a raw-only offline reconstruction); sample Pearson correlation on holdout; lag-one AUX correlation over k16..29. Persistence is a **diagnostic baseline only**, not a replacement DSP model and has access to instrument output.

## Findings
|Metric|#83 ADC4|#84 ADC4|
|---|---:|---:|
|4s/0.9766Hz holdout median abs relative error|30.9019%|5.9059%|
|Previous-AUX-reading persistence holdout median abs relative error|1.2444%|6.0210%|
|Model vs AUX Pearson r on 7 holdout frames|-0.3393|-0.3913|
|Adjacent AUX reading lag-one r on 14 frames|0.9738|-0.0807|
|AUX holdout range|2.97um|11.47um|
|Model holdout range|18.66um|3.97um|

#83 AUX k16..29 smoothly decreases from ~45.01 to 35.66um; raw 4s trailing-FFT model fluctuates 38.83..57.49um after k23. #84 AUX varies 22.26..37.13um across k16..29, raw model much steadier, 28.70..33.70um. These are **incompatible temporal dynamics**, not evidence that tuning a common hard lower spectral wall will solve reconstruction.

Cautions: Only 15-second captures, seven heldout frames; frame-side alignment +0.25s is an effective hypothesis and may be incorrect for LF branch. Native AUX output may be processed with differing state/window, filtering, phase, or temporal alignment. No exact factory IIR time constant can be inferred, and persistence uses actual instrument observations, so cannot score it as a raw-to-indicator predictive algorithm.

## Artifacts
- `/mnt/data/mvk_stage13/stage20_temporal_diagnostics.py`
- `/mnt/data/mvk_stage13/stage20_summary.csv`
- `/mnt/data/mvk_stage13/stage20_series.csv`

Production v0.3.40 untouched. Maintain >5Hz IIR 3rd-octave validated baseline separately. Next: confirm AUX timestamps and relative packet sequencing, then seek >=60-second session with physical 1Hz signal step or switch; direct MVKView binary inspection only if executable is actually available.
