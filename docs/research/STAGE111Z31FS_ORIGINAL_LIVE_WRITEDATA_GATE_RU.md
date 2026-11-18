# Stage111Z31FS — восстановлена оригинальная запись WriteData непосредственно в приёмнике

**Дата:** 18 ноября 2026 года. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Принцип:** исходная логика Go + независимая проверка Python + отображение в Qt; приватные оригиналы не публикуются.

## Три совместно проверенных оригинальных источника

Использованы именно локальные архив и индекс пользователя, а не пересказ предыдущего этапа:

- `/mnt/data/mvkview.idp` — IDR v3, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`.
- `/mnt/data/Projects.7z` — исходный декомпилированный Pascal/DFM; через локальный libarchive извлечены `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`. **5/5 совпадают по длине и SHA256 с таблицей `source_files`**.
- `/mnt/data/mvk_idr(1).sqlite` — `PRAGMA quick_check=ok`, таблицы `functions`, `calls`, `source_files` и адреса `TMVKThread.Execute 00807A98`, `TMVKThread.SetRate 00809400`, `TMvkChannelStorage.ProcessBufferChunk 007D2398`, `bFreezeUpdateClick 0084DEA4`, `bWriteAdcClick 0084E914`.

### Точная последовательность из оригинального Execute

1. `_Unit128.pas:0084E922..0084E975`: кнопка записи фиксирует `WriteDataTime`, копирует **10** исходных масок `cbFileChannels` и переключает `WriteData`. Флаг относится к локальному FileStream, а не к обязательной команде на прибор.
2. `_Unit125.pas:00807F6A`: `sub_00809414(False)` на каждой итерации живого потока обслуживает стадии открытия/закрытия ещё **до** следующего `ReadUInt32`.
3. `_Unit125.pas:008081EA..00808229`: принимаются истинные переменные по размеру сетевые `TmpStream.FMemory` блоки ADC/TACH; TCP/RAW полностью читается независимо от видимого графика.
4. `0080822F..0080824B`: допуск буфера к исходному хранилищу и писателю **только** если `received Fs==MvkSampleRate` и `FreezeUpdate==false`. Для TACH сначала используется исходная байтовая ветка `00808251..00808274`; все десять каналов проходят общий допуск.
5. `00808279..0080828C`: вызов `TMvkChannelStorage.ProcessBufferChunk`.
6. `00808291..008082A3`: стадия `WriteDataStage==0` становится **1 исключительно после первого допущенного ADC1** (канал 0), а не просто после нажатия кнопки или первого ADC2/TACH.
7. `008082AA..008082DE`: при стадии 1 и открытом файле выбранного канала происходит **прямая запись сырых байтов** `TmpStream.FMemory`. Gain/FIR/FFT не применяются повторно.
8. `00809414..00809811`: стадия открытия/закрытия FileStream (2→0→1→2), `008089A8` завершает активных писателей даже при остановке потока.

**Различие с Stage111Z31FR:** FR после измерения копировал доказанные RAW-пакеты по выбранным интервалам, но не мог знать при каждом пакете точное состояние `MvkSampleRate`, `FreezeUpdate` и ожидание ADC1. Теперь эти три условия фиксируются **непосредственно в приёмнике Go** и отдельно подтверждаются Python.

## Изменения production

- [`source_live_write_data.go`](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_write_data.go): новый локальный source writer при `-frame-marks`. В момент реального `ProcessChunk` запускает 10-канальную FileStream-модель, применяет Go original RX gate и только для выбранных каналов сохраняет **неизменённые ADC/TACH payload**. На первый допущенный ADC1 переходит Stage0→Stage1. Не пишет пакеты до ADC1, при неверной Fs или во время FreezeUpdate. На штатный stop закрывает файловые дескрипторы, а при обрыве маркирует запись `INTERRUPTED`. Не пишет команд в прибор.
- [Go `monitor.go`](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/monitor.go) и [`main.go`](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/main.go): связывают исходные операторские NEXT-FRAME marks с открытием/закрытием файлов **до** обработки пакета и вызывают запись после исходного receive-gate. RAW всегда остаётся полной независимой записью.
- Go формирует `SOURCE_W##_ADC#_LIVE_RX_UNSCALED.bin`, `SOURCE_W##_TACH#_LIVE_RX_UNSCALED.bin`, пакетный журнал `SOURCE_LIVE_WRITEDATA_PACKET_GATE.jsonl` с фактическими Fs/Freeze/Stage/CRC-подобным SHA каждого payload, и `SOURCE_LIVE_WRITEDATA_NATIVE_AUDIT.json`. SHA256 всего аудита записывается в `summary.json`; для выбранных файлов фиксируются SHA, байты и число пакетов. Исходный RAW также связан SHA256.
- [`original_write_data_live_gate.py`](../../mvk_compatible/core/original_write_data_live_gate.py): **независимо от Go** пересчитывает каждый RAW-фрейм, контролирует все десять счётчиков, покадровые приёмные позиции, фактическую Fs и Freeze, переход Stage0→1 только на ADC1, выброс запрещённых кадров, последовательность и байты каждого созданного файла. Подмена одного бита, пропущенный пакет или подложный stage при пересчитанных SHA — **жёсткий отказ**.
- [`original_live_write_stages.py`](../../mvk_compatible/core/original_live_write_stages.py): принимает в архивный локальный экспорт только прошедшие эту проверку Go-файлы, отдельно от FR ungated RAW-срезов и Native calibrated .f32. Существующая запись VALUES по настоящему PARAM `0x3100` и исходные frame marks не меняются.
- [Qt `main_window.py`](../../mvk_compatible/desktop/main_window.py): показывает число проверенных файлов с **истинным live Fs/Freeze/первым ADC1**. Не смешивает их с ungated FR-slices и не объявляет исходную совместимость .bin/.tsxml без аппаратного сравнения.

