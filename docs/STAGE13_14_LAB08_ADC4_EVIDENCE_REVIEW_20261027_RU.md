# Stage 13.14 — critical audit of uploaded MVK-LAB-08 against ADC4-first programme

Received three supporting artifacts `lf_capture_verify.py`, `lf_capture_verify_dev83_dev84_20261027.json`, and `LF_CAPTURE_VERIFY_dev83_dev84_20261027.md`. Inspected their actual code/JSON. **This stage reviews supplied computations; it does NOT independently rerun full PCAPNG decoding**.

## What the evidence establishes
Uploaded script processes device83/device84 ~15-second PCAPNG with 30 device calculated 4700-byte frames each. Per-frame device status for ADC4 is zero on both. Report maps 4700 word 48..65 to six consecutive triples (acceleration, velocity, displacement). It compares **one full-capture Hann PSD** with **medians of 30 device calculated frames**. It does not infer a factory DSP latency or perform 30-frame holdout validation.

ADC4 #83 vs #84 reported nominal 10–3000 errors:
- Acceleration +0.749% vs +4.024%;
- Velocity -0.366% vs +0.028%;
- Displacement -2.222% vs -2.729%.

For displacement 0.8–300:
- Simple lower edge from nominal 0.8Hz gives #83 **+80.559%**, #84 **+27.663%**.
- Starting spectral integral from next third-octave center (0.9765625Hz), without new gain weights, gives #83 **+6.141%**, #84 **+0.409%**.
Same for 0.8–150 at these channels. **This is a hypothesis about an effective lower edge, not proof of proprietary high-pass filter or nominal physical integration bound.** It derives from prior session #13 and tests the rule on later captures.

## Important source-review cautions
1. The report claims word44/45 zero means buffers filled. Zero can simply mean *no flag or a counter with another convention*; absent an independently confirmed field definition, do not prove buffer readiness from zero.
2. `aux_t` derived from capture decoder may encode a calculation counter or device uptime; the assertion `absolute uptime ~55000s` needs confirmed units/epoch. Do not use it as an absolute clock.
3. Some reported rows are noisy/damaged channels (83 ADC1 short, ADC5 open; 84 ADC7/8 open). Keep them out of primary accuracy aggregates, but retain as status regression cases.
4. The ULF 0.63–1.6Hz abnormalities and 4–8s correlation experiments are exploratory and not our next priority. User explicitly requested focus **above 5Hz**.
5. The distinction between different signal paths for rows and exported third-octave bands is plausible; the submitted tests do NOT rigorously prove internal firmware architecture from a few differences. The statement that 2–1000 and 10–1000 are 'not nested' may equally reflect differences in filter response, time-window alignment, or nonstationarity; hold as hypothesis.

## Next ADC4-first experiment
- Keep frozen 34-band causal Butterworth SOS model from Stage13.12 and single common BIN/VALUES timing offset. **Validate 5–10kHz third-octaves on PCAPNG 83 and 84** with their internally co-captured ADC and 4700 frames; training/holdout window selection against 83 then untouched test on 84, filter coefficients not refitted.
- For fixed metrics compare matched 4700 frames, not the median versus a whole-record PSD, on a consistent set of window endpoints and test windows; report 6 x3 tables plus statuses.
- Treat 0.8Hz displacement rule as a separate exploratory hypothesis, without diverting the main 5Hz+ focus. Do not merge into production v0.3.40.

This report intentionally avoids claiming re-execution of original source code whose `/home/z/my-project/` paths are environment-specific.
