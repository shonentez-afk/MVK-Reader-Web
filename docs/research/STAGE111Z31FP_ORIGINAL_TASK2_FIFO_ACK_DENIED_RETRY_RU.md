# Stage111Z31FP — исходный Task2: один FIFO TX перед чтением, ACK/DENIED и retry

Дата: 18.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.

## Источник — обязательная совместная приватная проверка

Использованы вместе (локально, оригиналы не публиковать):

- `/mnt/data/mvkview.idp`: IDR project v3, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`, IDR-адреса исходного `TMVKThread.Execute`, `QueueCommand`, `SetRate`.
- `/mnt/data/Projects.7z`: извлечены `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`; все 5/5 размеры и SHA256 совпали с реестром `source_files`.
- `/mnt/data/mvk_idr(1).sqlite`: `PRAGMA quick_check=ok`; сигнатуры и граф вызовов `TMVKThread.Execute 00807A98`, `QueueCommand 00809330`, `sub_00809288`, `sub_0080937C`, `SetRate 00809400` проверены.

### Доказанный порядок исходного рабочего потока

1. `_Unit125:00809330` кладёт тройку `Cmd/Addr/Data` в `CommandList`.
2. `00807E8F..00807F6A` при `Stage=1` и непустом `TList` через `TThread.Synchronize -> sub_00809288` извлекает **ровно один** элемент, записывает 8+1 исходных DWORD в тот **же** `TIdIOHandler`, освобождает элемент и лишь затем переходит к следующему чтению `ReadUInt32` (`00807F78`). Никакого залпа нескольких команд из одного обработчика пользовательского действия в исходном worker нет.
3. `0080807B..008080A7`: ACK регистрируется, но Task2 не переходит в Stage2; ACK не имеет уникального идентификатора ранее отправленной SetRate. Его можно учитывать как временное свидетельство **только после команд на том же сокете**.
4. `008080AC..008080E1`: DENIED вызывает `errOperationDenied`. Исключение обрабатывается `0080896D`; после закрытия сокета `008089A3..00808B15` Task2 сбрасывает Stage и возвращается к исходной последовательности подключения/ожидания. Это исключение завершает текущую попытку, но не обязательно сам worker.
5. `00809364` и `00809400`: SetRate обновляет локальный `MvkSampleRate` и ставит исходную SetRate в очередь; подтверждённая A/B PCAP конструкция 36 байт остаётся неизменной.

### Внесённые исправления (production Go)

- `source_live_task2_tx.go`: штатный stdin `RATE` только *очередь* и локальный выбор частоты; `afterReceivedFrame` только фиксирует состояния, ACK и DENIED. Ни один callback не отправляет команды. Новый `sentInSocket` сбрасывается при новом подключении, предотвращая приписывание нового ACK/DENIED отправке на предыдущем сокете. `sentCommands/sentBytes` остаются суммарными и не обнуляются для честной трассировки. <https://github.com/shonentez-afk/MVK-Reader-Web/commit/4c0cdea31e8bb7601b0ec3bc286da109545b2aa8>
- `main.go`: ровно один `sendNext` после штатной проверки stop/deadline/RAW-лимита и перед очередным `Read`; применяется только к явно разрешённому устройству и существующему TCP Task2 соединению. <https://github.com/shonentez-afk/MVK-Reader-Web/commit/39cca58f6b96eaec0f15f90b19b1e3989a48641a>
- `source_task2_connect_retry.go`: `SOURCE_OPERATION_DENIED` теперь следует тому же пути retry, что исходное исключение, **только когда отдельно одобрено** физическое переподключение после RAW (`sourceAfterRAWReconnect`). Без отдельного допуска отказ завершает текущую операцию без нового сокета. <https://github.com/shonentez-afk/MVK-Reader-Web/commit/8650e029565c3f9ab1d09608eb8aab7df012e682>

### Регрессии

- `source_live_task2_tx_test.go`: первая отправка после PARAM делается в следующей итерации чтения, двухэлементная операторская очередь не передаётся одним залпом, сохранены исходные 36-байтные SetRate в правильном FIFO порядке; ACK не вызывает тайную отправку; новый сокет не наследует временные ACK/DENIED доказательства от первого. <https://github.com/shonentez-afk/MVK-Reader-Web/commit/2b839ddebbe7e06e4cce1efd06e37fd20ab9b464>
- `source_task2_passive_retry_test.go`: два реальных loopback TCP-сокета: первый выдаёт DENIED, затем после согласованного backoff новый сокет получает PARAM; сохранён оригинальный RAW и SHA-разделение; 0 байт TX в пассивном режиме. <https://github.com/shonentez-afk/MVK-Reader-Web/commit/5c73387bd19a0bcdd9efd5e763cfa0f569c907e8>

Тесты выполняются только на `127.0.0.1`; физический МВК01 не подключался. Нельзя объявлять новый пакет PASS до полной GitHub Actions приёмки последнего кодового SHA. Исходные `IDP/7z/SQLite/PAS/DFM`, реальные RAW/PCAP/BIN не публиковались.

## Что пока ещё не означает original 1:1

Физический прибор, точная причинная привязка ACK к команде (нет transaction ID), полный полевой сценарий IP → Measure → изменение Fs → DENIED/reconnect → сохранение, аппаратные Task3–5/Flash/перезапись IP и точный исходный WriteData/WriteValues продолжают требовать отдельной проверки. Аппаратные команды опасного изменения настроек не активируются автоматически; `original_delphi_compatibility_verified=false`.
