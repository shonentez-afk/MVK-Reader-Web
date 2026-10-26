# MVKView ADC 4: comparison with decoded 4700-byte frames (2026-10-26)

Source: user-provided screenshot of instrument A, ADC 4, and previously analyzed RAW capture from that instrument. Screenshot timestamp unknown: comparison is **not synchronous**.

| Field | MVKView | Range seen in previously decoded RAW | Record float32 index |
|---|---:|---:|---:|
| Sensor DC voltage (V) | 10.62 | 10.623-10.625 | 0 |
| Acceleration RMS to 25 kHz (m/s2) | 0.3766 | 0.365-0.384 | 47 |
| Acceleration crest factor | 4.639 | 3.981-6.732 | 46 |
| Acceleration RMS 10-3000 Hz (m/s2) | 4.467 | 4.233-4.639 | 48 |
| Velocity RMS 10-3000 Hz (mm/s) | 4.672 | 4.611-4.789 | 49 |
| Displacement RMS 10-3000 Hz (um) | 18.61 | 18.639-19.789 | 50 |

The 24 RMS fields occupy indices 48-71. Peak and peak-to-peak fields are separately arranged at 80-103 and 112-135. The screenshot gives an independent cross-check of label order and scale, not an exact same-time numeric equality.

Screen values should never be represented as a capture taken at the same instant as the RAW. Original proprietary source files and the screen capture are not committed.

Main Reader Web v0.3.40 was not executed or changed.
