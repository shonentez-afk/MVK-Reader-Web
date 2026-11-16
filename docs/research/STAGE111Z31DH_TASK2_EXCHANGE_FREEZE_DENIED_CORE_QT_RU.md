# Stage111Z31DH — Task2: полная автономная цепочка обмена и доверие LIVE при отказе

Дата: 16 ноября 2026. Источники: приватные Projects.7z/_Unit125.pas, Projects.7z/_Unit128.pas, mvkview.idp, mvk_idr(1).sqlite. В публичной ветке хранить только производные алгоритмы и тесты. Исходные файлы, IDP, SQLite, PCAP и BIN не публиковать.

## 1. Непосредственно подтверждено исходными инструкциями

- _Unit125.pas 00807BC2–00807CE0: новый TMVKThread.TIdTCPClient на порт 10230, Stage=0 после создания, ConnectTimeout=1000 ms, ReadTimeout=5000 ms. Успешный connect ещё не Stage1.
- 0080839E–00808617: после получения валидного непустого сообщения регистров переводит Stage=0 в Stage=1. Данные АЦП и входящий ACK сами этот переход не создают.
- 00807E8F–00807F67: для Task=2 перед очередным ReadUInt32 снимает ровно одну запись из TList при Stage=1, вызывает 0080937C с ECX=2, EDX=Addr, затем отдельно TIdIOHandler.Write(Data). Не 12-байтная структура TList, а 9×UInt32 = 36 байт последовательных вызовов.
- 0080807B–008080A7: успешный входящий ACK просто логируется при Task=2; переход Stage=2 по ACK возможен в других Tasks, но не означает подтверждённый наш SetRate для пассивного Go.
- 008080AC–008080E1: DENIED с типом 0x00010FFF возбуждает errOperationDenied. При этом оригинал не продолжает делать вид, что текущий поток полностью нормален.
- 00808232–0080828C: `FreezeUpdate` или несовпадающая частота предотвращают ProcessBufferChunk; пакет всё равно считывается. Проверка каналов 0..9 остаётся.
- _Unit128.pas 0084DEA4–0084DEC3: кнопка bFreezeUpdateClick переключает Boolean TMVKThread.FreezeUpdate и обновляет pnMeasure.
- 008089B0–00808B0E: после ошибки Task=2 Stage=0, первый retry ставит новую SetRate напрямую через 00809364 при PauseValue<26, даже если прежняя команда осталась в TList; интервалы 250 ms, затем sqrt(2) до порога 801.

## 2. Реализовано

**Core:** новый `original_mode2_task2_exchange.py` реализует полный изолированный source Task2 test replay: начальный mRate1Click(Items[0])=65536, Stage0 при соединении, фрагментированные реальные пакеты во внутреннем `OriginalSourceReadFramer`, Stage1 после PARAM, одна dry-run команда из FIFO перед чтением, 9-словный проверенный Indy-план, входящие ACK без подтверждения отправленной команды, DENIED с errOperationDenied и сбросом Stage, флаг FreezeUpdate, пропуск несовпадающей ЧД, источник повторной SetRate при ошибке, исходная пауза и безопасный STOP. **Нет socket, device write, Go process, TCP retry или таймеров.**

**Core/настоящий Native:** в `original_mode2_live_health.py` наблюдаемый счетчик DENIED из текущего Go JSON становится системной ошибкой доверия: прежние предварительные графики и кнопки локальной записи больше не могут оставаться разрешёнными после отказа. Для старых status-снимков без нового доказательного поля отказ неизвестен, но не фабрикуется; отрицательный/ложный тип счетчика отвергается.

**Core/Qt:** `original_mode2_runtime_trace.py` содержит отдельный source processing freeze reference. Реальная кнопка Qt `bFreezeUpdateClick` меняет его вместе с уже существующим флагом временной остановки визуального превью и публикует тот же receipt на pnMeasure/PageStatus/PageFile. Реальный Go RAW продолжает записываться и команды не отправляются; программно такое поведение отличается от полной физической реализации TMVKThread.

**Исправление предыдущего расхождения:** `OriginalMeasureState.report` теперь показывает пять действительно подтвержденных из приватного IDP пунктов ЧД `65536,32768,8192,2048,512`, но отдельно `original_hardware_rate_setting_verified=false`.

## 3. Тесты

- `test_stage111z31dh_source_task2_exchange_core.py`: FIFO, 36-byte source Write plan, timing после Stage1, source ACK без связи с нашим SetRate, DENIED errOperationDenied, retry SetRate (включая сохранённые дубли), фрагментация, FreezeUpdate и несовпадающая ЧД.
- `test_stage111z31dh_denied_source_quality_core.py`: один действительно наблюденный DENIED закрывает доверие к каналу локальной записи и переводит штатный статус в ошибку; проверка некорректных счетчиков.
- `test_stage111z31dh_qt_source_freeze_denied.py`: настоящая Qt кнопка Freeze и реальные исходные статусные окна, отказ выключает локальную запись, подтверждения команды нет. Включён во все 4 Windows QPA/offscreen 100/150-DPI набора.
- Существующий test_stage111z31bs_original_measure_controls_core.py обновлён после доказательства пяти частот.

## 4. Граница аппаратной функциональности

**Не выполнена:** реальная Delphi-compatible исходящая команда и проверенное взаимодействие с МВК01, авторизованное сопоставление ACK с нашей командой, настоящий исходный auto-reconnect на физическом приборе, физический FreezeUpdate внутри TMVKThread, численный DSP/RPM и бинарный формат Delphi ChannelFile/ValuesFile на одном входном измерении. Новый автономный exchange не заявлен как hardware implementation.

Приёмка исходного SHA DH: проверять конкретный Actions run, Linux/Windows Core, Go build, Qt offscreen/native 100/150 и собранный EXE. Не помечать новый EXE принятым до 4/4 SUCCESS.