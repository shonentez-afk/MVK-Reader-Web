# MVK-LAB-07 capture review, 2026-10-27

User supplied six items: cap_parse.py, capture_verify.py, cap_series_diag.py, cap_outlier_diag.py, CAPTURES_VERIFY_dev83_dev84_20261027.md, captures_verify_dev83_dev84_20261027.json. They describe distinct ~15-second captures “83 первый” and “84 отдельно,” not the four ~30-second PCAPNG previously tested.

Locally confirmed: Python syntax valid; cap_parse 16/16 selftests pass, capture_verify 9/9 selftests pass after correcting local test paths. JSON: device83 30 AUX4700 and 30702 ADC packets, device84 30 AUX4700 and 30716 ADC packets. Source analysis records no TCP gaps and no sample counter gaps. Device83 ADC1 status 0x800, ADC5 0x400; device84 ADC7/8 0x400. Treat these as abnormal sensor status for healthy-only statistics.

Evidence for MVK-LAB06 upper edge model: device83 ADC6 10-3000 instrument 3.40558, model 3.36262 (-1.26%), rectangular -16.68%; device84 ADC5 instrument ~9.608, model -4.96%, rectangular -38.54%. Exception: device84 ADC6 instrument ~15.207, model ~11.907 (-21.70%), rectangular -84.92%. Very high energy near 3.8–4.2 kHz makes this channel an informative stress case. Empirical weights were frozen from prior runup83: no independent proof of proprietary FIR and no permission to refit on 84.

Important code issues to address: cap_parse.device_streams emits dst=key[2] (source port) rather than destination IP key[1]. capture_verify main comparison uses full-record PSD against median 4700, not true synchronized matching windows; computed 2-s windows not used for those rows. Calculated aux_t uses ADC counter estimator, not proven DSP timestamp. Velocity and displacement use simple rectangular integrals rather than empirical fixed-band edge model. Third octave protocol retains all 43 fields including 0.63 Hz; mapping not fully proven.

Next: use corrected parser and both counters to verify true per-frame alignment and holdout comparison, with explicit abnormal-sensor masks; compare LAB06 vs normative HP3/LP3 without target-dependent calibration. No production v0.3.40 changes.
