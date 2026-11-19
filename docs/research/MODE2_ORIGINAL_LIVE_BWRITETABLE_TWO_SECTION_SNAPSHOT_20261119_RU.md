## Итоговая приёмка пакета — 19.11.2026

**Проверенный код SHA:** `cfeeba987397fce6419b9e3da58d40f85b74526f`.
**[GitHub Actions #44493773084](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44493773084) — 5/5 SUCCESS**, все работы полностью завершены:

- Linux Go original RX/export — PASS.
- Linux Python Core — **2537 passed / 142 skipped / 30 subtests PASS**.
- Windows Core — **2782 passed / 7 skipped / 30 subtests PASS**.
- Windows Qt/изображения/масштабирование — **59 + 50 + 194 passed**.
- Windows Native QPA/font — PASS; PyInstaller автономная EXE — PASS.
- [Готовый Windows ZIP **MVKViewCompatible_Stage111_Windows_Preview** (69 479 205 байт)](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44493773084/artifacts/14514736756).

Это **программная/синтетическая приёмка исходного каркаса**, НЕ Win32 Delphi 1:1 на реальном МВК01; флаг `original_delphi_compatibility_verified=false` остаётся.

# MVKView 1.0.47 — восстановление LIVE bWriteTable, структура TABLE и независимость от WriteValues

**19 ноября 2026.** Ветка `research/stage111-mvkview-desktop-20261029`. **Последний кодовый SHA:** `cfeeba987397fce6419b9e3da58d40f85b74526f`. [GitHub Actions #44493773084](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44493773084) — зафиксировать завершённый результат отдельно, не считать PASS до конца. Предыдущий 15-mode пакет: #44489702966 — 5/5 PASS.

## Три приватных оригинальных источника — реально сверены вместе

- `/mnt/data/Projects.7z` SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`: снова распакованы и проверены на byte-size/SHA **5/5** `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`.
- `/mnt/data/mvk_idr(1).sqlite` SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`, `PRAGMA quick_check=ok`. Оригинальный обработчик `Tmvkform.bWriteTableClick 0084E020` (в `_Unit128.pas` строки 10793–11255), `bWriteValuesClick 0084E988`, `TMvkCellList.GetValueText 007CF3A8/007CF4A4`, `GetValueWithFmt 007CF3C4`, `SaveValuesToFile 007D013C/007D01E8`.
- `/mnt/data/mvkview.idp` SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`: исходные поля TMVKThread.WriteData/WriteValues/WriteValuesTime, типы и ссылки TMvkCellList. Файл остается приватным.

Ни оригинальные PAS/DFM, ни IDP/SQLite/FIR/PCAP/RAW в публичный GitHub не выгружены.

## Подтверждённый исходный алгоритм (важное исправление аудита)

`_Unit128:0084E020` — **ОДИН** UI snapshot в момент нажатия, **не** длительная запись и **не** устройство TX:
1. Из `edLibraryPath` и локального времени составляется `TABLE-yyyy-mm-dd--hh-nn-ss.csv`. `RewritText`.
2. Первая строка `sep=|`.
3. **Секция 8 АЦП:** `xParamName|` и только отмеченные `cbFileChannels[0..7]` в заголовке, `xChannelN|`; затем `ResultAdcCells` (24 по исследованному source cell bank), затем `ResultAdcBandCells` (43), каждая строка пишет `GetTitle|`, `GetValueText|` для выбранных ADC, `GetUnits`, `WriteLn`.
4. Пустая строка `WriteLn`.
5. **Отдельная секция 2 TACH:** заново `xParamName|` и отмеченные `cbFileChannels[8..9]`, затем `ResultTachCellList` (6) с `GetTitle`, `GetValueText` и `GetUnits`. **Не** общий заголовок 10 каналов!
6. Ошибка открытия/закрытия файла выводится через `errCannotWriteFile`; успех `xSnapshotSavedToFile`.

Оригинальный `bWriteValuesClick 0084E988` имеет **другую семантику**: удерживаемые маски и флаг TMVKThread.WriteValues; настоящая запись идёт внутри `_Unit125:008085A5..008085BD` на входящий `PARAM 0x3100`. Не объединять со снимком TABLE, не вызывать SetRate или прочие device-команды от кнопки TABLE.

`TMvkCellList.GetValueText` — исходный dispatcher **30 типов** ( `sub_007CE6E4`, 007CE6E4..007CE9A0). Отсутствующий `Data` возвращает `####`; отдельные numeric/date/hh:mm:ss/hex/string/special enum и `TMvkAdvancedCell.GetTitleByID`. Полное восстановление метаданных типов, форматных спецификаций, таблиц TLanguage, отображения тревог и Win32 ANSI ещё НЕ выполнено. Не заменять unknown выдуманным GetValueText.

## Что реализовано в этом связанном пакете

- `mvk_compatible/core/original_live_table_snapshot.py`: проверяет одну реально активную исходную Go-сессию с `source_live_page_status_banks_verified=True`, accepted PARAM, 8ADC+2TACH, 1 TCP, не CaptureOnly/Stop/stale/system fault/invalid frames. Требует 10 строгих Boolean выбора и хотя бы одно реально принятое значение выбранного канала.
- Только исходные RAW DWORD слова из проверенного `source_live_page_status_banks` (не пересчитанные FFT/RMS). Два раздела исходной TABLE, 24+43 ADC и 6 TACH, 2 отдельных заголовка и пустая строка. Неизвестные metadata/units помечены `—`, значения помечены `(RAW)`; оригинальные значения `GetValueText` НЕ присваиваются.
- `sep=|`, исходная временная маска `TABLE-yyyy-mm-dd--hh-nn-ss.csv`; **локальный UTF-8 BOM**, а НЕ неподтверждённый Delphi `TTextRec` ANSI/CP1251. Новая запись только `xb` (без перезаписи), размер не более 250К, локальная проверка ВСЕХ строк и байтов, SHA256, удаление частичного файла при ошибке. В отчёте нет приватного пути.
- `mvk_compatible/desktop/original_measure_controls_ui.py`: реальная `bWriteTable` при LIVE разрешается только при наличии проверенного приёмника/PARAM; открывает сохранение локального файла, перепроверяет идентификатор сеанса после диалога; `bWriteValues` остаётся прежней отдельной кнопкой-переключателем. Новый Qt property `sourceOriginalLiveTableSnapshotReceipt` удаляется при начале/конце измерения; Stop не меняет уже сохранённый CSV. Физические команды прибору не посылаются.
- `test_mode2_original_live_table_snapshot.py`: проверяет источник и оба исходных заголовка, 24+43+6 строк, выбор 10 каналов, точный исходный сепаратор/перечитанные строки, RAW/NaN/unknown, существующий файл, небезопасный путь, symlink, чужой run, устаревший status, Stage3, reconnect, source sample-rate transition, Stop.
- `test_mode2_original_live_table_snapshot_qt.py`: реальное Qt нажатие `bWriteTable`, локальный CSV, независимость от WriteValues и hardware TX, Stop, отказ от сохранения при изменении источника во время file picker. Весь пакет не требует прибора.

## Дополнительно восстановлена причина отличия оригинального WriteValues от TABLE

Вновь проверен автономный исходный обработчик `_Unit125:008066F0..00806912` (SQLite: `sub_008066F0`, страницы исходного Pascal 12693–12873), который вызывается при настоящем исходном `PARAM 0x3100` с включённым `WriteValues`:

- Начинает строку **локальным временем `hh:nn:ss.zzz`**. Это отдельный таймер от имени файла TABLE и не timestamp TCP-пакета.
- Для каждого из 8 АЦП последовательно читает **три оригинальных типа списков**: `ResultAdcSpecCellList`, `ResultAdcCellList`, `ResultAdcBandCellList`. В каждой группе использует соответствующие флаги `TMVKThread+400DE`, `+401DE`, `+402DE`, формирует `|GetValueText` только выбранных элементов.
- Отдельно обходит 2 тахоканала с флагами из `+400DC` и `+403DE` и собственным `ResultTachCellList`; завершает одну строку переходом на новую строку.
- `@LStrFromUStr` преобразует результат в ANSI-строку, затем вызывает исходный writer в `TMVKThread+40088`; формат Win32 ANSI и locale должен быть подтверждён оригинальным запуском.
- **Наш текущий Go WriteValues пока сохраняет событие/байты RAW `PARAM 0x3100`, но НЕ формирует этот исходный трёхгрупповой `GetValueText` CSV.** Нельзя подменять его новым one-shot TABLE. Следующая основная реализация — тот же Go register-image в момент настоящего `0x3100` + флаги и исходные типы/единицы, вместе с эталонным форматом каждой строки.

## Граница приёмки

**Сделано:** точная исходная структура кнопки/двух секций и безопасный локальный снимок реально полученных регистров + Qt. **НЕ сделано:** Win32 1:1 byte-exact TABLE и original `TMvkCellList.GetValueText` (строки/units/DateTime/Advanced enum), исходная CP1251/locale, точная DIR, истинные CSV/TEXT-форматы WriteValues, timing и аппаратный прием. Нельзя писать `original_delphi_compatibility_verified=true`.

Следующий **единый крупный пакет**: из оригинального `TMvkCellList.GetValueText` восстановить cell metadata/type/units/TLanguage и original `TMVKThread.WriteValues` timestamps для всех выбранных 73 result flags и 43 SPEC, довести эталонный CSV до байтов, затем сквозная аппаратная парная проверка. Программу `main` не менять, реальные SetRate/Flash/IP/Reboot/Task3/4/5 без оператора не посылать.
