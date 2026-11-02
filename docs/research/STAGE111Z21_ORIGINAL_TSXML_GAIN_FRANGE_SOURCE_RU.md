# Stage111Z.21 — ORIGINAL MVKVIEW: TSXML, BIN и путь InternalChannelGain → FRange

**Дата:** 02.11.2026. **Ветка:** research/stage111-mvkview-desktop-20261029. Приложение: автономная MVKView Compatible Windows, не Web.

## 1. Частные исходники и доказательства

Приватный архив `Projects.7z` прочитан локально через libarchive, в архиве **134 элемента, ~40,7 МБ распакованных данных**; извлечены **только три** оригинальных IDR-дампа для статического аудита:

- `_Unit125.pas` SHA256 `c1129f65f2b9d102edacc099ca22cf37bf0644edc98c7c1bb6c6c5d6a0003e86`.
- `_Unit128.pas` SHA256 `acd0459a59061b7950a18a2be03da6e67134b116560d13357de532f3204ac899`.
- `_Unit115.pas` SHA256 `c767410a02cb67b317346f303353e14b54e5756d8fe41150d3124bc3a071e2c0`.

Оригинальные PAS/IDP/EXE и бинарные данные **НЕ размещались в GitHub**. Это source static IDR evidence, **не динамическая трасса реального оригинального запущенного процесса**.

## 2. Подтверждённая структура ORIGINAL TSXML

Исходный writer `_Unit125.pas:00806A8C..00807111` формирует sidecar `имя.bin.tsxml`:

| Адрес | Подтверждённое действие |
|---|---|
| 00806B61 | XML declaration `windows-1251` |
| 00806D87..00806DA7 | `FrequencyPerChannel` из `[TMVKThread+0x400D0]` |
| 00806DD7..00806DF7 | `DataFileName` вида `.\\имя.bin` |
| 00806E41 | `Channel Index="0"` |
| 00806EB0..00806ECE | `ChannelNumber=esi+1` |
| 00806EF9..00806F24 | `ChannelFrequency` |
| 00806F4E..00806F7D | при индексах >=8 `Units=Count`, `RealDataType=Byte` |
| 00806F84..00806FE3 | при индексах <8 `Units` из канальных настроек, `RealDataType=Single` |
| 00806FE8..00807031 | **`DataLength` берётся из TFileStream.Size, т.е. БАЙТЫ** |
| 0080703B | `DataOffset=0` в штатном writer |
| 00807055..008070A6 | `InternalChannelGain` в канальной записи |

В оригинальном reader `_Unit128.pas:008460F8..00846266` отдельно узнаются `ChannelFrequency`/Units/`RealDataType`/`InternalChannelGain`; в `008465C1..008465E1` для `Single` число отсчётов = BIN bytes / 4, для `Byte` число отсчётов = bytes. Исходный reader допускает fallback без sidecar, но только через запрос параметров; наш автономный DirectBinSession **намеренно отказывается угадывать** без декларации типа.

## 3. Существенное новое звено K_Modbus ↔ TSXML gain ↔ FRange

- Оригинальный TSXML writer: `_Unit125.pas:00806964..00806985` при индексах ADC0..7 вызывает `TMvkCellList.GetFloatByAddr(0x0E)` для канальной таблицы. `0080698F..008069A5` заменяет нулевое/неупорядоченное значение на 1.0.
- Ранее независимый protocol audit `STAGE50_FC03_FRANGE_BIN_RU.md` определил Modbus канал `0x0100+0x100*N`, коэффициент `K_Modbus` по смещению **0x0E**. Это **source-based мост по одному смещению и канальной таблице**. Но необходимо отличать запись содержимого регистра, текущий runtime FRange и физическую размерность исходного BIN — они не всегда тождественны.
- В original archive reader `_Unit128.pas:0084622E..0084623F` `InternalChannelGain` разбирается `StrToFloat` → **Single**.
- На ветви положительного коэффициента `0084651F..00846522` ставит `ViewedFileIsNormalized=0`; при fallback `00846513..00846516` ставит 1. Missing/nonpositive float влечёт чтение `DefaultConfig.txt`/fallback, численный результат конфигурации не известен; для Byte fallback=1.
- `0084655B..0084655E` записывает обработанный Single gain непосредственно в `TMvkChannelStorage.FRange` (offset +4), а `_Unit115.pas:007D23B7..007D23E5` умножает float-buffer на FRange **только при ApplyRange**.
- Путь original writer `TmpStream` и алиасинг входного буфера при сохранении BIN по-прежнему **не аттестованы**. Потому в Qt нет автоматического повторного умножения на коэффициент. Это предотвращает double calibration.

