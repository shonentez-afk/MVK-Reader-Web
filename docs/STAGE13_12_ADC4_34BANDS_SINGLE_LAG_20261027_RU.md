# Stage13.12 — ADC4 unified IIR octave-bank holdout, 2026-10-27

## Executed
Actual 11:18 device83 ADC4 BIN and matching independently started VALUES (69 half-second rows). One global relative timing shift **-0.25s** from earlier wideband acceleration test, no band-specific lag search. Fixed causal scipy Butterworth order=4 bandpass (SOS, total transfer order=8), centers exact base-2 with 1/3 octave bounds fc*2^(+/-1/6). Anti-aliased polyphase decimation chosen by band (fs 2048 for <=500Hz, 8192 for <=2kHz, 32768 for <=8kHz, original 65536 for 10kHz). Continuous full-file sosfilt and trailing 1-second RMS for VALUES rows 19..57; train 19 rows, untouched holdout last 20. No coefficient fitting on either subset. Operator directed focus >5Hz; 34 bands 5..10000 included (other 9 from .63..4 Hz excluded).

## Results
On holdout, 545 comparisons where VALUES band acceleration exceeds 0.01 m/s2: median abs relative error **2.45583%**. This threshold excludes weak signals from composite percentage headline, but all band rows remain in CSV. Key holdout median abs errors: 31.5 Hz **2.24157%**, 40 Hz **0.58285%**, 80 Hz **4.75619%**, 100 Hz **2.97761%**, 125 Hz **4.45185%**, 50 Hz **30.99913%**. Weak sub-~25Hz bands have high percentage errors (e.g. 5Hz 18.57%, 12.5Hz 22.82%), many at small levels. One common lag and filter design generalize surprisingly well on multiple bands; this is evidence of a physically plausible IIR filter bank, not conclusive identification of manufacturer's exact method.

## Boundaries
Time origin was inferred from filename; true BIN start versus VALUES start remains unproven. Model SOS corner frequencies nominal, no IEC tolerance verification yet. Train/holdout share same recording, not independent session. Different decimation sample rates may influence filter approximation. Do not call this a measured 34-band factory transfer. Need inspect absolute errors, bias by band and amplitude thresholds, add real other-session dataset, verify warm-up and timing; use no <5Hz calibration. Production v0.3.40 untouched.

## Locally executed script/output
`/mnt/data/mvk_stage13/adc4_stage13_12_all_bands.py`, `adc4_stage13_12_band_frames.csv`, `adc4_stage13_12_band_summary.csv`.
