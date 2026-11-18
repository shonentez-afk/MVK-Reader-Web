# MVKView / MVK Reader Web — единая приёмка после «Измерить»

**Дата:** 18.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Цель:** один крупный, связанный цикл, а не дробление на независимые Stage с отчётами без работы приложения.

## Оригинальные источники — использованы только совместно и локально

1. `/mnt/data/mvkview.idp`, IDR project v3 (header `IDR proj v.3`), SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`.
2. `/mnt/data/Projects.7z`, SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`; пять извлечённых локально исходных `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm` соответствуют полным размеру и SHA из SQLite **5/5**.
3. `/mnt/data/mvk_idr(1).sqlite`, SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`, `PRAGMA quick_check = ok`, функция `TMVKThread.Execute 00807A98`, вызовы `TMvkCellList.GetValueText 007CF4A4`, `sub_00806A8C` (TSXML), `sub_00809414` (стадии файлов), `bWriteAdcClick 0084E914` и `bWriteValuesClick 0084E988`.

Приватные Pascal/DFM, IDP, SQLite, EXE и реальные пользовательские RAW/PCAP/BIN **не попадали** в публичный GitHub.

## Сквозной сценарий, затронутый единым пакетом

`IP → нажать Измерить (Mode2) → показать измерительные вкладки независимо от успешности соединения → соединение Task2 → PARAM/Status0 → исходная FIFO SetRate (только после отдельно разрешённого TX) → приём кадров 8 ADC + 2 TACH + PARAM/AUX4700 + ACK/DENIED → выбор MvkSampleRate и FreezeUpdate → запись WriteData + WriteValues → остановить → закрыть открытые файлы → проверить RAW/маркеры/байты → локальный экспорт BIN/TSXML/VALUES → Qt статус`.

В нижеследующей таблице **не** смешивать существование кода, прохождение синтетических тестов и аппаратную 1:1 приёмку.

| Составная часть | Код и исходное правило | Проверка |
|---|---|---|
| Исходящий SetRate, порядок FIFO, ACK, DENIED и реконнект | Предыдущие FO/FP; отправка по тому же Task2 TCP, не более одной команды перед чтением; отдельное согласие для физического TX | Loopback TCP и предыдущие CI |
| Полный приём | Непрерывный `incoming.raw`, 10 каналов, Unknown type с корректной длиной пропускается, повреждённый пакет отклоняется; внеполосные регистры не маскируют ADC | Go Native RX |
| `WriteData` | [Go live writer](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_write_data.go): Stage0→1 только первый допущенный ADC1, затем выбранные ADC/TACH; пакет принимается только при `received Fs==MvkSampleRate && !FreezeUpdate` (исходный `0080822F..008082DE`) | [Source gate tests](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_write_data_test.go); SHA/байты проверены отдельно |
| `WriteValues` | [Новый Go live writer](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_values.go): стадии открытия/закрытия по `bWriteValues`, реальный PARAM-дескриптор **0x3100**, точные байты и маски, без фиктивных строк из AUX4700; не выдавать JSONL события за исходный Delphi CSV | [Native Go tests](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_values_test.go) |
| Одна TCP-сессия, оба writer-а, остановка | [Полный локальный TCP-тест](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/mode2_full_measurement_chain_test.go): PARAM, исходная 36-байтная SetRate, ADC/TACH, запись обеих кнопок, clean stop, RAW и бинарные файлы | Один интеграционный тест. Только `127.0.0.1`, не настоящий MVK01 |
| Независимая байтовая проверка | [Core Go WriteData proof](../../mvk_compatible/core/original_write_data_live_gate.py) и [Core Go WriteValues proof](../../mvk_compatible/core/original_live_values_proof.py) независимо перечитывают RAW, проверяют каждый marker, `Fs`, Freeze, Stage, SHA, маски, Source Tick и каждый байт созданного файла | [Go writer+Core E2E](../../mvk_compatible/tests/test_stage111z31fs_original_live_writer_e2e.py) и [VALUES E2E](../../mvk_compatible/tests/test_mode2_live_values_full_chain.py), включая подмену данных при пересчитанных SHA |
| Исходный формат TSXML | [Source PageFile/TSXML contract](../../mvk_compatible/core/original_mode2_source_files.py): символы исходного имени по `007B1FA4`, filename timestamp `yyyy-mm-dd--hh-nn-ss`, TSXML `00806A8C`: CP1251, `MainRoot`, DateTime, Culture, From/To (мс), ChannelsQuantity, FrequencyPerChannel, DataFileName `.\\...`, Channel, `Single` для ADC / `Byte` для TACH, `Count` для TACH, DataLength **байты**, DataOffset, InternalChannelGain | [TSXML contract test](../../mvk_compatible/tests/test_mode2_full_recording_file_contract.py). Sidecar помечен как частично восстановленный, не как точный Delphi |
| Итоговый общий экспорт | [Core writer](../../mvk_compatible/core/original_live_write_stages.py): `WriteData` с настоящим Go live gate, отдельно сырые FR-срезы и Native calibrated, настоящие 0x3100-события, совместимые структурные TSXML, SHA и provenance, локальные новые файлы, никакой перезаписи исходного RAW | Интеграционные Python тесты и Windows Core |
| GUI и статус | [Qt main window](../../mvk_compatible/desktop/main_window.py) отображает для той же записи число живых gated ADC/TACH, исходных 0x3100-событий и созданных TSXML. Не обещает побайтную идентичность файлов Delphi | Windows Core/Qt + Windows native QPA 100% и 150% |

## Файлы и границы достоверности

- `incoming.raw` — полный входящий поток, SHA256. Не смешивать отдельные TCP-сессии.
- `SOURCE_W##_ADC/TACH#_LIVE_RX_UNSCALED.bin` — настоящие выбранные байты оригинального sample packet при проверенном Go live gate. **Не** значит, что исходный Delphi `.bin` уже совпал до последнего байта.
- `SOURCE_W##_VALUES_3100_RECEIVED.jsonl` — по одному исходному PARAM 0x3100 событию только когда original WriteValues открыт; snapshot FRange/числа не изобретаются.
- `SOURCE_LIVE_WRITEDATA_NATIVE_AUDIT.json`, `SOURCE_LIVE_VALUES_NATIVE_AUDIT.json`, `SOURCE_FRAME_MARKS_NATIVE.json` — отдельные SHA-аудиты, привязанные к этому `summary.json` и RAW.
- `SOURCE_W##...bin.tsxml` — структура исходного XML с точным порядком элементов и длиной в **байтах**. Одновременно проверяется имя существующего BIN. Один TSXML для смешанных Fs запрещён. **Не** выдавать вычисленную из UTC дату конца сеанса, provisional labels, пустой units или unity gain вместо реальных оригинальных PageFile/FRange/Windows DateTime за точный источник.
- `VALUES##_SOURCE_3100_EVENTS.csv` и `VALUES##_NATIVE_VERIFIED_SELECTED.csv` — отдельно истинный trigger RAW и отдельно реконструированные из предшествующего AUX числа. **Не** оригинальный `TMvkCellList.GetValueText` CSV, пока не реконструированы все branch variants, локаль/ANSI и advanced titles.
- В функции `TMvkCellList.GetValueText 007CF4A4` обнаружен особый путь advanced-cell `TMvkAdvancedCell.GetTitleByID` и общий форматтер `007CE6E4`. Поэтому нельзя просто форматировать все числа как `float` и объявлять совпадение Delphi.

