# MVKView 1.0.47 — сквозной аудит IP → Измерить → приём → все вкладки → Stop

**Дата:** 19.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.
**Аудитный тест:** `mvk_compatible/tests/test_mode2_original_five_tabs_one_run_audit.py`, коммит `52c5a2e567aacc8e844ef47ed71173b8f698563f`.
**CI нового теста:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44485471309 (запросить окончательный результат).
**Предыдущая кодовая матрица:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44481780490 — 5/5 SUCCESS (до добавления аудитного теста).

## Проверенные ОРИГИНАЛЬНЫЕ источники, совместно и локально

Все приватные файлы действительно проверены заново локально, НЕ по одному GitHub-манифесту:

- `Projects.7z`, SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`: извлечены 5 исходных `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`; каждый размер и SHA256 **5/5 точно совпадает** с `source_files` из SQLite.
- `mvk_idr(1).sqlite`, SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`: `PRAGMA quick_check=ok`; заново просмотрены компоненты TPageControl, 7 TTabSheet, 15 tcStatus, события и адреса.
- `mvkview.idp`, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`: оригинальная структура TMVKThread, TMvkChannelStorage, поля FRange, x87 и локальные FIR банки.

**Запрещено** копировать эти приватные PAS, DFM, IDP, SQLite, FIR, RAW/PCAP, runtime дампы в публичный GitHub, CI или артефакты.

## Подтверждённая исходная последовательность

Оригинал: `bTaskConnectClick 00848E78` → `00846AD4(Mode=2)` → конструктор десяти `TMvkChannelStorage` (8 Float32 ADC + 2 TACH Byte; `0x200000` элементов/буфер) → `SetTabVisible` PageStatus 00846D2C, PageAdc 00846D3C, PageSpectrum 00846D4C, PageFile 00846D5C → **условный** PageCalib 00846D74, видим только `FactoryMode [Tmvkform+628]!=0` → `pnMeasure.Visible=True` 00846D84 → `TMVKThread.Create` 00846DCC → `mRate1Click` 00846DF7 → **`SetActivePage(PageStatus)`** 00846E0E → кнопка «Отключить», `tmInterfaceUpdate` 20 ms → PageStatus dispatch через 00847248.

**В обычном режиме фактически открываются ПЯТЬ:** PageStart, PageStatus, PageAdc, PageSpectrum, PageFile. `PageConfig` скрыта; `PageCalib` скрыта без FactoryMode. У исходного FactoryMode два отдельных пути: приватное `Advanced\Mode` в оригинальном конфиге или действие `imLogoMouseDown` с комбинацией модификаторов **и** UserQuery=Yes; это не автоматический шестой таб и не разрешение выполнять калибровку железа. Всего в DFM 7 TTabSheet.

Оригинальный `tmInterfaceUpdateTimer 0084F7C8 → 00847248` каждые ~20 ms вызывает обновление **ТОЛЬКО АКТИВНОЙ** вкладки: PageConfig 008472D0, PageStatus 008475BC, PageAdc 00847EAC, PageSpectrum 00848148, PageFile 0084845C, PageCalib 00848688; затем 008486F4 для панели измерения, если видима. `PagesChange 0084ECF0` немедленно обновляет активные графики. `tcAnyChange 0084F708` связывает выбранный АЦП PageAdc и PageSpectrum.

## Табличная сверка каждой вкладки во время Mode2

| Вкладка | Исходный оригинал | Наше Qt/Go (проверено по текущему коду) | Остаток до оригинала |
|---|---|---|---|
| **PageStart / Задачи** | IP из `edIpAddr`, Mode2 создаёт приёмник и выбирает SetRate, вторая команда «Отключить» | `OriginalStartController` вызывает `enter_measurement_mode`, открывает пять вкладок и ставит PageStatus до Native TCP; затем отдельное разрешение оператора | Оригинал подключается из своего обработчика автоматически. У нас дополнительный защитный диалог/подтверждение, корректный по безопасности, но не идентичный 1:1. Исходные тайминги и точные Status тексты не приняты |
| **PageStatus / Расчётные данные** | `tcStatus` 15 режимов, четыре `TStringGrid` + `chResult`, исходные регистры и `GetValueText` | 15 переключаемых режимов есть; в **LIVE режим 0** показывает 15 подтверждённых системных полей (по Valid WORD Go); source 14 внутренних StatusCells отделены от 15 видимых полей. | **ГЛАВНЫЙ ФУНКЦИОНАЛЬНЫЙ ПРОБЕЛ:** LIVE режимы 1–14 по умолчанию не получают исходных показателей АЦП/контроля/43 полос/TACH, `source_status_projection(index,None)` показывает UNKNOWN; корректный обратный парсинг полного набора PARAM/VALUES, 24×8, 43×8, 6×2 TACH и родной `GetValueText` пока не выполнен |
| **PageAdc / Временной сигнал** | `tcAdc` 8 каналов, `GetSignal`, GetAdjustedEnvelopeLength, FIR/IQ, RMS, масштаб X/Y, SourceCursor, Freeze | Go single-socket original Float32 2²¹ ring, Fs/Freeze/FRange gate, SHA-checked полные исходные GetSignal окна. Отдельный Qt FIR worker и полный курсор в модели. Без подтверждённого Go ring — только обозначенный provisional preview | **Нет 1:1** оригинального x87 FIR/RMS/масштаба/точного HTag LastProcessedPos/TQGrapher cursor, полного timestamp и всех исходных подписей на живом приборе. Имеется безопасный локальный кандидат, не runtime Delphi |
| **PageSpectrum / Спектр** | `tcSpectrum` 8 АЦП, `GetSpectrum` и 4 Y режима, `bSpecLines` pre-FIR, post-FIR FFT, Hann, I/Q, скроллинг, курсор, Copy/Save | Есть 8 вкладок, оригинальные пункты меню N/режимов; full source-ring FFT, FIR/IQ кандидат с локальным IDP, четыре Y-режима; недостоверный результат скрывается | **Нет 1:1** x87 Hann/FFT/Power/интеграции и оригинальной живой экранной геометрии/курсора; **LIVE `bSpecCopyValue` и `bSpecSaveValue` отключены**, т.к. число ещё не аттестовано как Delphi |
| **PageFile / Параметры записи** | 10 масок ADC/TACH, 43 SPEC + 73 VALUES, чекбоксы имени/папки/XML, `WriteData`/ `WriteValues`, локальное время | Маски 10/43/73 и 2 action tabs работают; единый Go TCP действительно пишет только подтверждённые RX/0x3100, метки начала/конца по frame boundary, отдельные RAW и SHA | Точное `TABLE`/ `VALUES` CSV, `GetValueText`, **собственные** имена BIN, TSXML CP1251, Windows местное время, физическая байтовая 1:1 приёмка не завершены |
| **Общая `pnMeasure`** | FreezeUpdate, SetRate, `bWriteTable`, `bWriteAdc`, `bWriteValues`, `lbStatus`; 20ms GUI timer | Freeze gate в одном Go приёмнике без остановки RAW; SetRate 36B между пакетами на том же TCP только после явного разрешения; source WriteData/Values, Stop, статус ошибок | **LIVE `bWriteTable` пока отключена** (доступен только verified offline TABLE CSV), оригинальная CSV/текст приборных вычислений отсутствует; реальный SetRate/ACK/DENIED/timeout/status/Freeze/Stop не подтверждены на МВК01 |
| **PageConfig / Настройка** | Не открывается при Mode2, доступна в отдельной задаче Mode4/6 | Скрыта по умолчанию при «Измерить» | Полный доступ к исходным функциям Task0 конфигурации вне Mode2 — отдельная задача, не блокирует обычную проверку пяти вкладок |
| **PageCalib / Калибровка** | Скрыта по умолчанию, **открывается в Mode2 только при FactoryMode=True** | Форма и локальная офлайн-рабочая область есть; стандартный Mode2 не открывает; calibration hardware отключён | **FactoryMode-включение из конфигурации/secret logo и действия генератора/калибровки не восстановлены**; это защищённый отдельный операторский режим, не часть обычного безопасного Mode2 |

## Приём сигнала и ошибки — что доказано / что ещё не доказано

**Есть программно (localhost + CI):** оригинальная 36-байтная SetRate FIFO между application packets на единственном сокете; Task2 Stage0/1/3; 8 ADC/2 TACH; порции переменной длины; valid-unselected-Fs в RAW, но не в выбранном кольце; Freeze без остановки RAW; 2²¹ live Float32 FRange=1 ring; GetSignal/GetSpectrum/полные HTag окна + source SHA; RAW и SHA, packet-header errors, denied/reconnect с новым TCP state, WriteData/WriteValues 0x3100, Stop и fail-closed против старого превью.

**Не подтверждено реальным прибором:** байтовые пары SetRate/ACK/DENIED/Status0 и interleaved TX/RX на МВК01; точные оригинальные ConnectTimeout=1000 ms, ReadTimeout=5000 ms и Stop timing; все переключения Fs, Freeze и file-closure при packet errors/reconnect; физический предел/взаимосвязь ring и GetSignal; оригинальный NUMERIC (особенно FIR/Hann/FFT), оригинальная частотная сетка и локализованный `GetValueText`; оригинальные TIMESTAMP, BIN, TSXML/CSV. **Гипотезы и синтетические тесты НЕ означают физический Win32 1:1.**

`original_delphi_compatibility_verified=false` остаётся.

## Новый сквозной UI-тест

`test_mode2_original_five_tabs_one_run_audit.py` — один реально созданный `MainWindow`, 5 доступных вкладок после кнопки до TCP (Status active), 7 исходных компонентов в дереве, запрет Config/Calib при FactoryMode=0, 10+43+73 исходных чекбокса, 15 PageStatus субрежимов, поочередное переключение пяти реальных QWidget, один синтетический Go session/status/preview, PageStatus→ADC→Spectrum→File→ADC, затем второй клик Stop, запрет позднего повторного отображения графиков, очистка без переноса предыдущего архива. Приватный исходник или реальный МВК01 не требуется.

## Следующий ЕДИНЫЙ крупный пакет без micro-stage

1. **LIVE 15 PageStatus modes**: сохранять в Go по исходному выбору Fs/Freeze/Stage полный `PARAM` register-image с Valid provenance, независимо проверять RAW и исходные адреса `GetValueText`; 8 АЦП, 43 полосы, 2 TACH; не заполнять отсутствующие вычисления вымыслом.
2. **LIVE GetSignal и GetSpectrum 1:1**: парные исходные pre/post FIR/x87 Hann/FFT/Power/Y, FRange, точные масштаб/курсоры, бины и средние, Copy/Save; приватный оригинальный IDP только на ПК оператора.
3. **LIVE WriteTable/Data/Values 1:1**: исходные расчётные CSV, BIN, TSXML, имя, Win32 время, closed/reconnect/Stop bytes и SHA, без смешения с forensic exporter.
4. **Финальная приборная парная приёмка**: оригинал 1.0.47 и совместимая программа на одном физическом МВК01 и совпадающем RAW с 8ADC+2TACH+PARAM, SetRate разрешён отдельно, положительные/отрицательные ветки, без Flash/IP/Reboot/Task3/4/5.

Ветка `main` не затронута; никакой аппаратной отправки не делалось.
