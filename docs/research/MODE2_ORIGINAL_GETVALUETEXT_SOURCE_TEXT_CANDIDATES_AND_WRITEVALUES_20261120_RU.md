# MVKView 1.0.47 — source GetValueText / потоковый WriteValues: текстовые кандидаты

**20.11.2026. Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. **Код:** [`55b1b40b`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/55b1b40be21766efdcc26a8018fdefdacab1d442). **CI нового кода:** [#44670485422](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44670485422) — считать PASS только после фактического completion/success всех пяти jobs.

## Исходная сверка, приватно

- `/mnt/data/Projects.7z` прочитан локально libarchive; извлечены `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`. Все **5/5** совпали по размеру и SHA256 с локальной `mvk_idr(1).sqlite`.
- `mvk_idr(1).sqlite`: `PRAGMA quick_check=ok`; проверены addresses/lines/call graph `007CE6E4`, `007CF4A4`, `007B2090`, `008066F0`.
- `mvkview.idp` — исходный третий приватный файл присутствует локально и использован как связанный IDP-источник из предыдущей сверки; независимая перепроверка IDP-типов в этом проходе НЕ заявлена. Не публиковать исходники, IDP, SQLite, PCAP/FIR/RAW в GitHub.

## Новые подтверждения по исходному машинному коду

1. `_Unit115:007CE6E4` — 30 входных типов (0..29), 13 фактически используемых ветвей plus default. `007CE77C` — float32 через `007B2090`, `007CE799` — IntToStr, `007CE7AC` — IntToStr U32, `007CE7C3` — дата, `007CE7F0` — время hh:mm:ss из секунд, `007CE8D4` — байтовый HEX, `007CE8E7` — индексы установленных битов, `007CE8FC` — IPv4 из DWORD, `007CE90C` — ограниченная текстовая ячейка, `007CE91F` — 0x + 8 HEX, `007CE92F` — 0x + 4 HEX, `007CE93F` — битовая маска, `007CE95B` — HEX-байты без пробелов. Ряд этих ветвей зависит от длины поля, языковых/Win32 параметров и требует runtime parity.
2. `_Unit115:007CF4A4` — type 10 с `TMvkAdvancedCell` НЕ форматирует число; извлекает Bits/BitStart и вызывает `GetTitleByID`. При доказанном nil Data возвращает `####`. Не путать с неполным сетевым DWORD.
3. `_Unit125:00804A30` — 3 Result Advanced на одном ADC `+0x120` со сдвигами **0/4/10** и ширинами **1/3/2**; дальше 3 float32 `+0x00/+0x5E/+0x5C`.
4. `_Unit125:008053B8` — TACH 2 Float32 + 4 Cardinal. Исходная схема PageFile **10 каналов / 43 SPEC / 36 VALUES**.
5. `_Unit125:008066F0` — исходный `WriteValues` строит строку `hh:nn:ss.zzz|...`, проходит отмеченные ADC (SPEC43 → Result6 → Band24), затем TACH6, заканчивает CRLF и преобразует Unicode в ANSI-поток; исходную кодовую страницу/Delphi Locale/все имена Advanced ещё не проверяли побайтово.

## Что реально добавлено коммитом

**Отдельный третий источник `SOURCE_Wxx_VALUES_3100_TEXT_CANDIDATE.csv`**, формируется на том же реальном тике `PARAM 0x3100` тем же Go writer. Существующие `SOURCE_Wxx_VALUES_3100_RECEIVED.jsonl` и `SOURCE_Wxx_VALUES_3100_RAW_LAYOUT.csv` сохраняются. Новая строка содержит локальный таймстемп и по порядку selected cell: Float32/UInt32 текст-кандидат, для Advanced — `UNRESOLVED_ADVANCED_ID_N`, для частичных/stale — `UNKNOWN`. Это не диагностические RAW-гексы в основном текстовом companion, но и **не выдаётся за точную строку MVKView**. Float32: приближённое воспроизведение исходного `FormatSpec=4` с 4 значащими цифрами и обрезкой хвоста; Delphi x87/locale/границы округления не подтверждены.

Дополнительные поля JSONL и audit: `source_cell_type`, `source_advanced_selected_id`, `source_text_candidate_line_sha256`, версия format candidate, имя/число строк/байт/SHA companion. Test coverage: порядок SPEC/RESULT/BAND/TACH, битовое извлечение Advanced, NaN/неполный TACH, SOURCE tick and SHA. Текстовый кандидат не имеет флага `original_delphi_compatibility_verified=true` и не заменяет два прежних evidence files.

## Что открыто

1. `TLanguage.localize`, `TMvkAdvancedCell.GetTitleByID` для оригинальных имен и тревог; `GetUnits` и FormatSettings Windows.
2. Истинная Win32 `007B2090` float rounding и отображение всех 30 типов с доказанным размером/типом/единицами; 30 маршрутов **НЕ** 30 завершённых formatter.
3. Переключение на оригинальную ANSI `WriteValues` без RAW diagnostic prefix, byte-to-byte comparison с оригинальным MVKView (как минимум два locale и boundary значения).
4. TABLE 6+24/6, TSXML/BIN source Win32 byte parity и приборный одновременный прогон МВК01 `IP → Измерить → PARAM/GetSignal/GetSpectrum → WriteValues/TABLE → Stop`.

**Статус:** `original_delphi_compatibility_verified=false`; `original_delphi_values_csv_byte_parity_verified=false`; `physical_mvk01_e2e_verified=false`. Только исследовательская ветка; `main` не менять. Реальные TX только после явного разрешения оператора. Не публиковать приватные данные.

## Путь для следующего крупного пакета

Довести 13 formatter case до подтверждённых 30 type routes с оригинальным TLanguage/Advanced/GetUnits и full FormatSettings, привязать к 0x3100 writer, провести программное Go/Python/Qt/Windows end-to-end и **только по исходному эталону** подтвердить byte-exact Win32 CSV. Не дробить на мелкие этапы.
