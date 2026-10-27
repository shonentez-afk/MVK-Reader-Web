# Stage13: trailing 2-second ADC-vs-4700 comparison, 2026-10-27

Offline-only audit of four attached PCAPNG, using previously frozen MVK-LAB06 v3 inference (no refitting). TCP/10230 reassembled by TCP sequence; parsed 33064-byte VAST_MVK header and per-ADC gain, ADC 1052-byte float frames, and **only** calculated frames whose marker is 0xff800c0d and exact size 4700 (short 44-byte messages also exist and must be excluded). Important corrected bug: ADC cumulative samples per channel = number_of_ADC_frames * 256 (not sum of each frame's sample length times 256).

At a 4700 record, accumulate already-seen ADC samples and compare current 4700 10–3000 acceleration RMS with frozen-v3 model over **preceding 2 seconds of recorded ADC data**. The temporal relationship is **position aligned within a single stream, not proven factory DSP integration interval**; possible internal pipeline delay. Every fifth calculated frame sampled to reduce computational load. 11 sampled frames per session × 8 channels × 4 files = **352 comparisons**. For 83 recording one known 847-byte missing TCP segment; exclude from acceptance, and its comparison is exploratory. For 84 recording malformed trailing/partial stream also observed.

Median signed error percent per channel, model relative to 4700:

| capture | ADC1 | ADC2 | ADC3 | ADC4 | ADC5 | ADC6 | ADC7 | ADC8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| realtime83 | +0.57 | -2.37 | +1.36 | +0.19 | -5.77 | -3.52 | -0.28 | -3.33 |
| realtime84 | -5.35 | +5.47 | +0.98 | -3.22 | -5.68 | **-11.84** | +0.52 | +2.31 |
| recording84 | -4.26 | +6.62 | +2.44 | +0.80 | -6.17 | **-8.02** | +0.92 | -1.08 |
| recording83 (TCP gap) | +2.54 | -1.42 | -1.59 | -0.97 | -3.41 | -3.21 | +1.06 | -4.70 |

Earlier full run of all 55/56 eligible 4700 frames in each realtime session was also observed before sampling for reproducible 4-file export: 83 realtime ADC6 median -2.87%, 84 realtime ADC6 median -11.09%. This supports stability of the problematic 84 offset; no inference about exact DSP delay.

Critical interpretation:
1. **Not accepted** as exact synchronized measurement: no proof that the preceding 2s ADC window matches manufacturer's 4700 DSP effective interval, no timestamp semantics fully identified.
2. Frozen MVK-LAB06 weights fitted on device83 show systematic **8–12% underprediction for ADC6 device84** in local windows. Earlier normative HP3×LP3 baseline sometimes matched better. Do not silently replace normative baseline or production.
3. Next experiments should test documented instrument frame counters, offset and target-free lag sweep and report error on held-out timestamps. Do not tune weights/gamma from the same evaluation 4700 frames.
4. Original captures/derived full rows remain local, not uploaded as source data. Production v0.3.40 unchanged.
