# Stage13 next step: 4700 decoder reconciliation, 2026-10-27

## Checked before adding code
Sources: manufacturer manual VARB.411711.112 RE Appendix 2, docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md, docs/FRAME_4700_REAL_RAW_REGRESSION_20261026_RU.md, existing tools/raw_offline_audit/decode_4700.py and verify_4700_mapping.py. Existing calculations are NOT repeated.

Confirmed on earlier captures: 4700-byte TCP/10230 calculated frame, 8 x 584-byte records, each 43 third-octave slots, 24 RMS/peak/span triplets; 48 frames/384 channel records in prior study. The 43 slots are also represented in Modbus decoder.py and documented Appendix 2. The reason P1.3 says 42 is UNRESOLVED, not a proven omitted 0.63-Hz band.

## New deliverables
1. `tools/raw_offline_audit/test_4700_calculated.py`: synthetic 4700-byte fixture, tests 8 channel records, 43 slots incl. 0.63 and 10000 Hz positions, first calculated RMS, status bit 4, zero padding, rejection of invalid marker/tag.
2. `tools/raw_offline_audit/audit_4700_first_octave.py`: uses **existing** `decode_4700.iter_frames` to summarize values of first (nominal 0.63 Hz) and last (10000 Hz) slot per channel across real RAW. Includes status values. No threshold or fabricated interpretation.

Run from root (offline): `python -m unittest tools/raw_offline_audit/test_4700_calculated.py -v`.
Then `python tools/raw_offline_audit/audit_4700_first_octave.py CAPTURE_A.raw CAPTURE_B.raw > first_slot.json`.
The preexisting RAW files are not uploaded to GitHub. This turn has NOT run new tests on a clean repo checkout or the private RAW files; statuses remain NOT RUN. No live device access. v0.3.40 unchanged.

## Acceptance criteria
- Run synthetic tests without failures.
- On original 2 RAW files, verify count 24 calculation frames each and 8 channel records/frame.
- Analyze whether first slot is always zero, varies, or correlates with channel status. A permanently zero first slot is evidence, **not proof**, of why 42 is written in P1.3.
- Next add non-destructive field-by-field comparison of time-aligned 4700 measurements with MVKView/Modbus exports, and explicitly capture time limitations.
