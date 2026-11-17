# Stage111Z31DM–DP — исходящая 36-байтная SetRate подтверждена по реальным PCAP и исходной Delphi, реконструкция полной первой транзакции

Дата: 17 ноября 2026 года. **Доказательное разделение:** оригинальная MVKView Win32 действительно отправляла 36 байт в двух реальных A/B TCP/10230 захватах 2026-10-26; успешный пассивный Go Native R6.1 и записи 1111.pcapng/83/84 при этом не требовали исходящих application payload. Не делать ложный вывод «команда обязательна» или «команд не существует».

## Независимый реальный эталон (уже в публичном проекте)

`docs/CLIENT_COMMAND_36_BYTES_TCP10230_ANALYSIS_RU.md` от 2026-10-26 — результаты офлайн-анализа ДВУХ оригинальных захватов подключения/отключения A/B. Реальные клиентские 36 байт из двух сегментов **4 + 32** совпали в A и B побайтно:

```text
0d 0c 80 ff 24 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 01 00 00 00 0e 00 02 00
00 00 01 00
```

| Время от SYN | A | B |
|---|---:|---:|
| Первые байты от прибора | 1.277 мс | 11.667 мс |
| Начало source TX 36 | 41.593 мс | 68.079 мс |
| Конец source TX 36 | 44.807 мс | 68.252 мс |

**Прибор начинает передавать данные ДО этого сообщения.** Доказано присутствие и байты команды, но не необходимость для streaming и не аппаратный эффект смены rate. В `docs/LONG_TCP10230_CALIBRATION_AUDIT_20261026_RU.md` сессия `1111.pcapng` начинается посреди stream без SYN/VAST_MVK, поэтому отсутствие раннего TX не противоречит A/B. `docs/THREE_NEW_CAPTURE_SESSIONS_AUX160_DYNAMIC_20261026_RU.md` подтверждает: в ТРЁХ пассивных Go-сессиях клиентских payload=0, RAW равен TCP RX; 8 АЦП и AUX принимаются без команд. Эти PCAP оригинальные файлы не находятся в текущем контейнере; отчёты не подменять повторным анализом файлов.

## Исходные адреса Delphi и отправка

Частный `Projects.7z/_Unit128.pas`:
- 00846D91..00846DD1 — `edIpAddr.Text` (ранее из `mvkview.exe.xml/Device/Address`) передаётся в `TMVKThread.Create`.
- 00846DDF..00846DF7 — немедленный `mRate1Click(Items[0])`, rate=65536. Это постановка в очередь, а не немедленный TCP send.

Частный `Projects.7z/_Unit125.pas`:
- 0080618E `MvkSampleRate=0x309` (777) — стартовый sentinel, отличающийся от выбранной частоты.
- 00809364/00809400 `QueueCommand(Cmd=1,Addr=0x0E,Data=65536)` при изменении частоты.
- 00807C12..00807C39 — remote `edIpAddr:10230`, ConnectTimeout=1000ms, ReadTimeout=5000ms.
- 00808617 после корректного входящего `PARAM` (не TCP Connect!) — `Stage0→1`. При следующем Source Execute Read-cycle 00807E8F..00807F52 берётся **одна** FIFO команда, вызывается `0080937C` (8 WriteUInt32) и затем `Write(Data)` (девятый UInt32).
- Точные 9 слов: `FF800C0D,00000024,00000000,00000000,00000000,00000000,00000001,0002000E,00010000`; Win32 Indy AConvert=False + ToBytes ⇒ little endian, полная 36-байтовая последовательность **теперь независимо совпадает с PCAP**.
- Source `008061DB` заполняет 14 StatusCells байтами FF. `0080872D` сравнивает **unsigned** StatusCells[0]>0 после PARAM; пока `0x1006` не получен, `0xFFFFFFFF` может перевести исходный поток в Stage3 ДО отправки. Это возможная причина NO TX, а НЕ подтверждённая ошибка оборудования. В проверенном Go неизвестный Status0 должен остаться UNKNOWN, Stage3 только от реально прочитанных двух слов; это сознательная безопасная разница.
- Incoming `0x00010FF0` ACK не содержит доказанного ID исходной SetRate, не выдавать входящий ACK за его подтверждение. `0x00010FFF` DENIED — отдельная ошибка/повтор.

