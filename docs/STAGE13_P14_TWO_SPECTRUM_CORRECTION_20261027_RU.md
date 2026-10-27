# P1.4: correction of the Stage13 algorithm structure

Source: VАRB.411711.112 RE Appendix 1 sections 2.1-2.4, printed pages 42-44 (PDF pages 42-44). The original technical description is explicit:
- P1.2 produces high-resolution acceleration spectra from Hann-windowed FFT on decimated rates.
- P1.3 calculates third-octave acceleration / velocity / displacement spectra with **amplitude windows**, power summing, sqrt, and sensor coefficient.
- P1.4 calculates the **lower transition from high-resolution acceleration spectrum**, the **upper transition from third-octave spectra**, and an unweighted middle third-octave sum where Kpr=1. Power contributions are combined before sqrt and scaling.
- User-defined bands in sec 2.4 are a DIFFERENT algorithm (unweighted third-octave summing).

## Identified defect in our scaffold
The earlier `mvk_stage13_fixed_band.py` applied three zones to a single high-resolution PSD. That does NOT reproduce P1.4. It is retained for historical experimental comparisons but must not be labeled a vendor reconstruction.

## New implementation
`tools/mvk_fixed_band_lab/p14_two_spectrum.py` now represents both paths distinctly. `third_octave_power` forms band powers by multiplying the high-resolution PSD by the **square** of externally supplied amplitude windows; `fixed_band_power` combines lower high-res, upper third-octave and interior third-octave energy without double counting. Added three synthetic tests in `tests/test_p14_two_spectrum.py`.

Still unknown: true manufacturer octave windows, FIR stages and FFT lengths, normalization, lower/upper coefficients, and per-window timing. These are not invented. Testing of committed code has NOT been run in a clean checkout during this turn; never report PASS. Production v0.3.40 remains untouched.

## Investigation process correction
The official manual should have been treated as the primary source before fitting cutoff, Butterworth orders or empirical weights. Prior numerical experiments remain observations but should not be presented as direct identification of the manufacturer's DSP. Prioritize primary-source review, then a mathematically explicit implementation, synthetic tests, and only then comparison with BIN/MVKView.
