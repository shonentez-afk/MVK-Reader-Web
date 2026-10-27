# Stage13.18 — ADC4 low-frequency displacement wall and time-window audit

Date 2026-10-27. **Independently executed** on original 15s PCAPNG of devices 83 and 84. Raw ADC4 parsed and calibrated with native gain; anti-aliased downsampling to 1024Hz. For frame k=4..29 trailing 4/8/12s FFT PSD Hann windows end at captured AUX relative time +0.25s (effective previously selected offset, **not validated actual factory latency**). Direct spectral acceleration-to-displacement per-bin weight q_disp = (1e6/(2*pi*f)^2)^2. Compare RMS 0.8..300um to AUX word62 for ADC4. Fixed candidate lower edges 0.8, 0.9765625, 1.0, 1.0625, 1.125, 1.2, 1.6, 5Hz. No selection on device84.

**Scope and limitation:** This is an exploratory direct rectangular spectral integral, WITHOUT the proprietary/frozen edge weight W9/S9 at 300Hz. At 0.8..300 displacement those high frequency contributions are small, but do not claim numerically identical reconstruction of prior composite #13; modest ~0.05um discrepancies may occur. The window model is not known OEM averaging, and frame offsets only effective synchronization hypotheses.

Full-file ~14.992s (#83) / 15s (#84) comparison to median device frames:
|lower edge Hz|#83 estimate um|#83 device median um|#84 estimate um|#84 device median um|
|--|--:|--:|--:|--:|
|0.9765625|41.5676|39.2085|31.4801|31.3306|
|1.0625|38.9175|39.2085|30.9501|31.3306|
|5|24.4082|39.2085|30.0366|31.3306|

Paired 8s windows at k from 4..29 with end+0.25s, 14 eligible frames/device:
|Device|edge .9765625 median abs %|edge 1.0625 median abs %|
|--|--:|--:|
|83|25.9404|13.5100|
|84|2.1424|6.4819|

These values expose time-window variability and show 1.0625Hz is not universally better than .9765625Hz on device84. **Cannot assign factory lower edge from a single ~15s PSD**, and should not introduce channel-specific tuned lower edges in production.

**Critical artifact of discrete FFT masks:** for 4s windows df=0.25Hz, wall 0.9766 and 1.0 select the SAME first bin (1.0); 1.0625 and 1.2 both select first bin 1.25. For 8s df=.125Hz, 0.9766/1.0 first bin 1.0, 1.0625 first bin 1.125. For full #83 capture length 14.9921875s, df=.066701Hz, first selected frequency for cutoffs 0.9766/1.0 is 1.000521Hz; for cutoff 1.0625 is 1.067223Hz. Thus previous reported bisection wall **1.000521** merely gives a *bin boundary*, not frequency precision to 0.001Hz. Calling wall around 1.06Hz physically established is incorrect. Even flat-window PSD masks cannot distinguish any walls falling between adjacent bin centers.

Inputs in original container:
`/mnt/data/83 первый(1).pcapng`, `/mnt/data/84 отдельно(1).pcapng`.
Artifacts:
`/mnt/data/mvk_stage13/stage18_wall_audit.py`,
`/mnt/data/mvk_stage13/stage18_wall_frames.csv`,
`/mnt/data/mvk_stage13/stage18_wall_summary.csv`.

Next: independently determine device DSP LF temporal averaging and filter skirts, ideally >60s with controlled 1Hz excitation; separate signal validity warnings from physical measurement values; retain v0.3.40 baseline unchanged.
