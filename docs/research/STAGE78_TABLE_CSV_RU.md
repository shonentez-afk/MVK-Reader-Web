# Stage 78 — TABLE CSV snapshot export

2026-10-28, offline reverse engineering original MVKView `_Unit128.pas` and 32 real TABLE CSV. 14/14 IDR anchors checked.

`Tmvkform.bWriteTableClick` at `0x0084E020` builds a file at `edLibraryPath` named `TABLE-yyyy-mm-dd--hh-nn-ss.csv`. It creates a text file with Delphi `@RewritText`; writes `sep=|` and header using localized `xParamName`; iterates checked channels (`cbFileChannels`) and writes their headings. For each result row it uses `ResultAdcCellList.GetTitle` and per-selected-channel `GetValueText`; similarly exports `ResultAdcBandCellList`; then an independent tachometer section from `ResultTachCellList` (up to two tach channels). Errors use `errCannotWriteFile` / `SpawnError`; the file is closed by `@Close` at `0x0084E6CD`.

All 32 TABLE CSV snapshots have 40 physical lines and `sep=|`, with 19 files exporting one ADC and 13 exporting three ADCs. These are point-in-time snapshots, not a chronological data series like VALUES. They are not time-aligned to archived PCAPNG; do not infer DSP lag from near-value comparisons.

Local package `MVKVIEW_STAGE78_TABLE_CSV_20261028.zip` includes full `REPORT_RU.md`, offline `analyze_stage78.py`, `FILE_PROFILES.csv`, and test results. No device commands or firmware work. Stable v0.3.40 untouched. Stage79 next: TSXML lifecycle, then BIN and end-to-end spectrum tests.