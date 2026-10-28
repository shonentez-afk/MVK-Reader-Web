# Stage13: MVK-LAB-07 original PCAPNG reparse — 2026-10-27

## Source and reproducibility
Independently reparsed the two actual user-uploaded PCAPNG captures (device 83 first, device 84 separately), using the accompanying cap_parse.py, not merely reading the supplied MVK-LAB-07 JSON. Results agree with CAPTURES_VERIFY_dev83_dev84_20261027.md.

| Metric | Device 83 | Device 84 |
|---|---:|---:|
| ADC 1052-byte frames | 30702 | 30716 |
| Calculated 4700-byte frames | 30 | 30 |
| TACH 284-byte frames | 7674 | 7678 |
| AUX 44-byte frames | 3837 | 3839 |
| AUX 76-byte frames | 30 | 30 |
| AUX 160-byte frames | 135 | 135 |
| TCP gaps/overlaps/conflicts | 0 / 0 / 0 | 0 / 0 / 0 |
| 4700 counter increment in consecutive frames | 130 each | 130 each |
| ADC counter increment in consecutive per-channel frames | 256 each | 256 each |
| Final truncated ADC frame | 816 / 1052 bytes | 816 / 1052 bytes |

Across each interval between 4700 frames, the per-channel ADC stream advances 32768 samples = 0.5s at 65536Hz. Both devices publish calculation frames at 2Hz. This proves publishing cadence, NOT the vendor DSP integration window length or internal processing delay.

## Status bits confirmed from calculated frames
- Device83: ADC1 0x800, ADC5 0x400; other six channels zero.
- Device84: ADC7 and ADC8 0x400; other six channels zero.
Exclude abnormal sensor-status channels from healthy-channel accuracy statistics while still retaining raw observations.

## Quality and remaining limitations
These captures are distinct from the four previous approximately 30-second PCAPNG. Do not merge their time axes or compare unrelated medians. The truncated final ADC frame is capture-stop truncation and not an internal ADC sequence break. cap_parse.device_streams metadata bug: destination address erroneously assigned key[2] (source port) instead of key[1]. Fix in a later parser patch before using destination metadata.

The verified 130 calculation ticks per 32768 ADC samples yields a rate ratio, but does not identify the relative clock epoch. Next priority: fit the affine counter relationship with stable residuals across frames, inspect buffer/processing latency, then hold out calculation frames to test frozen MVK-LAB-06 against the normative baseline on common windows. Device84 ADC6 near 4kHz is the most informative stress case; do not refit frozen coefficients on evaluation data. Preserve main v0.3.40.
