# Единый пакет восстановления: PARAM/Freeze в цикле IP → Измерить → Stop

Дата: 18.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.
Этот документ фиксирует конкретно восстановленную часть оригинального алгоритма, а **не** объявляет весь MVKView 1.0.47 побайтово идентичным.

## Совместные приватные источники

Использованы все три: `/mnt/data/mvkview.idp` (оригинальные метаданные и адреса, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`), `/mnt/data/Projects.7z` (декомпилированные Delphi/Pascal/DFM, SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`), `/mnt/data/mvk_idr(1).sqlite` (индекс 25 404 функций, SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`). Сверены SHA256 всех пяти исходных файлов `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm` с таблицей `source_files` SQLite. Приватный исходный код/архив/IDP/SQLite в GitHub **не включены**.

Функции/адреса: `TMVKThread.Execute 00807A98` (паскаль `_Unit125.pas`); `Tmvkform.bTaskConnectClick 00848E78` (`_Unit128.pas`); `TMVKThread.SetRate 00809400`. **PARAM**: после envelope читаются пять DWORD по `0080841B..00808448`, поле `count` по смещению 24. При `count == 0` ветка `0080844F → 00808718` оставляет Stage0 прежней; пакет **28 байт допустим**. **FreezeUpdate**: `0080850C..00808516 → 008085E1` читает и отбрасывает все DWORD данных PARAM, не вызывает обновление регистров/VALUES. Непустой PARAM позднее переводит Stage0→1 в `00808617`, даже если блоки были пропущены под Freeze. Триггер `0x3100` обрабатывается только при невключённой Freeze по `008085A5..008085BD`.

## Реализованные связанные изменения

1. `protocol.go`: принимает валидный `PARAM=28` и проверяет `count=0`; по-прежнему отвергает повреждённые дескрипторы и не выдумывает значения.
2. `monitor.go`: сохраняет **все** TCP-байты в неизменяемый `incoming.raw`. Пустой PARAM учитывается как кадр без смены Stage; при `FreezeUpdate` не обновляются register image, `liveBin.paramFrame`, AUX4700, `ValuesTicks/WriteValues`. Отдельно считаются реально пропущенные PARAM, AUX и `0x3100`, а сырой поток остаётся пригоден для судебной/технической проверки. Счётчик **полученных непустых PARAM** не смешивается с применёнными значениями: нужен оригинальной Stage1.
3. `source_original_param_gate.go`, `main.go`: для Mode2 ведётся **локальный** `SOURCE_ORIGINAL_PARAM_FRAME_GATE.jsonl`: номер реально разобранного кадра, SHA256 полного PARAM, количество дескрипторов, FreezeUpdate, признаки AUX и `0x3100`. Файл и SHA256 входят в итоговый Go-архив и `summary.json`; никакой команды прибору и второго TCP-соединения нет.
4. `original_param_gate_proof.py` и `original_values_3100_timeline.py`: после Stop Python **по-новому проверяет** исходный RAW против каждого журнального PARAM; считает только применённые AUX и `0x3100`, а замороженные пропускает. Неизвестный/подменённый/отсутствующий журнал при наличии пропущенных кадров — строгий отказ; ни один «задним числом нарисованный» тик не принимается. Для прежних архивов без журнала допустим только legacy-путь без подтверждённых Freeze-пропусков.
5. `original_mode2_received_frames.py`: тот же 28-байтовый пустой PARAM разрешён и в отдельной исходной Python-модели; `original_live_write_stages.py` связывает её с проверкой реальной Go-сессии; нижняя панель Qt показывает правильную семантику Freeze.

## Проверки сквозной цепочки

- Go: `TestOriginalMode2EmptyPARAMAndFrozenRegisterGateToStop` и `TestOriginalMode2ZeroRecordPARAMNoSyntheticStageOrValue` — RAW/SHA, Task2 Stage, 10-канальные кольца ADC/TACH, пустой PARAM, снятие Freeze, AUX, (0x3100), Stop, локальные writer-ы, встроенный журнал.
- Python: `test_original_task2_valid_28byte_empty_param_keeps_stage0` и `test_original_go_param_gate_raw_replay_frozen_values_skip_and_sha` — повторное чтение RAW, SHA, пропущенный/принятый (0x3100), отказ при подмене Freeze или хеша кадра.
- Общая `MVKView Compatible - Windows EXE` CI: Linux Go, Linux Core, Windows Core/Qt, Windows QPA и Windows EXE на **одном финальном SHA**. Не называть исправления PASS до получения успешной сборки на нём.

## Незакрытые критерии оригинального полного приёма

- Полный цикл на физическом МВК01, в том числе SetRate с отдельным разрешением, DENIED/timeout/reconnect и Stop с фактическим пакетом в Wireshark.
- Точные оригинальные `GetSignal`, `GetSpectrum`, FRange после первого PARAM, сравнение тех же отсчётов (не соседних измерений).
- Оригинальные Win32 имена файлов/часы, `TMvkCellList.GetValueText` (и advanced titles), BIN/TSXML/CSV.
- Приёмка всех визуальных и событийных состояний окон и меню на живом приборе.

**Оценка:** структурная/алгоритмическая идентичность этих конкретных ветвей подтверждена исходниками и синтетической регрессией; `original_delphi_compatibility_verified=false` до независимой аппаратной и парной Delphi-сверки.
