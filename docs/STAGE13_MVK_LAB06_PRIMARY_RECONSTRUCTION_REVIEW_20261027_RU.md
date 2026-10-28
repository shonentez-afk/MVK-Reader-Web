# MVK-LAB-06 as Stage13 primary experimental instrument reconstruction (2026-10-27)

## Decision / supersession
The user-supplied MVK-LAB-06 experiment is the **primary experimental reconstruction** of MVK01 Appendix 1 P1.2-P1.4 and fixed-band calculated quantities. Earlier work `tools/mvk_fixed_band_lab/fixed_band_normative.py`, `p14_two_spectrum.py`, `p12_p14_pipeline.py` remains useful as independent models and scaffolding, **NOT** the leading or more complete reconstruction. Do not restart solved ADC6/8 upper-edge research.

## Received source artifacts (local user uploads; do not mistake local attachments for a GitHub commit)
1. `instrument_reconstruction.py`, SHA256 `6e5346a8ee68ac24461243f26e13a84f82ec930fd328486bb56d07e7f4be7b21`
2. `INSTRUMENT_RECONSTRUCTION_dev83_20261027.md`, SHA256 `864b0e107ae7607f2c7a7a193b2cf66a73699efcb46ab32c0dc6d8f184be4458`
3. `instrument_reconstruction_dev83_20261027.json`, SHA256 `48759de47ecb8f08a0c5b26642f9de68f77409c9c5e241cf2fdf340bcdcf07b6`

Code and complete numeric report are preserved in the uploaded artifacts for this project. This registry records their provenance; it does **not** claim the full three files have been uploaded into GitHub. The Python file has fixed paths `/home/z/my-project`, so cannot yet be run end-to-end in a portable checkout without the RunUp BIN and MVKView TABLE datasets.

## Reproducible local check (actually executed)
- `python -m py_compile instrument_reconstruction.py`: PASS
- Imported the module and invoked `selftest()`: **12 PASS / 0 FAIL**.
- JSON has reported statistics consistent with document, namely:
  * acceleration (ВУ): median absolute 0.7995898%, max 3.8623429%;
  * velocity (ВС): median absolute 0.5951304%, max 34.2345685%;
  * displacement (ВП): median absolute 5.9749567%, max 108.4392796%.
- These tests are synthetic and internal consistency checks; no fresh end-to-end refit was run for this review.

## What reconstruction actually achieved
- Empirical v3 hybrid energy model: full-resolution low-frequency edge, flat mid-band energy, weighted upper third-octave edges, channel-specific fitted gamma.
- For 3000 Hz, empirical coefficients `w_3150=0.4053022408746561`, `s_4000=0.10487198698380487`, applied to energy contributions, not amplitude.
- ADC6/ADC8 issue is accounted for by measured energy above nominal 3000 Hz, including resonances in the 3150-Hz band.
- Fits six fixed-band rows × eight channels for each of acceleration, velocity, displacement, using RunUp 83 and six MVKView TABLE timestamps. The 48-cell acceleration fit median is ~0.80%; not a factory coefficient identification.
- Leave-one-channel-out for ADC6 is notably weaker (median 5.46%, maximum 18.62%). Some VS/VP low-frequency rows are substantially worse; avoid blanket `<5%` or `full DSP recovered` claims.
- Synthetic assumed third-octave calculation uses **42** centers 0.8..10000, while documented packet registers contain **43** 0.63..10000; this may differentiate calculated subset vs transmitted set but is NOT proven. Maintain all 43 protocol fields.
- Model labels or source-code claims `VERIFIED`, manufacturer's actual FIR coefficients, class-2 windows, third-octave window scalings and exact DSP averaging are not independently established by this fit.

## Action for next iteration
1. Preserve complete uploaded script/MD/JSON and portable input fixture with hashes, without pushing private RAW/PCAPNG.
2. Extract `instrument_reconstructed_v3` into a **portable inference-only** module, frozen weights and explicit calibration provenance, no embedded target-fitting or `gamma` derived from evaluation targets.
3. Validate frozen model on entirely independent device 84 and archived 4700 outputs, with no refit; report per quantity, band, channel, interval and status; compare only when window synchrony is defensible.
4. Compare normative HP3/LP3 model, preexisting two-spectrum P1.4 scaffold, and MVK-LAB-06 on identical input windows. Decide acceptance before integration; frozen production v0.3.40 untouched.

**No live device connections, no modifications to production.** This review supersedes the prior false impression that the newly written basic pipeline is the most advanced completed reconstruction.
