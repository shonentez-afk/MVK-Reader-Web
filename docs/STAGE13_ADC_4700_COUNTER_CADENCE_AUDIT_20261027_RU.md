# Stage13 — audit of ADC and 4700 counters across all four existing PCAPNG (27 Oct 2026)

Only offline read of user-provided device 83/84 PCAPNG. Code: local `counter_alignment_audit.py` (container artifact), no device network access.

## Established directly from the frame headers
ADC packet marker `0xff800adc`, size 1052: per-frame channel id at offset +20; sample-origin counter at +12 (uint32 LE), increments by **256** samples per ADC block, including across wrapping arithmetic. All eight channels have **zero non-256 counter discontinuities** among parsed ADC frames of four captures. Each block holds 256 samples at fs=65536 samples/s.

Calculated packet marker `0xff800c0d`, **EXACT size 4700**: counter at +20 (uint32 LE), increases **130** between consecutive calculated frames. Exclude 44/76/160-byte packets sharing marker.

| PCAPNG | complete 4700 | consecutive intervals | calc step | per-ADC sample step | TCP |
|--|--:|--:|--:|--:|--|
| realtime83 | 59 | 58 | 130 each | 32768 each | no gap, parsed to end |
| realtime84 | 60 | 59 | 130 each | 32768 each | no gap, parsed to end |
| recording83 | 60 | 59 | 130 each | 32768 each | one 847-byte TCP gap; malformed tail |
| recording84 | 60 | 59 | 130 each | 32768 each | no TCP gap; malformed tail |

Thus the 4700 publish rate is **2 Hz** (one frame per 0.5 seconds), and its separate counter runs at an observed **260 units per second**. This is empirical counter-rate evidence only; the physical meaning/clock origin of the counter and exact DSP accumulation interval are not proven.

## Critical nuance for timing
At a 4700 packet, ADC frames may have a rotating channel phase; for example first 4700 realtime84 occurs after 31744 samples for ADC1–5 versus 32000 for ADC6–8, a difference of ONE ADC packet (256 samples = 3.90625 ms). This phase is a framing / interleaving effect, not evidence of a channel-specific DSP delay. Use the ADC header sample counter (+12) and 4700 tick counter (+20) as separate time axes, never silently equate numerical values.

Recordings 83 and 84 each contain damaged/unparsed stream tail or one stream gap, so parser stopping is not proof the entire capture is intact. The prior lag sweep ±1s showed ADC6 device84 underprediction persisted ~8–13%. Establishing 2Hz frame cadence does NOT fix that discrepancy or prove a DSP delay.

## Next decisive step
Compute the affine relation between the two counter clocks (ADC 65536/s vs reported calc 260/s) within each capture, estimate stable residual phase in samples. Evaluate packet interleaving independently. Then test counter-aligned common-frame subsets and hold out a portion of frames for lag selection, without changing frozen MVK-LAB06 weights or channel gamma. Proper synchronization still requires knowledge of DSP filter/window delay; do not claim time alignment merely from packet order.

No changes to frozen production v0.3.40; no private captures stored on GitHub.
