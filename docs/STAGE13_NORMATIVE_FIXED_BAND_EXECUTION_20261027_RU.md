# Stage13 fixed-band normative equivalent — executed 2026-10-27

Primary sources: VARB.411711.112 RE Appendix 1 §1.3 (fixed bands reference GOST ISO 2954-2014); GOST ISO 2954-2014 §5.3 third-order Butterworth high-pass plus third-order Butterworth low-pass; VARB Appendix 1 P1.2-P1.4 shows actual device three-zone FFT/third-octave integration. Existing repo research: docs/STAGE13_GOST_ISO2954_BUTTERWORTH3_20261027_RU.md and tools/adc_filter_edge_audit/check.py. No new guesses about exact internal implementation.

Code: `tools/mvk_fixed_band_lab/fixed_band_normative.py` computes frequency-domain magnitude-square weighted RMS from one-sided periodogram using **separately** designed digital HP3 and LP3. This is the GOST-inspired equivalent response; does NOT claim factory edge weights or proprietary DSP filter architecture.

Local execution on attached float32 physical-unit BIN files (fs=65536 Hz, full-run boxcar periodogram with DC detrending):

| band Hz | ADC4 RMS m/s2 | ADC6 RMS m/s2 |
|---|---:|---:|
| 2-1000 | 3.938269805 | 1.636408052 |
| 10-1000 | 3.938169109 | 1.629112616 |
| 10-2000 | 4.287050650 | 2.210320178 |
| 10-3000 | 4.365258579 | 3.542213511 |

ADC4 n=2212096 duration=33.75390625s; ADC6 n=4000256 duration=61.0390625s. Earlier MVKView VALUES median ADC6 10-3000 ~3.537: model ~+0.15%. Values not strictly synchronous. Earlier ideal cutoff ADC6 ~2.860. This confirms frequency-response modeling explains the main discrepancy; not a manufacturer algorithm identity proof.

Executed local Python unittest on exactly equivalent calculation and four test cases: 4/4 PASS. Tests cover HP3*LP3 cascade, cutoff -3 dB amplitude, tone RMS, invalid cutoff handling. A clean GitHub checkout test run was NOT performed.

Key difference to earlier experiment: original `tools/adc_filter_edge_audit/check.py` used a single SciPy bandpass butter(3,[low,high]); new version uses explicit HP3 and LP3 cascade, as described by normative reference. We did not silently overwrite earlier reports. Both remain experimental.

Next: apply fixed-band equivalent to all eight ADCs on existing calibrated PCAPNG or archived BIN with precise gain provenance; compare only aligned windows to instrument 4700 output. Then implement instrument P1.4 windows only when numerical coefficients are obtained. Production v0.3.40 unchanged; no connection to instruments.
