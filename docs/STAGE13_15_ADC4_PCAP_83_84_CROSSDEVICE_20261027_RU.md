# Stage13.15: PCAPNG ADC4 third-octave IIR external test (2026-10-27)

## Execution and data
**Independently re-executed** parser on original `83 первый(1).pcapng` and `84 отдельно(1).pcapng` in active container. Both yielded 30 AUX4700 frames, ADC4 raw 982528 and 983040 samples respectively (~15s), zero ADC sequence gaps, calibration channel gain extracted from initial VAST_MVK header, ADC4 status 0. Raw values converted to acceleration by per-device gain. Frame timestamps are **relative sample-counter-derived** and are not confirmed manufacturer DSP calculation-latency stamps. Reused Stage13.12 *fixed* causal scipy butter order 4 bandpass (8th-order overall), exact base-2 1/3-oct centers, anti-alias resampling by band. 34 centers 5–10000 Hz. Each model output is trailing 1s RMS, compared directly to AUX words 1..43 in ADC4 for matching PCAP. Not a comparison with independently launched VALUES export.

## Time alignment
Evaluated relative endpoints AUX[k] + {0,0.25,0.5,0.75,1.0} seconds (the first AUX frame is relative time 0 by construction). Used same eligible k=4..14 and 34 bands on device83 for training offset choice, target >=0.01 m/s2. **Picked +0.25s** on device83 training (median abs % 2.7067%; +0s 2.7420%, +0.5s 3.0896%; weak preference; timing itself is not identifiable to better than .25s). No device84 data involved in selecting parameters. Test untouched AUX k=15..29.

| Device ADC4 | Period | Valid comparisons with device >=0.01m/s2 | Median abs percentage error | Median absolute error m/s2 |
|---|---|---:|---:|---:|
| 83 | train k4..14 | 306 | 2.7067% | 0.01070 |
| 83 | holdout k15..29 | 417 | **2.8321%** | 0.01008 |
| 84 | train k4..14 (not used) | 332 | 4.5231% | 0.04896 |
| 84 | holdout k15..29 | 453 | **5.2189%** | 0.04998 |

Selected band holdout median abs percentages:
| Hz | 83 | 84 |
|---|---:|---:|
| 31.5 | 2.06% | 9.41% |
| 40 | 0.69% | **49.62%** |
| 50 | 24.67% | 5.84% |
| 100 | 2.75% | 4.53% |
| 125 | 3.88% | 6.99% |

On 84, 40Hz instrument median 0.11345m/s2, model median 0.16994m/s2 (median abs error 0.05841m/s2), while 50Hz instrument 2.8963m/s2, model 2.8619m/s2. Hypothesis: strong 50Hz neighboring tone leaks into model 40Hz skirt; requires filter frequency-response calculation and spectral peak identification, not automatic gain/edge fitting. On 83, 50Hz weak band 0.04628m/s2 device, 0.05578 model, median absolute error 0.01004m/s2, 24.67% relative.

## Limitations
- 34 >5Hz bands tested; 9 lower bands excluded per operator instruction. Several low-level bands have high relative errors and <0.01 excluded from aggregate headline.
- Same-session holdout for device83 and independent cross-device test for device84; external validation is stronger than earlier BIN+VALUES holdout but is NOT proof of exact manufacturer filters.
- Sample-counter-derived timing; AUX first frame may have a capture boundary/phase offset and shared +0.25s is only an effective alignment. TRAIN performance +0 and +0.25 differ by only 0.035 percentage point; **do not claim physical DSP delay**.
- Frozen model and params, no gamma or band-specific offsets, no coefficient fitting. Main v0.3.40 unchanged.
- Input PCAPNG captures and parser files must be present to re-execute. Local `/mnt/data/mvk_stage13/stage15/stage15_pcap_iir.py` SHA256 `c1bba85e143e7d307c1f8b756d4cd04a41623cf83e657e42287b15fda6e77c90`.
- Outputs local: `all_band_frame_candidates.csv`, `selected_summary.csv`, `selected_band_holdout.csv`, `meta.json`.

## Next
Inspect 40/50Hz transmission and 84 actual peak using periodogram. Validate anti-alias/sample-rate and order effects with train-only optimization if needed then untouched device84 holdout. Confirm effective time alignment with signal changes and AUX frame timestamps. Only after this evidence passes propose non-production opt-in DSP kernel.
