# Stage13.19 — ADC4 low-frequency temporal-window transfer check (2026-10-27)

## New independently executed experiment
Original synchronized 15-second PCAPNG for #83 and #84, raw calibrated ADC4, AUX word62 for low-frequency displacement 0.8..300Hz. Anti-alias polyphase downsample by 64 to 1024Hz. Tested trailing Hann-FFT PSD displacement RMS and **fixed** temporal windows 4/6/8s, lower cutoff 0.9765625, 1.0625, 1.125, 1.25 or 5Hz. Fixed relative effective frame offset +0.25s from earlier stage (not proven physical hardware delay). Restricted to frame k16..29, all windows valid. Selection strictly on #83 k16..22 (seven frames), untouched #83 k23..29 and #84 k23..29 seven frames each. No new calibration/gain or #84-driven selection.

**Selected on #83 train**: 4-second trailing window, cutoff 0.9765625Hz. Median absolute relative errors:
- #83 train 15.2998% (n=7)
- #83 holdout 30.9019% (n=7)
- #84 train, evaluation only, 6.1150% (n=7)
- #84 holdout 5.9059% (n=7)

Even within #83 the train-selected method deteriorates by ~2x on the next 7 frames. It is *not* a recovered factory ULF averaging window. Do NOT introduce into MVK Reader Web production. Additional context: cutoff .9765625 on fixed 6-second windows gives #83 holdout 25.1%, #84 holdout 4.28%, while fixed 8-second gives #83 holdout 27.1%, #84 holdout 4.34%; these are descriptive, not selected results. The original 34 third-octave bands above 5Hz from Stage13.15 remain a different, previously separately tested task.

## Boundary conditions
The algorithm is rectangular frequency-mask integration of a Hann periodogram, not the frozen W9/S9 composite or a real OEM IIR/high-pass response. Seven frames per partition within one short recording, strongly correlated; cannot estimate stable holdout uncertainty, and comparing models by same source may overfit. Periodogram start-up/edge effects and unknown device averaging explain plausible mismatch, but evidence does not identify a specific mechanism. Infer nothing about lower-wall physical specification or whether #83/#84 OEM differ.

## Verifiable artifacts in active runtime
- `/mnt/data/mvk_stage13/stage19_lf_temporal.py`
- `/mnt/data/mvk_stage13/stage19_frames.csv`
- `/mnt/data/mvk_stage13/stage19_summary.csv`

Next step: do NOT continue tuning FFT window/cutoff against 15s recordings; require longer >=60s transition recording and independent physical excitation with stimulus record, or isolate another known OEM calculation path from MVKView binary; keep native raw, device-derived, experimental metrics distinguished.