## Тесты и доказательства

- [Go source receiver tests](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_write_data_test.go): локальные пакеты ADC2→неверная частота ADC1→заморозка ADC1→первый допущенный ADC1→TACH→ADC2→SetRate→Freeze→unfreeze→stop, проверка исходных байтов и каждой стадии; отключение без повторного клика против аварийного `REMOTE_DISCONNECTED`, сохранность исходного RAW.
- [Python Core E2E](../../mvk_compatible/tests/test_stage111z31fs_original_live_writer_e2e.py): синтетический 8 ADC Native ZIP + авторитетные Go source marks + реальный RAW + packet gate + локальные файлы; независимый экспорт и негативные сценарии с изменёнными байтами, масками, SHA, временем стадии и ложным clean close.
- **CI:** запускать полный набор по SHA последнего кодового изменения; переносить PASS только для действительно завершившихся jobs. Никакого утверждения аппаратного теста по синтетическим fixtures.

## Оставшиеся реальные ограничения

1. **Микросекундная точность клика Win32**: операторский QT→Go NEXT-FRAME mark принимается на первой полной границе следующего полученного TCP блока; оригинал обрабатывает флаг `WriteData` перед очередным `ReadUInt32`. Без одновременной инструментированной записи original EXE не заявлять совпадение для самого первого/последнего пакета.
2. **Оригинальные имена/TSXML:** оставшийся путь `00809475..008095F2` для имени и `00806A8C` для .tsxml; рабочие Go файлы намеренно названы `SOURCE_..._LIVE_RX_UNSCALED.bin`, не выдаются за оригинальный `TMVKThread` FileStream 1:1.
3. **WriteValues текст:** исходный `TMvkCellList.GetValueText` формат и региональная Windows кодировка требуют отдельной реальной Delphi пары. Истинный триггер PARAM `0x3100` уже восстановлен в FQ.
4. **Оригинальный реальный прибор:** не выполнялось аппаратное подтверждение на MVK01 новой Qt+Go программы; термин `original_delphi_file_parity_verified` остаётся **false**. Реальный исходящий SetRate доступен в отдельно разрешённом активном режиме и не меняет принципов receive-gate.
5. **Ошибки, сетевые reconnect, переполнение диска:** при недостоверных вводных или неподтверждённом финале запрещается публиковать локальный архив как полностью проверенную исходную запись, RAW при этом сохраняется для анализа.

Приватные IDP/PAS/DFM/SQLite, оригинальный EXE и реальные RAW/PCAP/BIN **не добавлялись** в публичный GitHub. Отдельных команд Flash/перезаписи IP/Reboot этот этап не добавляет.
