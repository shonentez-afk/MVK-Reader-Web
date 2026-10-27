# Stage13: normative explanation of Butterworth order 3, 27.10.2026

## New independent evidence
MVK01 manual VАRB.411711.112 RE (2019), Appendix 1 sec 1.3, printed page 39 explicitly relates the relative frequency transfer function for the **2-1000, 10-1000, 10-2000 and 10-3000 Hz** fixed bands to **GOST ISO 2954-2014**. Crucially, sec 5.3 of this GOST specifies a bandpass response resulting from a cascade of **third-order Butterworth high-pass and third-order Butterworth low-pass** sections; the normalized frequency response is described by transfer functions (1)-(6). This is INDEPENDENT documentary support for **order 3**, previously picked empirically from ADC6 RMS.

References:
- Manual primary: https://propribory.ru/static/upl/23-03-2023/BkodyDMPWOsJJuQe/%D0%92%D0%90%D0%A0%D0%91.411711.112%20%D0%A0%D0%AD%20%D0%9C%D0%92%D0%9A.pdf
- GOST public official card: https://protect.gost.ru/gost/details/8a2554be-3817-4a6f-ad0a-ac6dd5db525b
- GOST section 5.3 with explicit Butterworth-3 statement: https://allgosts.ru/17/160/gost_iso_2954-2014

## What this confirms and DOES NOT confirm
CONFIRMED: standard names two third-order Butterworth sections; manual invokes this standard's relative frequency sensitivity for the listed fixed bands; thus Butterworth-3 is now a **normative shape candidate**, not a baseless order fitted to one BIN. The six cross-band comparisons under 0.35% are consistent with this evidence.

NOT PROVED: implementation exact coefficients in device DSP, whether HP and LP are analog prototypes discretized by bilinear transform or digital SciPy butter with fs=65536, FIR decimation stages, Hann block length/averaging and edge-window weights. The manual P1.4 explicitly computes upper boundary using third-octave spectra. Numerical equality of a digital Butterworth response is evidence for an equivalent frequency response, **not** proof DSP implements IIR sections or uses scipy.signal.butter.

## Additional important manual findings
- Explicit 10-3000 acceleration register A+0x60 in Appendix 2 sec 3.4, A=0x2000+N*0x200.
- P1.3 mentions 42 third-octaves but 3.4 allocates 43 floats and 3.5.5 enumerates 43 central frequencies. Unresolved.
- Channel readiness status bits 4,5,6 mean buffer not filled; avoid treating transient calculated outputs as fully ready.

## Action
Reevaluate `tools/adc_filter_edge_audit/check.py` as a **standard-inspired response check**, but continue marking it experimental. Implement normative frequency response directly from GOST formulas and test whether digital-vs-analog discretization and measurement windows matter; do not replace production v0.3.40 without independent acceptance.
