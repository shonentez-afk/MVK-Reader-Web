# Stage 60 — verification of channel control records against manufacturer specification

Original evidence: manufacturer protocol v1.0.39, sections 3.5, 3.7.9-3.7.11 (Modbus register map). Independent evidence: offline PCAPNG captures from units 83 and 84, parsed using existing cap_parse.py.

Each channel 160-byte message contains 128 bytes, interpreted as eight records of 16 bytes: (float32 current_value, uint32 status, float32 value_at_last_change, uint32 reserved). Identifiers are 0x2130+0x200*N, matching documented Modbus offset A+0x130, A=0x2000+0x200*N.

Checked 960 records per instrument (8 channels x 8 parameters x 15 snapshots). Instrument 83 has zone codes 0x00, 0x11, 0x12, 0x14, 0x15, all documented by manufacturer. Instrument 84 has zero-filled control records, but its ADC measurements are present. Channel 2 / parameter 4 has green in 9 and red in 6 snapshots. Seen event masks (status >> 8): 0, 0x02, 0x04, 0x08, 0x0c. These correspond to event bits 9-11 from document.

Important caveats:
- Fourth (reserved) word is nonzero in 17 records of instrument 83. Preserve raw uint32; don't assign an invented meaning.
- Some parameters have nonzero current values while status zone is 0x00; do not discard measurements solely on status=0.
- Actual physical parameter number is in channel configuration (Aconfig+0x60/0x70, 32 bytes per parameter), NOT inside the status record. Need match configuration before labeling individual metrics.
- Manufacturer document defines Modbus/502, not the proprietary TCP/10230 envelope. Structural compatibility was empirically verified, but versions 1.0.39 and later firmware are not assumed byte-for-byte identical.

Local evidence: MVKVIEW_STAGE60_CONTROL_VERIFIED_20261028.zip, CONTROL_FIELDS.csv (128 channel/parameter rows), TEST_RESULTS.txt, validate_control.py. Stable v0.3.40 untouched.
