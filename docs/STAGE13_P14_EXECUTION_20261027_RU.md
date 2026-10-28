# Stage13 - P1.4 implementation and offline execution audit, 2026-10-27

## Authority and scope
Primary specification: manufacturer handbook VАRB.411711.112 RE, Appendix 1, algorithms P1.2, P1.3 and P1.4, printed pp. 42-44. The architecture requires a high-resolution spectral path for the lower-edge term and third-octave powers for the upper-edge and interior terms. This is NOT identical to summing a single FFT with rectangular band limits. The exact proprietary FIR, third-octave windows, upper and lower fixed-band weights, buffering and time averaging are still unknown.

## Implementation
- `tools/mvk_fixed_band_lab/p14_two_spectrum.py` keeps high-resolution PSD and third-octave powers separate, combines three disjoint power contributions, checks duplicate use of octave bands.
- `tools/mvk_fixed_band_lab/tests/test_p14_two_spectrum.py` contains 3 synthetic tests: squared amplitude weights, independent paths and overlap rejection.
- `tools/mvk_fixed_band_lab/bin_hann_preflight.py` provides independent Welch Hann 1-Hz frequency-bin diagnostics on exported float32 BIN; it does **not** claim to compute proprietary P1.4 output.

## Actually executed locally
A faithful local copy of the current p14_two_spectrum.py numerical functions and three GitHub test cases was executed in the local Python environment using `python -m unittest -v`: **3 passed, 0 failed**. This does not certify the untouched GitHub checkout or untested production program.

Separately, scipy.signal.welch (fs=65536; Hann window; nperseg=65536; noverlap=32768; density scaling; DC detrend) was executed directly on both uploaded BIN files:

| Band, Hz | ADC4 RMS m/s2 | ADC6 RMS m/s2 |
|---|---:|---:|
| 10-1000 | 4.008267 | 1.673414 |
| 10-2000 | 4.314398 | 1.917671 |
| 10-3000 | 4.366450 | 2.860347 |
| 3000-3536 | 0.328961 | 2.865118 |
| 3000-3500 | 0.319350 | 2.787191 |
| 3500-5000 | 0.827021 | 4.054397 |
| 5000-10000 | 1.123306 | 11.133442 |

ADC4: 2,212,096 samples, 33.75390625 s, mean 0.483709, std 4.597803. ADC6: 4,000,256 samples, 61.0390625 s, mean 1.779480, std 13.922322. Both were previously checked for finite samples. These measurements characterize signal energy and are **NOT** values predicted by the full P1.4 vendor algorithm.

## Acceptance status
- Structural separation of P1.4 paths: IMPLEMENTED.
- Synthetic numerical tests: 3/3 PASS locally (equivalent copied code).
- Device-specific FIR and 1/3-octave amplitude windows: UNKNOWN.
- Fixed-band edge window coefficients: UNKNOWN.
- Vendor-equivalent acceleration RMS from P1.4: NOT COMPUTED.
- MVKView metrological acceptance: NOT PASSED.
- Production v0.3.40: UNCHANGED; no live device connection.

## Next implementation gate
Read the handbook diagrams and formula definitions first, extract any numeric coefficients actually present, then introduce traceable weight tables. No fixed-band weight may be estimated from the same target RMS and subsequently described as manufacturer-specified. Validate with independent spectral test vectors and existing BIN before integration.
