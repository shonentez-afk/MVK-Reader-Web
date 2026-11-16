# Stage111Z31CR — original connected MVKView: 5 корневых вкладок, 15 режимов статуса, BIN-проводка и LIVE-панель

**Дата:** 16.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.  
**Принятый исполняемый source commit:** `3e105fd407d6fa0280781a69ebeebd5d529fcc90`  
**[CI Actions #43801008576](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43801008576) — 4/4 SUCCESS.**

## Прямые оригинальные свидетельства

Оператор прислал три изображения непосредственно оригинальной
**ТПО МВК 1.0.47**, НЕ скриншоты нашей копии: подключённое
окно с PageStatus, Windows common диалог `Открытие` со
списком исходных BIN для АЦП1–8 и исходный PageStart
без измерения. Дополнительные `mvk_original_empty_ui_* (3)`
повторяют старый **idle-only** захват и не заменяют новые
наблюдения connected состояния. Исходные изображения содержат
частные сведения и в публичную ветку не отправлены.

**Оригинальные режимы TPageControl:**
- IDLE: одна вкладка «Задачи».
- ОФЛАЙН-архив: «Задачи», «Временной сигнал», «Спектр»
  (ранее подтверждённый отдельный источник).
- CONNECTED/LIVE: **ровно пять** корневых вкладок
  **«Задачи» — «Расчетные данные» — «Временной сигнал» —
  «Спектр» — «Параметры записи»**. PageConfig и PageCalib
  остаются созданными в 7-страничном Delphi DFM, но не
  выступают дополнительными исходными вкладками всегда.
  Гипотеза прежнего `unknowns` «оригинал только с одним АЦП»
  **ОПРОВЕРГНУТА**: пользователь явно показал
  `АЦП 1 … АЦП 8` и `Тахометр 1/2` на одном экране.

**15 внутренних вкладок «Расчетные данные»:**
«Состояние системы», «Контроль», «Все каналы (СКЗ)»,
«Все каналы (пик)», «Все каналы (пик-пик)»,
«АЦП 1…8», «Тахометр 1», «Тахометр 2».
Оригинальный выбранный режим «Состояние системы» —
таблица `Наименование параметра | Значение`, 15 имён:
серийный номер устройства; версия внутреннего ПО;
системные ошибки; время работы; размер карты памяти в КБ;
MD5 внутреннего ПО DSP; состояние контроля и неквитированные
события по группам 1/2; счётчик процедур расчёта; счётчик
запросов Modbus; последний адрес Modbus; последнее число
регистров Modbus; число активных клиентов Modbus.
Нули и `0.0.0.0` на оригинальном снимке **наблюдаемы, но
НЕ являются доказанными измеренными значениями R6.1**
и не переносились как фиктивные результаты Qt.

**Нижняя панель connected оригинала:**
`Пауза приема`, `ЧД 65536 Гц` с меню,
`Запись таблицы`, `Запись сигнала`,
`Запись значений`, `Подключен к прибору`.
На оригинальном снимке три кнопки записи отключены.
Снимок не устанавливает безопасные командные контракты
`SetRate/Write` и не разрешает аппаратные операции.

**Windows common dialog после «Загрузка сигнала из файла»:**
заголовок «Открытие», фильтр «Двоичные файлы временного...»
и восемь отдельных однотипных BIN на АЦП1…8 с общими
серийным номером и timestamp. Нажатие кнопки открывает
диалог НЕМЕДЛЕННО, а не переносит на самостоятельную
разработческую PageFile.

## Действующие изменения Core + Qt

1. `core/original_runtime_tabs.py`: строгий параметр
   `live: bool`, `ORIGINAL_LIVE_VISIBLE`, 5-страничный
   исходный порядок; прежние режимы IDLE=1/ARCHIVE=3
   сохранены. `desktop/source_visual_skin.py`
   использует реальное `MainWindow._live_active`.
   После `_end_live_capture` выполняется исходный
   возврат к `PageStart`, без остаточной PageFile tab.
2. `core/original_ui_form_contract.py`: настоящие
   русские заголовки корневых страниц; точный
   `QMainWindow.windowTitle = ТПО МВК 1.0.47`.
   `core/original_pagestatus_source.py`: все 15
   исходных операторских подписей без служебных
   `0...14` индексов, но сами типизированные Core
   `MODE_NAMES` и расчётные dispatch-contracts не сломаны.
3. `desktop/original_start_ui.py` Mode1 `bTaskView`
   теперь вызывает `MainWindow.choose_archive` прямо
   из PageStart. `MainWindow.choose_archive` открывает
   настоящий нативный `QFileDialog.getOpenFileName`
   с заголовком «Открытие» и первым BIN-фильтром.
   Отмена ничего не меняет; выбранный BIN/TSXML либо
   ZIP передаётся в ранее проверенный Core и графики.
   `DirectBinSession.open` ищет одноимённую
   original `MVK...-ADC[1..8]-timestamp.bin`
   группу, требует парные TSXML, согласованную Fs
   и не выдумывает калибровку. `PageFile` и
   оригинальные файловые обработчики остались
   функциональны при явной навигации.
4. `core/original_connected_status.py`: реальные
   15 имён + два заголовка; `ConnectedSystemStatus`
   получает только валидированный read-only Go
   `MVK_NATIVE_R6_LIVE_STATUS_V1` (phase RECORDING,
   decoded frames>0, status not stale). Эти факты
   разрешают показать **транспортное** `Подключен к прибору`
   и зелёный индикатор, но НЕ лицензируют
   серийник/firmware/MD5 DSP/uptime памяти/Modbus.
   Все 15 system values пока `—` (UNKNOWN);
   Go кадры не отображаются как счётчик процедур
   прибора, Go elapsed не считается uptime прибора.
   При невалидном/просроченном status UI теряет
   признак подключения, не хранит чужой сеанс.
5. `desktop/native_capture_dialog.py` выдаёт
   `statusReady/statusInvalid` ИЗ существующего
   локального проверенного Go status JSON, не
   открывает дополнительный приборный TCP.
   `desktop/main_window.py` передаёт подтверждённый
   статус существующей `OriginalRootShell`.
   `desktop/original_shell.py` рисует настоящую
   двухколоночную таблицу и все 15 source вкладок,
   с рабочей навигацией; для известных ZIP/AUX/VALUES
   остаются реальные source показателей/43 полос,
   для Direct BIN неизвестные значения не домысливаются.
6. `desktop/original_measure_controls_ui.py`:
   оригинальные подписи нижних кнопок,
   `Пауза приема` реально переключает
   **отображение** LivePreview, не уничтожая RAW;
   `ЧД` показывает полученный валидированный
   rate без подмены исходного `SetRate`.
   Три Write-кнопки в LIVE остаются отключены,
   поскольку аппаратные операции не восстановлены.
   Проверенные OFFLINE-экспорты прежнего Qt не
   выдаются за оригинальный приборный Write.
7. **Никакого исследовательского UI в обычном EXE:**
   не устанавливаются F12/Ctrl+D developer shortcuts,
   исходный root shell не показывает дополнительные
   engineering вкладки/панели/notes/CSV bars.
   Только явно выставленная среда
   `MVKVIEW_DEVELOPER_UI=1` включает
   разработческое меню для QA (не штатный UI).
   Локальные оригинальные images из DFM по
   `MVKVIEW_PRIVATE_SOURCE_DFM` загружаются без
   включения developer режима и без публикации
   проприетарных изображений.

## Численная и UI приёмка

В реальной Windows CI проверена
`QTest.mouseClick(bTaskView) → common native dialog
Cancel → QTest.mouseClick(bTaskView) → synthetic BIN/TSXML
→ DirectBinSession → full FFT/Adc/Spectrum`.
Далее самостоятельный synthetic Native LIVE
`_begin_live_capture → 5 root tabs → 15 status tabs
→ confirmed transport JSON → stale status → disconnect
→ 1 root tab`. Никаких реальных сокетов/команд.
Старые тесты, нажимавшие Mode1 как скрытый
переход PageFile или ожидавшие старый заголовок
без номера версии, обновлены по оригиналу.
Произведён полный Windows PASS, не только isolated QA.

| Job | Итог |
| --- | --- |
| Linux Core | **1960 PASS**, 113 SKIP, 1 warning, 30 subtests |
| Windows Core | **2143 PASS**, 7 SKIP, 1 warning, 30 subtests |
| Windows Qt smoke | **49 PASS** |
| Windows Qt offscreen DPI100 | **11 PASS** |
| Windows Qt offscreen DPI150 | **154 PASS** |
| Native Windows QPA DPI100 | **11 PASS** |
| Native Windows QPA DPI150 | **11 PASS** |
| Windows onefile PyInstaller+Native Go R6.1 | **SUCCESS** |

[EXE Artifact #14196404338](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43801008576/artifacts/14196404338),
ZIP **69 050 753 байта**, срок хранения **30.11.2026**.
EXE SHA-256
`11779b0a70c7223436a4232a04f95110bf63bf9dce5e328e8e39a9f0d32003e7`;
GitHub steps подтверждают `sha256_actual_exe_matches_manifest=true`.
[Native Qt 100/150 QA #14196397635](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43801008576/artifacts/14196397635)
хранится до **23.11.2026**, содержит только
синтетические Qt скриншоты/JSON, не оригинальные BIN/PNG.

## Что честно ещё не восстановлено

- 15 реальных исходных device system регистров,
  значения firmware/serial/MD5/Modbus/памяти и
  источник static/updated rows: Go Native R6.1
  пока валидирует транспорт и некоторые ADC
  sensor status, не все 15 оригинальных системных
  параметров. Не заменять их нулями из скриншота.
- Оригинальный `TMVKThread.SetRate`/частотное меню
  и аппаратные `WriteTable/WriteAdc/WriteValues`,
  Reset/CalibStart/Upload/Download: нужен
  подтверждённый исходный protocol/state contract
  и оператор, а не вызов придуманной команды.
- Полный визуальный 1:1 connected оригинал
  1920×1020/150% vs native Windows CI 1440×870:
  top BWTable/BWOsc/BWSpec/BWEdit icon bytes,
  точные шрифты/строки, выделенная первая строка
  и все PageFile панели ещё требуют проверки.
  Уже есть opt-in источник private image collection:
  распространить на остальные оригинальные BW*
  только локально, без коммита vendor data.
- Для original raw `*.bin` строго требуется
  валидированный парный `TSXML`/Fs. Если его
  нет, нельзя молча строить ложную частотную шкалу.
- Паритет 15 активных Source-mode вариантов
  и PageFile с оригинальной запущенной MVKView
  на одном реальном измерении, плюс full
  envelope post-FIR/physical Y, ещё не закрыт.

**Следующий большой Core+UI этап:** восстановить настоящий
read-only system/status register projection, полную
работу PageFile и control/record transitions
без приборного WRITE, затем original same-data
Adc/Spectrum/Envelope E2E. Не тратить цикл
на уже принятые FFT, Hann/FRange/Power→Y и
фон/шрифты вместо исправления реальных
работающих функций.
