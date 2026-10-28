# Stage 78 — TABLE CSV snapshot export

2026-10-28, offline reverse engineering original MVKView `_Unit128.pas` and 32 real TABLE CSV. 14/14 IDR anchors checked.

`Tmvkform.bWriteTableClick` at `0x0084E020` builds a file at `edLibraryPath` named `TABLE-yyyy-mm-dd--hh-nn-ss.csv`. It creates a text file with Delphi `@RewritText`; writes `sep=|` and header using localized `xParamName`; iterates checked channels (`cbFileChannels`) and writes their headings. For each result row it uses `ResultAdcCellList.GetTitle` and per-selected-channel `GetValueText`; similarly exports `ResultAdcBandCellList`; then an independent tachometer section from `ResultTachCellList` (up to two tach channels). Errors use `errCannotWriteFile` / `SpawnError`; the file is closed by `@Close` at `0x0084E6CD`.

All 32 TABLE CSV snapshots have 40 physical lines and `sep=|`, with 19 files exporting one ADC and 13 exporting three ADCs. These are point-in-time snapshots, not a chronological data series like VALUES. They are not time-aligned to archived PCAPNG; do not infer DSP lag from near-value comparisons.

Local package `MVKVIEW_STAGE78_TABLE_CSV_20261028.zip` includes full `REPORT_RU.md`, offline `analyze_stage78.py`, `FILE_PROFILES.csv`, and test results. No device commands or firmware work. Stable v0.3.40 untouched. Stage79 next: TSXML lifecycle, then BIN and end-to-end spectrum tests.

## Независимая проверка пакета в новом сеансе (2026-10-28)
Пакет `MVKVIEW_STAGE78_TABLE_CSV_20261028(2).zip` действительно открыт. Внутри `RESULTS.json`, `REPORT_RU.md`, `analyze_stage78.py`, `FILE_PROFILES.csv`. Независимо прочитаны **32 строки профилей**: все содержат флаги `has_sep=True`, `lines=40`; распределение `selected_adc`: 19 × 1 АЦП и 13 × 3 АЦП. `RESULTS.json` согласован с профилями. **В ZIP отсутствуют исходные TABLE CSV и IDR `_Unit128.pas`**: 14/14 IDR-опор — исторический результат из `RESULTS.json`, а не повторный прогон. Архив `Projects.7z` и база `mvkview.idp` доступны в локальном рабочем каталоге, но извлечение `Projects.7z` пока блокируется отсутствием локального 7z/py7zr (попытка установки не удалась из-за отсутствия сети). Повторная независимая проверка исходного кода и сырых CSV ещё ожидается. Для неё добавлен `tools/research/stage78_recheck_offline.py` (коммит `5c56f731`). Никаких подключений к приборам. Stage79 остаётся открытым.
