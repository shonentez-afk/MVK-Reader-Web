# Stage98 Native R2: independent offline real TCP/10230 replay

Source: two previously provided PCAPNG captures, entirely offline; never paired/synchronized with MVK43 BIN and VALUES (different measurement sessions). Independent implementation based on `mvk10230_native/protocol.py`, not the older user-supplied v2 reader.

- PCAP 83: 108932 TCP payloads, 122 decoded AUX4700 frames, 4880 independently compared channel fields, 0 detected seq gaps, 5 retransmissions, 25 framing errors.
- PCAP 1111: 151661 TCP payloads, 169 AUX4700 frames, 6760 independently compared fields, 16 TCP sequence gaps, 18 retransmissions, 55 framing errors.
- Total: **291 actual AUX4700 frames, 2328 channel records, 11640 exact raw-versus-register-image comparisons**, all pass. Five compared values/channel: first third-octave band, first RMS, first peak, first peak-to-peak, uint32 channel status.
- Reader also recognizes ADC 1052, tach 284, structured 44,76,160,4700; results JSON and executable offline `r2_replay.py` in local package `mvk10230_native_R2_real_replay.zip` delivered to user, raw captures deliberately not committed.

**Limitations:** 25/55 framing errors are not explained yet and may reflect capture beginnings, missing packets, or simplified TCP reassembly. The replay code supports retransmission overlap/gap detection but not reordering or complete TCP stream provenance. Exact matching of 5 fields is NOT independently validated DSP mathematical equivalence for all 144 values and not a live device connection test. No network activity; no stable v0.3.40 changes. Next R3: ordered stream reassembly and session lifecycle, precise handling of truncated capture segments, full field comparison versus existing independent `decode_4700.py`.
