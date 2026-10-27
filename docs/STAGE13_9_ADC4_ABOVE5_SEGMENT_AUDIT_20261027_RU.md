# Stage 13.9 — ADC4: diagnostic bands above 5 Hz; early vs steady segments (2026-10-27)

Independent calculation ran directly on actual device83 ADC4 BIN from 11:18, matched to available VALUES rows by prior **hypothesized** one-second-window offset -0.25 s (not absolute hardware clock). Used 66 complete windows, first 12 early (window end <7s after BIN start), next 16 middle, final 38 late (end >=15s). Hann periodogram and acceleration-to-displacement spectral conversion, no new fitting. Source script local SHA256: `180b87f9beab557d679ee8b07cd72d5137d2b68666882ae72d97d8b79d5c451f`.

| PSD-model RMS quantity | early median | middle median | late median |
|---|---:|---:|---:|
| Acceleration 5–300Hz, m/s2 | 1.705 | 1.816 | 1.759 |
| Displacement 5–300Hz, microns | 23.063 | 22.120 | 22.670 |
| Displacement 5–10Hz, microns | 13.558 | 11.806 | 13.182 |
| Displacement 10–50Hz, microns | 18.431 | 18.403 | 18.448 |
| Displacement 50–150Hz, microns | 1.121 | 1.104 | 1.118 |

Last segment, per-window median energy fractions for *displacement 5–300Hz*: 5–10Hz **33.759%**; 10–50Hz **65.959%**; 50–150Hz **0.239%**; 150–300Hz ~0.04%. Individual medians need not sum to exactly 100. These are *model* spectral energy contributions, not guaranteed factory DSP filter outputs.

No strong systematic excessive start-of-record effect is apparent above 5Hz; however the 5–10Hz band varies more between windows than 10–50Hz, so do not label it interference without independent measurement. Third-octave nominal rectangular bins versus instrument VALUES show persistent large **negative** bias: center 31.5Hz ~84% median abs error, center 100Hz ~74%, in early/middle/late alike, with local PSD peaks near **38Hz** and **113Hz**, just outside the nominal centers. The peaks outside the rectangular band and the sustained bias suggest actual device filter skirts, bin-to-band mapping, or different processing window; not proof of one specific cause. Fix word mapping/bandpass impulse response before conclusions.

Generated (in active runtime, not necessarily GitHub blobs):
`/mnt/data/mvk_stage13/adc4_stage13_9_above5.py`,
`adc4_stage13_9_above5_frames.csv`,
`adc4_stage13_9_octave_31_100.csv`,
`adc4_stage13_9_summary.json`.

Next: confirm center-to-VALUES column mapping, FFT peak positions and third-octave filter skirts on ADC4; measure 10–50Hz vs 5–10Hz temporal stationarity without using bands below 5Hz to fit model; compare wideband results only against same-range VALUES. Keep TABLE asynchronous. Production v0.3.40 frozen.