## Обязательное правило итоговой приёмки

Один полный CI для **последнего кодового SHA**: Go RX/экспорт с единым loopback-сценарием, Linux Python Core, Windows Core/Qt и Native QPA, затем автономный Windows EXE. В CI нет подключённого МВК01. Отменённые из-за новых коммитов предыдущие runs **не** засчитывать. На 18 ноября запуск [#44246633525](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44246633525) — проверка кода; при новых кодовых коммитах использовать новый run.

## Что остаётся частью этой же общей задачи, а не новой россыпью мелких задач

- Побайтно восстановить `GetValueText` (включая 007CE6E4 и advanced titles), реальную кодировку и заголовки `VALUES`; это не может быть достоверно заменено float-таблицей.
- Привязать оригинальные `edFilePrefix`, `edFileMvkName`, `cbFileMvkName`, `cbFileWriteXml`, `cbFileFolderPrefix` к Go записи и отразить точные имя/папку и source DateTime; сейчас recovered TSXML schema не доказывает runtime fields 1:1.
- Проверить на реальном MVK01 **одну** полноценную пару оригинального Delphi и новой программы, по единому сценарию: Task2 Measure, SetRate, Freeze, два writer-а, ACK/DENIED/reconnect, stop, BIN/TSXML/VALUES, численные спектры и UI. Без этого `original_delphi_compatibility_verified=false`.

**Дальнейшую работу вести одним сквозным приёмочным пакетом, без самодостаточных «микро-Stage» по одной функции и без изменения `main`.**
