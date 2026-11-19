# MVKView 1.0.47 — оригинальные GetValueText (30 типов), WriteValues и 36 флагов

**19 ноября 2026 · Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. **Код:** `dc3d1c12d2d77c83f420084643a30768018d2f42`. **Текущая автоматическая приёмка:** [GitHub Actions #44500610063](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44500610063) — точный итог проверять по GitHub, не объявлять PASS до завершения пяти заданий.

## Подтверждение тремя приватными источниками

- `/mnt/data/Projects.7z` — `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`; повторная сверка **5/5** bytes и SHA с базой данных.
- `/mnt/data/mvk_idr(1).sqlite` — `PRAGMA quick_check=ok`, исходные addresses/callgraphs.
- `/mnt/data/mvkview.idp` — исходные типы/поля и связи `TMvkCellList`/`TMVKThread`.

Оригинальные файлы, FIR, приватные PCAP, сырые приборные данные **не включены в GitHub**. Физического подключения и команд оборудованию не выполнялось.

## Главная поправка к ранее сохранённым аудитам

**РАНЕЕ: 10 каналов + 43 SPEC + 73 VALUES, TABLE 24+43 / 6. Это НЕ ТОЧНАЯ ОРИГИНАЛЬНАЯ СХЕМА.**

**ПО ОРИГИНАЛУ: 10 каналов (8 АЦП + 2 TACH) + 43 SPEC + 36 VALUES, где VALUES = 6 общих ADC + 24 полосовых ADC + 6 TACH.**

Исходные конструкторы: `_Unit125:00804A30` создаёт 6 `ResultAdcCellList`; `00804DEC` — 24 `ResultAdcBandCellList` (и параллельные пиковые); `00805040` — 43 `ResultAdcSpecCellList`; `008053B8` — 6 `ResultTachCellList`. По `_Unit128:008443CF..00844454` подтверждены владельцы списков, `bWriteValuesClick 0084E988` копирует соответствующие **43+6+24+6** масок. Предшествующие технические заметки, называвшие 73 «оригинальным числом», считать **устаревшими** для LIVE Mode2. 73 остаётся только старым внутренним размером `OriginalPageFileSelection` для архивного экспорта и JSON frame-mark.

**Оригинальный TABLE**: первая секция `ResultAdcCellList` (6) + `ResultAdcBandCellList` (24), затем пустая строка, вторая секция `ResultTachCellList` (6). Набор 43 SPEC **не** записывается в кнопку TABLE. Восстановленный `original_live_table_snapshot.py` приведён к **6+24 / 6**, сохраняет `sep=|`, два заголовка и отдельный RAW-статус точности.

## Восстановленный оригинальный источник GetValueText

`_Unit115:007CE6E4` диспетчеризует типы `0..29` по исходной таблице переходов в 13 уникальных formatter-case. `GetValueText 007CF4A4` возвращает `####` **только при доказанном nil Data pointer**; отсутствие половины сетевого DWORD даёт `UNKNOWN`, а не «нулевой прибор».

Новый `mvk_compatible/core/original_get_value_text_source.py` хранит таблицу всех **30 исходных маршрутов** и branch addresses, даёт source candidate только для подтверждённого Float32, остальные оставляет типизированными RAW. Нет необоснованных значений для даты, времени, enum, тревог, Advanced битовых полей. Приватные `TLanguage`, локаль, форматные спецификации, Win32 округление **ещё не восстановлены 1:1**.

## Восстановленный WriteValues при PARAM 0x3100

В `source_live_values.go` прежние исходные `SOURCE_Wxx_VALUES_3100_RECEIVED.jsonl` не изменяются: они сохраняют точные принятые байты `PARAM 0x3100`, word count, SHA и RX sequence. По отдельному исходному файлу `source_values_tick_raw_layout.go` **в том же обработчике Go и том же TCP** записывается `SOURCE_Wxx_VALUES_3100_RAW_LAYOUT.csv` как независимый source-shaped RAW-кандидат:

1. Местное время `hh:mm:ss.zzz` на момент **фактически принятого** `PARAM 0x3100`.
2. Для отмеченных ADC1..ADC8 — строго в оригинальном порядке: **43 SPEC** (base+0x02), **6 RESULT** (три Advanced-поля одного `base+0x120`, плюс `base+0x00,+0x5E,+0x5C`) и **24 BAND** (base+0x60). Каждый список фильтруется собственным набором операторских флагов.
3. Для отмеченных TACH1..TACH2 — 6 полей. У `+0xFE` требуется свежесть обоих WORD **в текущем PARAM**, иначе `UNKNOWN`, даже если полный register-image содержит старое значение.
4. Нет выбранных original-каналов/ячеек, FreezeUpdate, source error или malformed `0x3100` — нет легитимной новой строки.
5. У каждой строки есть SHA256 и строгий список source address, word LE, тип-кандидат, список отсутствующих значений и три **false** флага паритета оригинальному Delphi.

`original_source_values_tick_acceptance.py` независимо и потоково сверяет JSONL и companion RAW-layout CSV: source tick/frame sequence, SHA исходного PARAM, исходный порядок полей, точные адреса/размер, LF/CRLF и SHA всех строк; после ошибки/ссылки/перестановки fail closed.

## Один оригинальный LIVE PageFile при старом формате транспорта

- Qt LIVE теперь показывает ровно **10 / 43 / 36** переключателей, соответствующих исходному Delphi (6 RESULT, 24 BAND, 6 TACH).
- В памяти `OriginalLiveFilePlan.values` по-прежнему **73 Boolean** только потому, что Go frame-mark/saved offline decoder ещё ожидает свой старый контракт. Значения [36..72] всегда `False` и недоступны в Qt; frame-mark только из 36 оригинальных селекторов. `anySourceValuesSelected` в Go проверяет только original group flags и реальные выбранные каналы.
- При переходе из LIVE в архив оригинальные 6 Advanced и 6 TACH не подменяются 24 offline RMS: только source 24 BAND RMS могут связаться с 24 реально подтверждёнными offline VALUE; по отсутствующим типам возвращается `unsupported_original_advanced_result_indices`, фальшивые данные не генерируются.
- Полная замена wire/архивного `VALUE_COUNT=73` на 36 в исследовательском форм-факторе пока **не выполнена**; нельзя без перепроверки старых архивных декодеров.

## Реальные ограничения до полного соответствия оригиналу

- Нет 1:1 исходного текстового formatter по всем 30 типам (`GetValueText`, `GetUnits`, `TLanguage`, Advanced и статусы тревог).
- RAW-layout не является оригинальным ANSI `TTextRec`/CP1251-файлом. Нет доказанной 1:1 точности времени, контрольных полей и исходных единиц. В CSV текст явно помечен `RAW_`.
- Исходный original TABLE/WriteValues byte-parity, BIN/TSXML, x87 FIR/FFT и поведение курсоров требуют парного оригинального эталона. Аппаратная сквозная проверка МВК01 отсутствует; `original_delphi_compatibility_verified=false`.
- Не менять `main`; не копировать PAS/DFM/IDP/SQLite/FIR/PCAP; не отправлять Flash/IP/Reboot/Task3/4/5 и не выполнять реальные команды без оператора.

**Следующий единый пакет:** source metadata/formatter table для всех 30 типов + оригинальный Unicode→ANSI путь и timestamps, затем byte-exact сравнение WriteValues/TABLE и настоящие Win32 x87 и приборные тесты.
