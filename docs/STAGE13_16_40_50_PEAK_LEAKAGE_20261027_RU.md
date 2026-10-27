# Stage13.16 — 40/50 Hz interband leakage verification

Reprocessed raw ADC4 from both 15s PCAPNG captures and confirmed the Stage13.15 filter frequency response using SciPy butter(4) SOS causal bandpass center nominal 40Hz, corner frequencies 35.076939..44.194174Hz. No refitting.

|Measure|Device83|Device84|
|--|--:|--:|
| Strongest PSD peak 25..70Hz |37.5Hz|50Hz|
| Welch PSD peak RMS within +/-1Hz |1.02543 m/s2|2.71748 m/s2|
| Stage13.15 AUX 40Hz heldout median |1.02097|0.11345|
| Stage13.15 model 40Hz heldout median |1.02380|0.16994|
| Frozen 40Hz filter magnitude at peak |0.99950|0.0528679|
| Estimated 40Hz RMS contribution from peak alone |1.02492|0.14367|

At device84 main 50Hz tone falls outside the 40Hz third-octave (40Hz band edges 35.08..44.19Hz); the current IIR filter transmits it with 5.29% amplitude and predicted contribution 0.144m/s2 already exceeds 0.1135m/s2 full 40Hz band reported by the instrument. This supports neighboring-peak skirt leakage as explanation for the over-prediction (49.62% median abs relative at 84, compared to <1% at 83). It does **not** identify precise OEM order or skirts. Full-capture Welch PSD plus heldout AUX medians are not frame-paired: these numbers are diagnostic only, and comparing ratios directly cannot establish exact gain. Freeze main v0.3.40 and use independent selection / heldout splits for any proposed filter redesign.

Executed scripts locally: stage16_verify_40_50.py and stage16_tone_check.py; outputs stage16_filter_response.csv and STAGE13_16_40HZ_50HZ_DIAG_RU.md.
