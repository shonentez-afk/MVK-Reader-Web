# Stage 13.13 — ADC4 independent-session readiness and absolute-error triage

Date: 2026-10-27. Systematic continuation of ADC4 third-octave reconstruction after Stage 13.12.

## Inputs and evidence boundaries
This analysis **reaggregates the actual Stage13.12 20 heldout rows** from the 11:18 BIN+VALUES pair; it is NOT an independent second-session validation. In the current workspace no second complete synchronized ADC4 BIN+VALUES pair has been identified. Several PCAPNG recordings are present but should not be misrepresented as the same session as VALUES. No refitting, no additional lag selection, no changes to frozen v0.3.40.

Original full-band model: causal order=4 scipy Butterworth SOS bandpass at exact base-2 third-octave centers, common -0.25s relative epoch hypothesis, signal anti-alias decimation depending on band, 1s trailing RMS.

## Holdout median values, 20 rows
|Center Hz|Median device output m/s2|Median model m/s2|Median absolute difference m/s2|Median abs percent error|
|---|---:|---:|---:|---:|
|31.5|0.157500|0.153878|0.003522|2.2416|
|40|1.023000|1.025962|0.005989|0.5829|
|50|0.036805|0.048213|0.011279|30.9991|
|63|0.025500|0.026838|0.001488|6.2329|
|80|0.069520|0.070652|0.003482|4.7562|
|100|0.265450|0.257879|0.008040|2.9776|
|125|0.449600|0.465362|0.019797|4.4518|

The 50Hz band accounts for approximately 0.00637% of the **sum of medians of device third-octave powers over the 34 bands >=5Hz** (a descriptive statistic, not necessarily actual factory wideband rms energy). Its relative error is large while its contribution is tiny. Do not tune the entire filter bank to reduce one weak-bin percentage.

Other threshold evaluations from SAME heldout rows:
- level >=0.005 m/s2: 638 comparisons, median abs relative 3.085%.
- >=0.01: 545 comparisons, median 2.456%.
- >=0.05: 482 comparisons, median 2.180%.
- >=0.1: 460 comparisons, median 2.140%.
- >=0.2: 397 comparisons, median 2.103%.

**Avoid claiming any of these are independent session tests.** The bandpass architecture is promising on heldout times but only one source session has source BIN+VALUES. Remaining priorities: (1) derive 50Hz residual by adjacent 40Hz skirt coupling, inspect beat/PSD and exact nominal edges without modifying released coefficients; (2) test fixed model on actual independent ADC4 PCAP against its per-frame 4700 calculated third-octaves, respecting data encoding/clock; (3) confirm cross-device results (#83 and #84); (4) include real amplitude and status filters in QA.
 
Generated reproducible script in current working runtime `/mnt/data/mvk_stage13/adc4_stage13_13_strength_audit.py`, source `adc4_stage13_12_band_frames.csv`, output `adc4_stage13_13_absolute_bands.csv`. This report is evidence-only; all source files are local until separately committed. Research branch only, v0.3.40 untouched.
