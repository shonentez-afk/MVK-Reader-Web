# Stage111Z31DG — приёмный протокол TMVKThread, ответы, ошибки и LIVE-проекция

Дата: 16 ноября 2026 года. Основа: приватные Projects.7z (_Unit125.pas), mvkview.idp, mvk_idr(1).sqlite. Ни один оригинальный файл, IDP, SQLite, RAW или личный PCAP в GitHub не публиковался.

## Проверенные исходные функции MVKView 1.0.47

| Адрес в оригинале | Операция |
|---|---|
| 00807C12–00807C39 | TCP порт 0x27F6=10230, ConnectTimeout=0x3E8=1000 мс, ReadTimeout=0x1388=5000 мс |
| 00807F74–00808019 | Чтение UInt32 типа и длины, затем проверка 8 ≤ L ≤ 0x20000 и L кратна 4 |
| 00808060 | Тип 0x00000001: идентификационные DWORD считываются и пропускаются |
| 0080807B | Тип 0x00010FF0: входящее подтверждение операции. В пассивном Go нельзя приписывать его своей команде |
| 008080AC | Тип 0x00010FFF: входящий отказ операции и исходное исключение errOperationDenied |
| 008080EB | Типы 0xFF8001AC TACH и 0xFF800ADC ADC: пять DWORD заголовка, канал 0–9, source rate; ProcessBufferChunk при совпадении выбранной ЧД и FreezeUpdate=False |
| 0080839E–00808718 | Тип 0xFF800C0D: список блоков регистров, descriptor Addr=low16, Words=high16, чётная ненулевая длина и граница регистра 0x4000 |
| 00808617 | Исходный Stage 0→1 при успешном разборе содержательного пакета регистров, не при TCP Connect |
| 00808736–00808762 | Stage 3 требует source StatusCells >0, что невозможно доказать лишь счётчиками Go |
| 008087BB | Неизвестные типы регистрируются и пропускаются, не превращаясь в измерения |
| 008088A2, 008088CE, 008088FA, 00808923 | Раздельные обработчики disconnect/read timeout/connect timeout/Indy network error |
| 008089BA–00808B0E | При Task2 сброс Stage0, PauseValue=25 означает 250 мс; Round(PauseValue)*10 мс, рост sqrt(2) до порога 801; повтор исходной SetRate при PauseValue<26 |

## Изменения Core, Go и Qt

- Core original_mode2_received_frames.py: чистый ограниченный эмулятор приёма фрагментированных фреймов с исходными типами, длиной, десятью каналами, source rate и FreezeUpdate, Stage0/1 и отказами. Сокетов и приборной записи нет.
- Core original_mode2_rx_evidence.py и native_r6_live_status.py: три счётчика входящих событий должны присутствовать атомарно, не превышать frames_decoded, не откатываться; отсутствие старых полей трактуется как UNKNOWN. Ни один входящий ACK не считается результатом нашей неотправленной SetRate.
- Core original_mode2_retry_timing.py: автономная модель source timeouts 1000/5000 мс и backoff 250 мс × sqrt(2); не подключена к физическому TCP.
- Core original_mode2_runtime_trace.py: единый receipt LIVE Mode2 содержит read-only события. Только после зарегистрированного входящего PARAM с блоками симулируется извлечение одной первоначальной SetRate(65536) из сухой очереди с девятью Win32 UInt32 Write calls. Physically sent = false.
- Go R6.1 monitor.go: счётчик source_rx_nonempty_parameter_frames увеличивается только для реально полученного и проверенного PARAM с ненулевыми блоками. Исторические ACK и DENIED счётчики уже были; live_progress.go экспортирует все три атомарно в один JSON sidecar. Входящий RAW, поток TCP и число клиентов не менялись.
- Qt main_window.py: единый read-only receipt прикреплён к существующим pnMeasure, PageStatus и PageFile, без инженерных экранов. PageAdc и PageSpectrum остаются привязаны к проверенному LIVE-превью.
- Qt original_measure_controls_ui.py: реальный входящий DENIED отображается на штатном lbStatus как отказ прибора, с явным пояснением, что наше приложение не отправляло команд. Go остаётся read-only.

## Автоматические проверки

- test_stage111z31dg_source_received_frames_core.py: фрагментация, исходные типы и границы пакетов, Stage0/1, FreezeUpdate, неверные длины, ACK/denied, неизвестный тип.
- test_stage111z31dg_native_rx_evidence_core.py: входящие счётчики, целостность, монотонность, неизвестность старых JSON, dry-run извлечение SetRate после Stage1 без отправки/ложного ACK.
- test_stage111z31dg_source_retry_timing_core.py: timeouts 1000/5000, старт 250 мс, √2, reset только после source connect.
- test_stage111z31dg_qt_received_protocol.py: реальные Qt панель и страницы, source Stage readiness и входящий DENIED, отбрасывание недостоверного JSON. Включено во все четыре Windows DPI100/150 native/offscreen набора.
- Go source_rx_evidence_test.go: реальные парсер/monitor с синтетическими PARAM/ACK/DENIED, без аппаратных команд.

## Границы приёмки

Автоматические тесты используют синтетику и не являются аппаратным испытанием. Пока НЕ восстановлены реальная отправка QueueCommand/SetRate, подтверждение ответа на нашу команду, физический source auto-retry, настоящая FreezeUpdate в вычислительном потоке, source Stage3 через StatusCells, Delphi BIN/VALUES байтовый паритет, RPM, GUI/DSP/спектр 1:1 на одном МВК01. Новые команды настоящему прибору не отправлять без отдельной верификации и допуска оператора.

Принятая DF baseline имеет 4/4 CI success; DG проверяется на своём точном исходном SHA, и не должен называться выпущенным до успеха всех 4 jobs.