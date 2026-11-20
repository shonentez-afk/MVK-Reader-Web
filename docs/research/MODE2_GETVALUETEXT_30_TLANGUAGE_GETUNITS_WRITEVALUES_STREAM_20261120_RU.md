# MVKView 1.0.47: GetValueText 30 типов → TLanguage/Advanced/GetUnits → потоковый WriteValues

**20 ноября 2026.** Ветка `research/stage111-mvkview-desktop-20261029`. Код пакета: [6978146](https://github.com/shonentez-afk/MVK-Reader-Web/commit/6978146e4f558709b96f42e527430b502ecc4fd8), [c37f31a](https://github.com/shonentez-afk/MVK-Reader-Web/commit/c37f31ad0f1c3e0b8cb4fefa1af54bf774acdf28), [0d0150a](https://github.com/shonentez-afk/MVK-Reader-Web/commit/0d0150aac7c7fe6dbc16cab723f265b797281e25). Последний code CI: [#44672076176](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44672076176); точный статус проверять по Actions, не называть 5/5, пока все пять jobs не завершены.

## Приватная верификация (НЕ публиковать эти файлы)

* `/mnt/data/Projects.7z` — пять оригинальных декомпиляций/форм: `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`. В этом сеансе извлечены локально с libarchive, все пять совпали по SHA-256 и байтовой длине с `source_files` в SQLite.
* `/mnt/data/mvk_idr(1).sqlite` — `PRAGMA quick_check=ok`, таблицы адресов/вызовов/исходных мест.
* `/mnt/data/mvkview.idp` — размер 42 094 126 байт, **прямо повторно проверены SHA-256 3/3 таблиц по адресу VA−0x400ED8**: 30 форматных символов (`0x8D2AD8`), 30 размеров ячеек (`0x8D2B18`), 43 частоты (`0x8D2F90`), точное совпадение с SHA в `original_config_idp_tables.py`. Все типы и длины нового форматтера согласованы с IDP. Полную независимую проверку всего IDP-файла/всех типов этим не подменять.

## GetValueText: полный source-dispatch и типизированные ветви

Действительный исходный `_Unit115:007CE6E4` имеет 30 типов `0..29`, **13 используемых formatter branches**:

| Типы | Оригинальный formatter | Отдельная реализация |
|---|---|---|
| 0 | Float32 `_Unit114:007B2090`, `FormatSpec=4` из `007CF3A8` | Float32, количество десятичных разрядов через повторные Float32 ×10, trim нулей; Win32 округление пока CANDIDATE |
| 1 | signed Int32 | Int32 десятичный |
| 2 | unsigned UInt32 | Cardinal десятичный |
| 3 | timestamp seconds → Delphi TDateTime | Только с явным Windows timezone bias, иначе UNKNOWN |
| 4 | 16 байт → сплошной HEX | HEX uppercase |
| 5 | DWORD → индексы установленных битов или `---` | Источник `007B2428` |
| 6, 7, 15 | IPv4 из DWORD | MSB-first dotted decimal |
| 8, 9, 11, 13, 14 | ANSI строка по source-width до NUL | С явной ACP для не-ASCII, без догадок об ANSI-кодировке |
| 10, 29 | `0xXXXXXXXX` | Для типа 10 с Advanced дополнительно `GetTitleByID` |
| 12 | `hh:mm:ss` из секунд | целочисленное деление |
| 16–23 | 4–32 бит LSB-first, пробел через четыре | `007B2390` |
| 24–27 | HEX 1–4 байт с пробелами | `007B2224` |
| 28 | `0xXXXX` из младшего WORD | `007B28F8` |

**Ограничение:** source-код и маршрутизация восстановлены; это ещё не доказательство, что у 30/30 получены побайтово идентичные строки, особенно Float32, даты, локаль и ANSI. Все паритетные флаги остаются **false**. `####` выводится только при доказанном `TMvkCellList.Data=nil`, а не при неполном сетевом регистре.

## Advanced и TLanguage

* `_Unit115:007CF4A4` для type=10 + существующий `TMvkAdvancedCell` извлекает ID из исходных битов, затем `007D0808 GetTitleByID` ищет метку. По `_Unit125:00804A30` поля ADC `+0x120`:
  * `ResultOverload`: bits 1, start 0, ids (0,1);
  * `ResultBuffers`: bits 3, start 4, ids (0,1,3,7);
  * `ResultSensorState`: bits 2, start 10, ids (0,1,2,3).
* Общий `TMvkAdvancedCell.GetTitleByID` теперь реализован и для всех source selector-списков с подтверждённой метаинформацией Bits/BitStart. Для `UseCompositeTitle` (в частности, AlarmAlert) исходный алгоритм выбирает все записи с условием `(entry_id & selected_id) == entry_id`, соединяет заголовки через `; `, либо возвращает `---`. Признак составного заголовка и битовые поля должны быть получены из исходного описания конкретной ячейки; произвольные значения не угадываются. Нет аутентичной TLanguage — метки остаются UNRESOLVED.
* Если ID отсутствует в source list, `GetTitleByID` доказанно даёт **`(0xXXXXXXXX)`**; если он существует, но перевод ещё не восстановлен, используется `UNRESOLVED_ADVANCED_ID_N` (не выдуманная локализованная фраза).
* `_Unit125:0080250C` конструирует динамические ключи `Prefix + "Cell" + ID`. Прежний `original_language_resource.py` знал лишь 191 статический ключ; теперь локальный импорт `TLanguage` распознаёт также исходные динамические ключи (`OverloadCell1`, `BuffersCell7`, `SensorStateCell3` и др.), учитывая приоритет последнего значения.
* Ресурс `Localization`/`ExtLocalization`/`WindowManLocalization` оригинального EXE **не извлечён**, поэтому произвольный локально поставленный UTF-8 JSON не считается оригинальным до сверки с настоящим RCDATA.

## GetUnits и PageFile TABLE

`_Unit115:007CF2FC` читает units из `Cell+0x1C`, без вызова TLanguage. По настоящим литералам конструкторов `_Unit125` для source 10 каналов:

* `SPEC43`: `м/с2`;
* `RESULT6`: `""/""/""/"В"/"м/с2"/""`;
* `BAND24`: `м/с2`, `мм/с`, `мкм` (повторяется 8 групп);
* `TACH6`: `Гц`, `Гц`, затем четыре пустых единицы.

Локальный `bWriteTable` теперь включает source-confirmed единицы, сохраняя исходные **две секции TABLE: 6 Result +24 Band / пустая строка /6 Tach**, `sep=|`, безопасный новый локальный файл, readback и SHA. Текст VALUES в TABLE всё ещё помечен RAW до Delphi-parity.

## WriteValues: текущая сквозная реализация

Go получает один реальный `PARAM 0x3100` на одном TCP, с Freeze/Stop/TACH freshness. Рядом сохраняются **три связанных** потока:

1. `SOURCE_Wxx_VALUES_3100_RECEIVED.jsonl`: оригинальные байты/адрес `0x3100`, порядок и SHA без изменений.
2. `SOURCE_Wxx_VALUES_3100_RAW_LAYOUT.csv`: source-order RAW`hh:mm:ss.zzz|RAW...\r\n` для независимой перепроверки.
3. `SOURCE_Wxx_VALUES_3100_TEXT_CANDIDATE.csv`: **без диагностических RAW-гексов**, source-order `hh:mm:ss.zzz|<float>|<cardinal>|<Advanced candidate>...\r\n`. Float32 через источник `007B2090`, Advanced по реальным битам, неизвестное — UNKNOWN.

Операции на том же источнике, дополнительных команд на МВК01 нет. JSONL теперь хранит `source_cell_type`, `source_advanced_selected_id`, `source_text_candidate_formatter_version`, `source_text_candidate_line_sha256`; итоговый audit содержит имя, число строк, байты и SHA текстового CSV. Новый **независимый Python-компаратор** `original_source_values_text_candidate_acceptance.py` пересчитывает 30-type source formatters для фактически используемых в WriteValues типов 0/2/10 и проверяет все три потока на каждом PARAM, а также метаданные/битовые поля/порядок/хеши. Все sample и отрицательные тесты синтетические, аппаратных данных нет.

## Что не завершено

1. Оригинальная точная локализация `TLanguage`, `TMvkAdvancedCell.GetTitleByID`, `GetUnits` для всех произвольных пользовательских ячеек вне source Result/Spec/Band/Tach.
2. Побайтовый паритет исходного Delphi `FormatFloat` при Win32 x87, `FormatSettings` (decimal separator, rounding), timezone и `@LStrFromUStr` → системная ANSI code page. Текущая текстовая запись **TEXT_CANDIDATE**, а не сертифицированный original-values CSV.
3. Парный оригинальный вывод `TABLE / VALUES / TSXML / BIN` и аппаратный MVK01 с оригинальным 1.0.47 одновременно.
4. Крупная приёмка `IP → Измерить → Task2 → PARAM/GetSignal/GetSpectrum → запись → Stop` на реальном приборе ещё OPEN.

**Запрещено объявлять** `original_delphi_compatibility_verified=true` или `physical_mvk01_e2e_verified=true` до независимой сверки. Не изменять `main`, не публиковать `Projects.7z / mvkview.idp / sqlite / private FIR / PCAP / live RAW`, не слать TX на прибор без согласия оператора.

## Дальше одним крупным пакетом

Извлечь аутентичный оригинальный RCDATA локализации из operator-owned EXE, провести Win32 byte-parity целиком по всем 30 типам/коллизиям и всем условиям (locale/timestamps/Unicode→ANSI), затем включить проверенный formatter в основной `WriteValues`. Верификация с реальным MVK01 обязательна до заявления полного MVKView-паритета.
