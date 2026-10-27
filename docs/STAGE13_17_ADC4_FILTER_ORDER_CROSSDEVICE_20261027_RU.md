# Stage13.17 ADC4 — filter order 4/6/8 non-retuned cross-device validation

Direct re-execution from both original PCAPNG captures (device83/device84), 30 AUX4700 frames each, ADC4 calibrated raw, 34 third-octaves 5..10000 Hz. Fixed causal Butterworth bandpass with scipy order N=4,6,8, same exact third-octave edges and same prior frame endpoint offset +0.25s; one-second trailing RMS. No new gain or per-band lag fitting. Holdout frames 15..29. On device83 training frames 4..14, N4 was best overall. Device84 was not used to select filter order.

|scipy order|83 train median abs %|83 holdout median abs % (417 comparisons >=0.01m/s2)|84 holdout median abs % (453 comparisons >=0.01m/s2)|
|---|---:|---:|---:|
|4|2.7067|2.8321|5.2189|
|6|3.1408|3.3228|5.2086|
|8|3.8415|3.8107|5.5728|

In device84 40Hz band, heldout instrument 0.113452m/s2; model median N4=0.169938, N6=0.072131, N8=0.064405. Median abs relative errors 49.62%, 32.98%, 42.43%. Current 40Hz IIR magnitude at 50Hz: N4 0.052868, N6 0.012181, N8 0.002803. **Increasing order alone overcorrects 50Hz leakage and worsens several source-83 bands**; not sufficient to identify proprietary filter response. Device83 31.5Hz median holdout abs relative N4 2.06%, N6 60.35%, N8 81.11%; 100Hz N4 2.75%, N6 13.63%, N8 26.24%.

Strong validation limitation: one 15s capture per device, small 11-frame train, 15-frame holdout; heldout within same sequence correlated. Comparison at fixed previously selected +.25s effective endpoint (NOT hardware latency). No cross-device tuning. Device84 6th-order tiny 0.01 percentage point aggregate improvement is not significant and is offset by worse bands. Primary recommendation: **retain N4 frozen as experimental baseline**, investigate third-octave center/skirts via targeted 40/50Hz transfer function and controls, without overfitting device84 holdout. Main MVK Reader Web v0.3.40 unchanged.

Artifacts created in active container:
- `/mnt/data/mvk_stage13/stage15/stage17_order_audit.py`
- `stage17_frame_comparisons.csv`
- `stage17_filter_50hz_response.csv`
- `stage17_summary.csv`
- `stage17_target_bands.csv`
