# Stage111Z31DQ-DY — полная цепь Measure: оригинальная отправка SetRate в том же TCP-потоке, ядро и Qt

Дата: 17.11.2026. Последний кодовый SHA 4efdb678055d7a9fef78dca8e5b09717c576eb4a. CI: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44002683666 (при подготовке отчёта проверка в процессе). НЕ называть эту версию выпущенной до подтверждения всех четырёх CI jobs. Не опубликованы приватные PAS/IDP/SQLite/PCAP/BIN/XML.

## Подтверждённый оригинал

- Из CP1251 XML, Configuration/Device/Address, по умолчанию 192.168.0.30, IP заполняет edIpAddr на PageStart. Исходный пользователь может изменить поле; при Measure его актуальное значение поступает в TMVKThread.Create и IPAddress. Локальный Ethernet IPv4 — отдельный IP привязки сетевого адаптера, не подмена адреса прибора.
- _Unit128.pas, _Unit125.pas: при нажатии Measure Mode2 и PageStatus + видимые вкладки появляются сразу ДО реального TCP connect; создаётся TMVKThread, внутренний constructor MvkSampleRate=0x309, mRate1Click создаёт FIFO SetRate(65536). Стандартные частоты 65536,32768,8192,2048,512 Hz.
- TCP/10230 соединение само может вызвать входящий RX без команд, как доказывают независимые пассивные Go captures. Оригинальный Task2 после непустого корректного PARAM переводит Stage0→1; только при Stage1 выдаёт одну команду FIFO, 8 TIdIOHandler.Write(UInt32 LE) + девятое Write(rate)=36 байт. В двух реальных A/B PCAP оригинального клиента от 26.10.2026 одинаковый поток 0d0c80ff2400000000000000000000000000000000000000010000000e00020000000100 разделён TCP на 4+32, прибор уже выдавал RX до TX. Следовательно, передача действительно существовала в оригинале, но не доказана как обязательная для старта.
- StatusCells[0] в источнике до данных FF-сентинел, что может включить Stage3 по unsigned >0. В совместимом клиенте запрещено объявлять аппаратный fault, пока реально не получено оба 16-битных слова регистра 0x1006. Incoming ACK не несёт подтверждённого transaction ID, поэтому учитывается только порядок во времени. DENIED прерывает командный путь.
- Источники дополнительных сетевых команд для чтения конфигурации и Flash/reboot являются отдельными служебными Task, не частью Measure, и никогда не должны попасть в штатную кнопку измерения.

## Изменения файлов Core + Qt + Go

- Go source/source_live_task2_tx.go и source/original_task2_command_lab.go: построитель девяти точных little-endian UInt32; настоящий conn.Write(36) на ТОМ ЖЕ TCP-сокете, который выполняет ProcessChunk. Только source SetRate Cmd=1/Addr=0x0E / пять подтверждённых частот; nil/unknown Status0, Stage3, DENIED, ошибки TCP блокируют дальнейшую отправку.
- По умолчанию весь Go R6.1 остаётся пассивным. Режим физической SetRate можно включить только с тремя явными аргументами: -approve=true, -source-setrate-tx=true, -source-setrate-tx-approved=true. Нужны локальные LiveStatus и stop-file. Это не означает уже проведённого аппаратного испытания на промышленном МВК.
- В NativeCaptureDialog PySide6 добавлен ОТДЕЛЬНЫЙ, выключенный по умолчанию чекбокс r6OriginalSourceSetRateTX, явное окно согласия. Пока один capture не подтверждён, пять пунктов оригинального меню pnMeasure bSampleRate отключены. Для каждого изменения во время измерения требуется отдельное подтверждение. Команда RATE N + LF передаётся по QProcess stdin, а Go разрешает только пять source rate. Физических команд в Qt нет, второго сокета не создаётся.
- source_task2_connect_retry.go восстанавливает source ConnectTimeout 1000ms, ReadTimeout 5000ms и первоначальный retry в паузах Round(25 * sqrt(2)^n) * 10ms, ограничение 8010ms. ПОВТОР ПОДКЛЮЧЕНИЯ доступен только ДО первых RAW байт и до физической TX: склейка двух физических TCP-сеансов в один RAW/BIN была бы неправдой.
- Source Native JSON, original_mode2_active_tx_provenance.py, original_mode2_transmit_evidence.py, original_mode2_runtime_trace.py, connected_system_status.py и оригинальная панель Qt показывают read-only=FALSE после реально отправленных application bytes, монотонные bytes/commands, выбранную исходную rate, временные ACK/DENIED и отказ. Source Rate TX никогда не объявляется проверенно применённой прибором лишь из-за входящего ACK.
- Go summary.json сохраняет source_setrate_tx_approved, source_setrate_sent_commands, source_setrate_sent_bytes, source_setrate_last_rate_hz, temporal ACK/DENIED. При изменения ADC Fs в текущем session RAW RX продолжает сохраняться, но single-rate предварительный BIN/preview заблокирован, что видно оператору: архив единой частоты без сегментации не сертифицировать.

## Автономные тесты

- Go live localhost fake device (отправка действительно идёт по conn.Write при valid PARAM), source full 36-byte stream PCAP match, test net.Pipe; система без разрешения остаётся 0 outgoing payload. Go source Task2 immediate/after error stage3, FIFO, RATE parsing, five menu rates, retry waits.
- Python Core отдельные test_stage111z31dt_original_real_tx_core.py и test_stage111z31dw_source_rate_stdin_core.py, проверка актульного LF, rollback команды, неправдоподобного TX proof, кросс-валидатора source RX и 14 StatusCells.
- Qt test_stage111z31dt_qt_original_real_tx.py включён в Windows native/offscreen DPI 100/150; проверяет действующую PageStatus/pnMeasure и разрешение исходных пяти кнопок.
- Всё это программные тесты/localhost fake instrument, а не измерение на настоящем приборе. Source commits до CI-принятия не выдавать за готовый EXE.

## Честные открытые границы

1. Авто-переподключение после уже поступивших RAW данных требует нового физического TCP-сегмента/измерительной сессии с новой идентичностью и доказанной последовательностью регистров, а не дописывания в один старый RAW. В текущем Go реализован только initial retry до RAW.
2. Byte-perfect исходный BIN/TSXML/WriteData/WriteValues при динамической смене частоты и командовании произвольными исходными приёмами записи НЕ завершён. Есть сохраняемый RAW, независимая проверка обычной непрерывной одночастотной записи и защита от ложного экспорта mixed-rate.
3. Source однозначная связка конкретной SetRate с ACK не доказана; в существующем полученном типе ACK отсутствует подтверждённый ID. Программа сохраняет temporal events, не подменяя ими реальный ACK.
4. Реальный полевой same-run тест Win32 MVKView 1.0.47 и новой MVKView Compatible, все Delphi Win32 расчёты DSP/FFT/RPM, временное отображение TQGrapher и графический/численный паритет 1:1, а также окончательные сложные 15 форматтеров видимой PageStatus, ещё не приняты.
5. Чтение конфигурации и Flash/Reboot — отдельные сервисные задачи, не включённые в Measure; их не отправлять промышленному прибору без отдельного сценария, источника и допуска.

Релевантные ранее подтверждённые отчёты: docs/CLIENT_COMMAND_36_BYTES_TCP10230_ANALYSIS_RU.md, docs/research/STAGE111Z31DP_ORIGINAL_36_BYTE_TX_PCAP_SOURCE_MODE2_CORE_QT_RU.md, docs/research/STAGE111Z31DL_ORIGINAL_XML_15_VISIBLE_STATUS_REGISTERS_IP_MODE2_RU.md.
