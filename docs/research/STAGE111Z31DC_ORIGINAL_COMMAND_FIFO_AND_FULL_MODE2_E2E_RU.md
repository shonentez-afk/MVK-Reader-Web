# Stage111Z31DC — исходная QueueCommand/SetRate, ошибки и сквозной Mode2 Core+Qt

Дата: 16 ноября 2026. Исходники сверены по локальным приватным Projects.7z/_Unit125.pas, _Unit128.pas и mvkview.idp. **Приватные артефакты в GitHub не загружать.** Исполнение команд на приборе НЕ разрешено и НЕ включено.

## 1. Подтверждённые исходные переходы

- _Unit128.pas 00848E78 bTaskConnectClick выбирает Mode2. Пять исходных вкладок и pnMeasure видимы **до** TMVKThread.Create 00846DCC; TCP не является условием показа.
- _Unit125.pas 008060B0/0080618E задаёт MvkSampleRate=309, Source INTERNAL code, **не** 309 Гц; WriteDataStage/WriteValuesStage изначально =2, флаги FreezeUpdate/WriteData/WriteValues=false.
- 00809330 QueueCommand(Cmd:Integer, Addr:Cardinal, Data:Cardinal) выделяет 12 байт **памяти**, добавляет в TList указатель. Это little-endian int32/uint32/uint32 в памяти, **НЕ** готовый сетевой протокол.
- 00809288 берёт CommandList.Get(0) и удаляет Delete(0): FIFO. 00807E8F..00807F67 забирает 1 запись при Source Stage=1, далее оригинал исполняет сетевой writer 0080937C (байтовый паритет ещё не принят).
- 00809400 SetRate при идентичном коде не делает ничего; при изменении обновляет MvkSampleRate и через 00809364 ставит в очередь Cmd=1, Addr=0x0E, Data=MvkSampleRate. Пять исходных Tag меню gvar_008D2F7C требуют независимой проверки; **пять Go Fs НЕ заменяют эти коды**.
- Source 00808871..0080897E различает EIdConnClosedGracefully/errDisconnected, EIdReadTimeout/errNotResponding, EIdConnectTimeout/errCannotConnect, EIdException/errTransferError и Exception. errInvalidPacket/errOperationDenied/thrSystemError — отдельные маршруты. Эти ошибки нельзя автоматически отождествить с Native R6.1 JSON отказом.
- Source tmInterfaceUpdateTimer 0084F7C8 вызывает 00847248, исходный GUI период 20 мс. Native Qt status poll около 900 мс. FreezeUpdate источника пропускает обработку входящих блоков; Go RAW намеренно продолжает писаться при визуальной паузе.

## 2. Сделано в Core + Qt

1. core/original_mode2_command_queue.py: автономный строго offline 12-byte TList command FIFO, одну запись за Stage=1, Source default rate code 309, SetRate только при изменении внутреннего кода, строгие Integer/Cardinal, лимит 256, транзакционный отказ и очистка; **нет socket или network API**.
2. OriginalMode2FaultRoutes: отдельно пять Delphi exception routes и три source parser/status errors; Native ошибки имеют отдельный не-Delphi provenance; журнал ограничен последними 64 событиями.
3. core/original_mode2_runtime_trace.py: одна цепочка MODE2_BEFORE_TCP → CONNECTING → RECORDING/SILENT/STREAM_ERRORS/REFUSED/STATUS_REJECTED → STOPPING → VERIFIED_ARCHIVE либо STOPPED_WITHOUT_ARCHIVE → IDLE. Initial status pending не подменяется connect fault, session_id и счётчики привязаны к одному Native run.
4. desktop/main_window.py: реальное Qt событие измерения, start, проверенный status, status rejection, Stop, failed retry и finish связаны одним Core runtime. Ровно один receipt используется на существующих pnMeasure/PageStatus/PageFile; PageAdc/PageSpectrum потребляют текущий проверенный Native preview через ранее принятый fail-closed gate. **Нет новых инженерных панелей или поддельных приборных регистров.**
5. При повторном разрешённом измерении после отказа создаётся новый Core command/fault/session ledger; уже ранее проверенный архив снова паркуется и не теряется.
6. Кнопки freeze/rate/source write остаются заблокированными во время STOPPING; после malformed Native status предыдущий preview очищается.

## 3. Автоматические проверки

- tests/test_stage111z31dc_source_command_and_runtime_core.py: FIFO, полная 12-byte структура, SetRate idempotence/overflow, fault routes, bounded long-run ledger, повтор/чужой/потерянный session_id, ожидание первого статуса, Stop/retry/finish.
- tests/test_stage111z31dc_qt_full_live_mode2.py: реальные виджеты пяти вкладок, 10/43/73 PageFile, PageStatus, PageAdc и PageSpectrum на одной синтетической Native-сессии, проверенный Float32 preview, исчезновение старых графиков при потере пакетов, здоровое повторное подтверждение, безопасная остановка и новый запуск с сохранённым архивом.
- Qt E2E включён в Windows offscreen 100/150% и native QPA 100/150% CI. Все тесты используют синтетику, **не прибор**.

## 4. Оставшиеся границы восстановления

**НЕ готово:** исходный on-wire serializer и ответы команд, точные пять rate Tag, физическое source FreezeUpdate, 20ms UI-паритет, все аппаратные retry/timeout, TACH RPM, same-device GetSignal/FIR/FFT/DSP/графика и полный Win32 1:1. Ни одна из этих границ не подменяется подготовленной очередью в памяти.

Следующий крупный пакет — сетевой serializer и аппаратный error/stop workflow сначала в закрытом эмуляторе, без исходящих команд; после восстановления полного байтового протокола — отдельная разрешённая оператором проверка на приборе и same-data original Win32 parity. Старые FFT/Power/Y, маски 10/43/73 и проверенный Go RAW без надобности не переделывать.
