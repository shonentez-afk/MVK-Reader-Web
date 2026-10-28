# Recovery and progress register — Stages 59–63 (2026-10-28)

Research branch only; protected stable v0.3.40 untouched.

| Stage | GitHub report | GitHub script | Local original source package |
|---|---|---|---|
| 59 | docs/research/STAGE59_SESSION_ALIGNMENT_RU.md | tools/research/stage59_verify_session.py | MVKVIEW_STAGE59_SESSION_ALIGNMENT_20261028.zip |
| 60 | docs/research/STAGE60_CONTROL_RECORDS_RU.md | tools/research/stage60_decode_control.py | MVKVIEW_STAGE60_CONTROL_VERIFIED_20261028.zip |
| 61 | docs/research/STAGE61_LOCAL_FRANGE_FORMULA_RU.md | tools/research/stage61_local_frange_formula.py | MVKVIEW_STAGE61_LOCAL_GAIN_20261028.zip |
| 62 | docs/research/STAGE62_ARCHIVE_FRANGE_SOURCE_RU.md | tools/research/stage62_archive_frange_verify.py | MVKVIEW_STAGE62_ARCHIVE_GAIN_20261028.zip |
| 63 | docs/research/STAGE63_CONFIG_CONTROL_MAP_RU.md | tools/research/stage63_control_address_map.py | MVKVIEW_STAGE63_CONFIG_CONTROL_20261028.zip |

Reports and compact, standalone research scripts have been uploaded and commits confirmed. **These GitHub scripts are not byte-for-byte copies of every full local script.** Full original scripts, reports, data tables, and test outputs remain in local ZIP packages; big private PCAPNG, BIN, production configs, EXE are intentionally not mirrored to the repository. This manifest does NOT claim a complete mirror of every historical working file. Legacy archived tools 25–58 and byte-identical local scripts require a separate detailed file-by-file synchronization pass.

Critical Stage63 caveat: control slot index (1..8) is not the manufacturer's physical measurement parameter index (1..144). True mapping requires per-channel FC03 configuration read at 0x100+N*0x100+0x60+slot*0x10. The sample DefaultConfig contains zero selections and must not be used as actual unit configuration.

No write commands to instruments; all new research read-only/offline.
