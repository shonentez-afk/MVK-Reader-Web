# Stage13: independent 0.63 Hz audit on four uploaded PCAPNG, 2026-10-27

Offline-only actual run. Inputs: recording 83, realtime 83, recording 84, realtime 84 (uploaded in current chat). TCP/10230 streams assembled by TCP sequence, duplicate TCP data discarded; no detected sequence gaps in the investigated streams. Found complete 4700-byte calculated summary frames: 60, 59, 60, 60 respectively, 239 frames / 1912 per-ADC channel records.

Field check: in each 584-byte channel record the first third-octave float32 slot is at record offset +8 (word 1), interpreted nominally as 0.63 Hz according to decoder.py and Appendix 2. A second 0.8 Hz slot is at +12. The first slot was NONZERO repeatedly, across BOTH devices and all eight channel positions. Examples:

- recording 83: channel 1 60/60 nonzero, channel 5 60/60 nonzero, channel 6 50/60 nonzero.
- realtime 83: channel 1 59/59 nonzero, channel 5 59/59 nonzero, channel 6 6/59 nonzero.
- realtime 84: channel 6 60/60 nonzero, channel 7 60/60 nonzero, channel 8 60/60 nonzero.
- recording 84: channel 1 60/60 nonzero, channel 6 60/60 nonzero, channel 8 60/60 nonzero.

This REFUTES the hypothesis that the first third-octave slot is a permanently empty/zero placeholder. It does NOT explain why P1.3 textual description says 42 bands while Appendix 2 and real TCP carry 43. Likely the text number is a count/edition inconsistency or another nuanced distinction, but neither is established.

All actual source files remain private and were not committed. This test is a direct follow-up of existing tools/raw_offline_audit/decode_4700.py mapping, with PCAPNG stream reassembly. Frozen v0.3.40 was untouched and no device connection occurred.

Next steps: fieldwise compare 4700 RMS vs same-time TABLE/VALUES/Modbus; preserve all 43 frequencies in decoder and do not throw out 0.63 slot.
