# Stage13: 1/3-octave class 2 and ADC6 upper edge, 2026-10-27

## Sources and boundaries
MVK01 manual VАRB.411711.112 RE, Table 4: class 2 third-octave filters per GOST R 8.714-2010. Independently checked GOST R 8.714-2010, section 4.4 and Table 1 (fractional-octave mapped limits), authoritative standard card https://protect.gost.ru/gost/details/e65eef54-f304-4416-a8b1-4292246f9d61 . Do not substitute newer GOST R 70024.1-2022 for the exact standard cited by the manual.

At nominal center 3150 Hz, approximate 1/3 octave edges calculated with base-2 conventions: 3150 * 2^(-1/6) = 2806 Hz, and 3150 * 2^(+1/6) = 3536 Hz. Exact GOST center/band-edge conventions may differ slightly. ADC6 prominent high-frequency peaks 3105 Hz and 3313 Hz are WITHIN the 3150 Hz third-octave passband.

GOST class-2 relative attenuation limits at center are -0.5 to +0.5 dB in GOST R 8.714-2010. Other normalized frequencies and edge/out-of-band positions have distinct limits; use formula (10)/(11) mapping for fractional-octave from Table 1, and linear interpolation per formula (12). Class 2 constraints describe an *allowed family* of transfer characteristics, not a unique filter, and do not specify a Butterworth order.

## Core distinction for 10-3000 Hz
The standard-conformant third-octave output centered near 3150 Hz may include strong ADC6 peaks near 3105/3313 Hz. However, the MVK fixed-band algorithm in Appendix 1 combines third-octave outputs with special upper-edge weights. The standard's passband tolerances do NOT determine those weights. Thus the device's effective fixed-band response at 3105/3313 Hz, or an asserted cutoff at 3300 Hz, CANNOT be derived solely from Table 4 or the class-2 mask.

## Verification state and next steps
VERIFIED documentary: class-2 requirement; 3150 Hz third-octave placement, nominal center and approximate boundaries; fractional-octave tolerances in the cited standard.
HYPOTHESIS: contribution of energy above 3000 Hz to the MVKView 10-3000 RMS through upper-edge weighting. No direct, uniquely identified vendor coefficients.
TODO: implement actual class-2 limit masks for the third-octave filter and compare an independently specified candidate transfer function against the mask; do NOT label a passing candidate as the actual MVK filter. Determine manufacturer's fixed-band upper-edge weights separately. No live device access; production v0.3.40 untouched.
