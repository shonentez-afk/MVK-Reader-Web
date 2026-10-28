# MVK01 handbook evidence: calculation of fixed frequency bands (2026-10-27)

Source: VАRB.411711.112 RE (2019), Appendix 1, pp. 41-44 (printed pages); same PDF stored at docs/vendor/ВАРБ.411711.112 РЭ МВК.pdf. The public copy was examined textually. No claim is made that the manufacturer specifies Butterworth third order.

## What the handbook explicitly states
- p. 41: ADC fs=65536 Hz; FIR anti-alias filters decimate to 32768, 8192, 2048 and 512 Hz.
- p. 42, Appendix 1 sec. 2.1: high-resolution spectra computed using FFT after a Hann window.
- pp. 42-43, sec. 2.2: fractional-octave/third-octave bands formed by weighting spectral component magnitudes; squared components are summed, followed by square root and sensor scaling. The velocity/displacement weights also carry frequency-domain integration.
- pp. 43-44, sec. 2.3: fixed-band vibration metrics combine THREE power-sum contributions: lower cutoff transition using high-resolution spectra (0.8, 2, 10 Hz); upper cutoff transition using third-octave spectra (150, 300, 1000, 2000, 3000 Hz); passband regions with relative transfer coefficient equal to one. Square root, then sensor scaling.
- p. 44, sec. 2.4: user-defined bands use summed third-octave squares without transition windows.

## Implications
This explicitly refutes treating vendor fixed-band RMS as an ideal rectangular integral of raw-signal PSD. Soft transition weighting at upper cutoff is documented and may account for ADC6 discrepancies when energy is high near and above 3000 Hz. However exact window weights/response values, transition width, DSP source code, and Butterworth order are NOT specified in the cited text. The previous third-order Butterworth match (<0.35% over six bands) is an **empirical surrogate model**, not manufacturer-confirmed implementation. Do not introduce the Butterworth model into production as an authoritative reconstruction.

## Next reproducible test
Using existing ADC4 and ADC6 BIN and vendor documentation, reconstruct the documented three-region spectral energy weighting; seek numeric fractional-octave window coefficients from additional manufacturer materials or controlled reference spectra. Preserve provenance of each implementation and do not fit the order to the same six reference values. The existing frozen v0.3.40 remains unchanged. No network or device access performed.
