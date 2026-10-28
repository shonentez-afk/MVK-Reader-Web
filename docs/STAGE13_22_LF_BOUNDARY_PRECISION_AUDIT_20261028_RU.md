# Stage13.22 — audit of LF boundary precision note and JSON (2026-10-28)

Reviewed user-supplied `NOTE_lf_boundary_precision.md` and `lf_boundary_parameter_v2.json` versus executable Stage13.18 (`stage18_wall_audit.py`). **The core correction is accepted:** the fitted 1.000521Hz is *not* a physical OEM DSP cutoff; with a rectangular frequency-bin inclusion mask the estimate is constant across whole intervals.

**Scope of 0.0625Hz:** valid **only** for `fs=65536Hz, n_fft=1048576`; then last rejected bin k16=1.0000Hz and first retained k17=1.0625Hz imply the exact mask-equivalence interval `(1.0000,1.0625]` using `f_k >= f_low`. The midpoint 1.03125±.03125Hz is a representation of that plateau, **not** measurement confidence. The statement of exact bit-for-bit equality depends on using the same bin mask/arithmetic, not a claimed OEM formula.

**Different actual FFT grids in our Stage13.18:** The stage18 script constructs `np.fft.rfftfreq(len(s),1/fs)` with **no zero-padding** after resampling by 64. With #83 ~14.9921875s, `n_orig=982528`, `df≈0.066701Hz`, the boundary mask removing the ~1.000521Hz bin means interval `(1.000521...,1.067223...]`. With #84 15s, `n_orig=983040`, `df=0.0666667Hz`, the corresponding bin centers 1.0 and 1.066667Hz. For shorter windows 4s/8s the grid is still coarser. **Never transplant the N=2^20 interval into Stage13.18/19 or the factory hardware.**

Also note: the uploaded note's statement that center-frequency inclusion and low-edge-of-bin inclusion yield identical assignments for the same cutoff is generally **not true**; for lower-edge criterion bin centers are effectively shifted by a half-bin. The specified plateau depends on the exact convention. Hann window leakage and model high-frequency corrections are separate sources of uncertainty, not captured by +/- half a bin.

A third caveat: Stage13.18 uses `np.trapezoid(vv,ff)` over *selected* bins; though still piecewise constant in cutoff, the first retained bin gets half weight, and this is **not** simply sum `PSD_k*q(f_k)*df` as written in the supplied markdown. This matters for exact reproduction of RMS numbers. Therefore restrict claims to 'equivalent for a specific implemented estimator' rather than claiming recovery of manufacturer processing.

The stated +6.14% -> -0.68% improvement for #83 ADC4 is a fit against the same capture; retain as demonstration, not independent validation. Remove interference-compromised #83 ADC7 from ranking; #83 ADC4 remains a *useful LF reference*, not global best. #84 ADC4 earlier capture is reported by operator to contain interference: **exclude it as a calibration/validation channel**. The new October 28 export labelled MVK00000043 includes ADC1,3,6, but is not yet proven identical to device84 from filename alone.

No production changes; `v0.3.40` remains frozen.

Corrected local machine-readable artifact: `/mnt/data/mvk_stage13/stage21/lf_boundary_parameter_audited.json`.