Таким образом: источник TSXML gain в оригинале стал значительно лучше понятен, но **побайтового доказательства эквивалентности исходного BIN и внутреннего float-ring нет**.

## 4. Что реализовано в нашем исходном коде

- `core/original_tsxml_contract.py`: строгое чтение оригинального CP1251 XML и ранней минимальной схемы; требует `MainRoot`, один `Channel`, `Single`/декларированный `Byte`, корректные DataLength bytes/DataOffset/Frequency. Проверяет необязательные, но оригинальные `ChannelsQuantity=1`, `FrequencyPerChannel`, `DataFileName` (только имя текущего BIN, без выхода в другие каталоги), `ChannelNumber`, `Units`, `InternalChannelGain` Float32, DTD/ENTITY, дубликаты ключей. Не выполняет сеть/запись/подмену калибровки.
- `core/direct_bin_session.py`: сохраняет реальное `ChannelNumber` из TSXML даже при нестандартном имени исходного BIN, а для стандартных `MVK...-ADC4-...` требует совпадение с индексом. Признаёт `Byte` как original count type, **НЕ** читает его как Float32 acceleration и не рисует ложный FFT. Строго проверяет размеры, finite Float32, SHA BIN+TSXML.
- `samples().audit`, `verify()` возвращают `declared_internal_channel_gain_single`, `original_loader_f_range_single_candidate`, source loader branch и false `metadata_gain_was_applied_to_bin_samples` / false `physical_units_verified`; сигнал остаётся тем же массивом Float32.
- В Qt Research Inspector `researchOriginalTsxmlGain` отображается кандидатный FRange выбранного АЦП и запрет повторного умножения. **`spec_f_range` не меняется автоматически**, он остаётся параметром отдельного исследования.
- Существующий Native R6.1 ZIP/export DSP, copy, source FFT не менялись.

**Отдельно:** CLI `python -m mvk_compatible.offline_source_audit_cli inspect путь_к_BIN.bin` позволяет проверить и **Byte** sidecar как метаданные без ложного ускорения. Результат в JSON без имени/пути и без исходных сэмплов; операции только локальные.

## 5. QA и границы

Синтетические тесты `test_stage111z21_original_tsxml.py` включают original writer CP1251 / ChannelNumber / DataFileName / Gain / no double scaling / Byte metadata only / NaN/Inf / mismatch / fallback / short synthetic schema / Native ZIP unaffected. Qt test проверяет Research Inspector и FRange=1 по умолчанию, несмотря на объявленный другой gain.

**Реальная оригинальная пара BIN+TSXML к одному из прежних captures в текущем файловом пространстве не смонтирована** (сейчас есть приватный источник IDR и реальные x32dbg snapshots before/after FFT); нет оснований объявлять полную аттестацию оригинального архивного BIN по всем режимам. Stage107 реальные reconstructed BIN/TSXML отдельно проверялись ранее по RAW, но оригинальному writer той же записи байтовый parity ещё не заявлен.

## 6. Следующий основной шаг

Source-specific parser готов. Следующий этап — создать строго воспроизводимый local golden для реальной парной оригинальной BIN+TSXML (при наличии у оператора), воссоздать исходный `ViewedFileIsNormalized/ProcessBufferChunk` → GetSignal → GetSpectrum с выбранными каналом, временем, N/Fs/FRange, сверить FFT bitwise и физи­ческую калибровку. `Byte` считать отдельным типом count, не акселерометрическим спектром.

Подтверждение только Linux/Windows GitHub Actions по **конкретному** source SHA и provenance; не объявлять SUCCESS/EXE, пока workflow и Artifact реально не завершены.