## Выполненные изменения Go / автономного Core / оригинального Qt

- `source/original_task2_command_lab.go`: реальный 36-байтовый source writer `sourceSetRateWireBytes` с пятью подтверждёнными rate, изолированный source Task2 duplex state и метод `writeOneBeforeRead(io.Writer)`. **Только тестовые `bytes.Buffer/net.Pipe`, НЕ production dialer**. Literal source FF sentinel Stage3 отдельно учитывается, так что он не маскируется корректным hardware error.
- `source/original_task2_command_lab_test.go`: 9 independent UInt32 words, пять rates, golden HEX из двух настоящих A/B PCAP, early ACK неупарен, nonempty PARAM→Stage1→ровно один FIFO writer, DENIED, Stage3, FF sentinel, локальный `net.Pipe`, и actual passive Go TCP на локальном fake server — ноль записанных байт даже после реально принятого `PARAM 0x1006=0`. Никаких соединений с настоящим МВК01.
- `source/live_progress.go` добавлен атомарный `source_mode2_tx_evidence`: source PARAM Stage1 candidate, доказанный нулевой Status0, отдельный risk от неопределённого source FF, потенциальная source dispatch, фактически **0 байт** переданных через Go.
- `core/original_mode2_transmit_evidence.py`: строгий validator, сверяет весь proof с самим RX PARAM, 14 StatusCells, CaptureOnly и read-only. Reject forged alleged command sent/nonzero byte count/ambiguous FF. Старые Go receipts без нового поля остаются UNKNOWN.
- `main_window.py`, `original_mode2_runtime_trace.py`, `original_measure_controls_ui.py`: одна и та же Core evidence включена в существующие штатные `pnMeasure/PageStatus/PageFile` properties; в стандартной подсказке `lbStatus` разъясняется, что была бы отправка исходной 36-байтной команды, а Go фактически отправил 0 байт. Не добавлены исследовательские окна; исходное меню частот НЕ маскирует read-only режим как реальную установку приборной ЧД.
- `tools/research/offline_tcp10230_pcap_audit.py`: локальный потоковый беззависимый reader PCAP/PCAPNG: раздельный RX/TX по TCP/10230, EPC Ethernet/RAW/сooked IPv4, TCP reassembly для первого 1MiB TX, обнаружение точной сигнатуры 36 байт при 4+32/другой сегментации/ретрансмиссиях. **Никогда не создаёт соединений**. Примеры:
  `python tools/research/offline_tcp10230_pcap_audit.py "подключение A.pcapng"`
  `python tools/research/offline_tcp10230_pcap_audit.py "1111.pcapng" --instrument-ip 10.13.42.84`
  (подставить ФАКТИЧЕСКИЙ IP из захвата, это не пример обязательного адреса для XML).
- Все тесты Python core и реальные Qt DPI 100/150 подключены в Windows/Linux CI.

## CI и ограничения

Последний программный исходный SHA: `4d6d407729e7422a605dddb4b438bcd84ae2acb0`. Дождаться **4/4 SUCCESS** в Actions для этого SHA прежде чем объявлять EXE проверенным; последующий документационный `[skip ci]` не пересобирает EXE.

**Не завершено:** включение физической source SetRate в действующий Native/Qt по отдельному промышленному допуску, подтверждённая атрибуция ACK, автоматический source live-retry и численный same-run DSP/RPM/GDI/экспорт. Известная точная команда не значит, что её обязательно надо посылать в работающий прибор: 3 пассивных live записи содержат полный сигнал без TX.

Не публиковать оригинальные user PCAP/RAW, PAS, IDP, SQLite, XML, фото или индивидуальные приборные данные.
