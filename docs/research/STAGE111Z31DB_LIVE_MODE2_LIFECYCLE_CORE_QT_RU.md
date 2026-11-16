# Stage111Z31DB — защита реального LIVE Mode2 при Stop / stale / fault

Дата: 16.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.

## Источник и пределы

Исходная логика сверена с операторскими **локальными** `Projects.7z/_Unit125.pas`, `_Unit128.pas` и `mvkview.idp`. Не добавлять их в GitHub.

- `00848E78 → 00846AD4`: кнопка «Измерение» выбирает Mode2; пять вкладок и pnMeasure показываются **до** создания TMVKThread.
- `00807A98`: TMVKThread.Execute владеет сетевым соединением/чтением; оригинальный `tmInterfaceUpdateTimer` вызывает `00847248`, период исходного таймера 20 мс.
- `00809330`: `QueueCommand(Cmd,Addr,Data)` добавляет в `TList` отдельный 12-байтовый узел. `00809364`: `SetRate` ставит Cmd=1, Addr=0x0e, Data=MvkSampleRate при изменении значения. `00807E8F..00807F62`: исходная очередь выполняется внутри socket thread; **это пока не подключено к прибору**.
- `00808241..0080824B`: исходный FreezeUpdate влияет на обработку очередного чанка, а не только на визуальное рисование. Совместимый Native R6.1 продолжает писать полный RAW при визуальной паузе: это осознанно **не полный source parity**.

## Что реально сделано в пакете DB (Core + Qt)

1. `core/original_live_view_gate.py`: `gate_live_preview` повторно сверяет каждое асинхронное событие `LivePreview` с ПОСЛЕДНИМ подтверждённым Native status. Только RECORDING, не stale, без ошибок кадров/пропусков, корректный session_id, проверенные счётчики, диапазоны/частота каждого АЦП; запрет после graceful Stop.
2. `desktop/main_window.py`: перед `_receive_live_preview` применяется Core gate; невалидный статус немедленно сбрасывает **оба** предварительных графика, старые спектры/отсчёты больше не остаются на экране. После Stop запоздавший хороший status/preview не разрешает показ; Qt виджет сохраняет одно транспортное соединение.
3. `core/original_measurement_mode.py`: состояние STOPPING не может показывать зелёное соединение, пока Go завершается. `core/original_measurement_pipeline.py` выключает при Stop паузу и выбор частоты; `desktop/original_measure_controls_ui.py` отключает обе кнопки записи. `desktop/main_window.py` дополнительно отвергает прямой `source_write_toggle` во время STOPPING, даже в обход кнопки. `request_measurement_stop` рендерит общую Core-политику, не подменяя её ручным QLabel.
4. Тесты: `test_stage111z31db_live_view_gate.py`, `test_stage111z31db_qt_live_view_gate.py`; предыдущие тесты live preview / toolbar адаптированы: для принятия превью нужен валидированный текущий status. Новые Qt тесты включены в Windows DPI 100/150 (offscreen и native QPA), ядро — в общий Linux/Windows suite.

## Что **НЕ** сделано и не должно заявляться

- Это НЕ аппаратный TMVKThread и НЕ device-write QueueCommand/SetRate.
- Полный original 20 ms GUI timing, FreezeUpdate blocking ProcessBufferChunk, оригинальные 5 source sample-rate кодов и аппаратный retry/error reconnect не восстановлены.
- Никакой операторский прибор не подключался в этом пакете. Go read-only, без исходящих payload-команд.
- LIVE FFT / GetSignal остаются **кандидатами** на основе валидированных исходных Float32 Native, не аттестованным численным/визуальным Delphi parity.
- Frame marks этапа DA остаются прежними, 10/43/73 и исходный RAW не меняются.

## Приёмка и продолжение

Новый код следует считать **изменением в проверке**, пока не принят актуальный GitHub Actions для последнего DB SHA: `15037f6412b08f667b6dc6809cfe3374571af38b`, запуск `#43845157714`. Документ [skip ci] сам по себе не является подтверждением EXE.

Дальше — одним комплексным пакетом исходный **автономный (без TCP) командный планировщик** с Cmd/Addr/Data, строгая полная карта исходных error/timeout/stop переходов и равный E2E всех LIVE страниц на одной сессии, затем отдельный разрешённый оператором аппаратный parity test. Не подменять 5 исходных кодов частот значениями Native Hz.
