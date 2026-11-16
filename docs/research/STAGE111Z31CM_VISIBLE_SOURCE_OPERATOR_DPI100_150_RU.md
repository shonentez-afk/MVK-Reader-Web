# Stage111Z31CM — настоящий пользовательский экран спектра: Qt DPI100/150, BIN E2E, F12

**Дата:** 16.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.
**ИСПОЛНЯЕМЫЙ и ПРОВЕРЕННЫЙ SHA:** `4b279153ec258238a5c05e874a007de41b310fde`.
[GitHub Actions #43785268848](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43785268848) — **SUCCESS 3/3**.

## Фактическая приёмка

- Linux offline Core: **1954 PASS / 108 SKIP**, 1 warning, 30 subtests.
- Windows Core: **2127 PASS / 7 SKIP**, 1 warning, 30 subtests.
- Windows Qt smoke: **49 PASS**.
- Windows real PySide6 Qt tests with effective DPR 1.5: **144 PASS**.
- Отдельный нормальный операторский UI при Windows **DPR=1.0: 1 PASS**; те же сценарии входят в пакет Windows DPR 1.5.
- Собран автономный Windows EXE с встроенным исходным Native Go R6.1, verified manifest/actual SHA совпадают.
  [EXE artifact #14190885654](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43785268848/artifacts/14190885654):
  ZIP **69 029 566 B**, до **30.11.2026**; EXE SHA256
  `8358f5230a8d261d551af461b741473fe40a4d226d4277e5bfb6849d59b237c5`.
- [Новая QA-галерея #14190148095](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43785268848/artifacts/14190148095):
  10 реально снятых `QWidget.grab()` синтетических экрана + JSON, 100/150%,
  209 576 B, до **23.11.2026**. Более ранний отдельный BJ/CB gallery
  [#14190396675](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43785268848/artifacts/14190396675)
  **НЕ** надо путать с новой галереей CM.

## Реальное изменение исполняемого приложения

`desktop/source_visual_skin.py`: после выключения технического режима F12
закрываются оба исследовательских дока, дополнительная Qt-панель и вторичная
техническая навигация. Они ранее могли остаться видимыми и смещать PageSpectrum
после выхода из режима F12. Ядро/FFT и приватные данные не затронуты.

В `tests/test_stage111z31cm_qt_source_operator_path.py` добавлен один
полный пользовательский путь **без подмены `session=object()` или
`_full_spectrum`**: создаётся только синтетическая Single BIN/TSXML,
`open_archive` открывает `DirectBinSession`, реальный пользовательский
`PageSpectrum` и `refresh_spec` выдают полный `NFFT=65536/N2=32768`
Float32; затем идут `bSpecVScale`, dense→sparse→dense, источник курсора,
**нажатия реальных Copy/Save**, флаги НЕ КАЛИБРОВАНО,
`F12` on/off, отсутствие аппаратных команд и SHA исходного BIN.
SHA полного Y при DPR1 и DPR1.5 одинаков:
`9bd646b8f91f4ff8581afe511208d37466e13162f04aefd77bc2fddcb4fb987a`.
Предыдущая общая 4-режимная реальная сквозная проверка **уже существует**
в `test_stage111z31o_direct_bin_gui_e2e.py` — не писать её заново.
`test_stage111z31n_qt_archive_graph.py` отдельно проверяет полный N262144
в инжектированной синтетике: её НЕ выдавать за новый оригинальный BIN runtime.

На нормальном старте видна только `PageStart`, с архивом только
`PageStart/PageAdc/PageSpectrum`. **Все 7 остаются смонтированными**,
дополнительные доступны через исходные действия и F12. ВАЖНО: второй ряд
вкладок на спектральном кадре является оригинальным внутренним
`tcSpectrum` (каналы) из `mvkform.dfm`; не удалять его как «лишний Qt таб».
`pnMeasure` скрыта в offline; `pnView` 48 логических px; все 9 оригинальных
DFM контролов и отдельная Qt графика работоспособны.

## Визуальная граница приёмки — ОТКРЫТО

- Скриншоты получены под `QT_QPA_PLATFORM=offscreen`; при 100% физические
  1360×850, при 150% физические 2040×1275 из одного логического 1360×850.
  Источник `core/original_live_whole_paintbox.py` / TQGrapher не переписан.
- На реальных снимках offscreen **кириллица и даже числовые подписи нарисованы
  квадратиками**, хотя `QRawFont.fromFont(Tahoma).supportsCharacter()`
  в отчётах возвращает True. Это расхождение виртуального изображения,
  НЕ доказательство дефекта в нативном Windows EXE. Проверить native QPA
  Windows при реальном desktop rendering, а не считать offscreen достоверным.
  Не вшивать приватные шрифты.
- Геометрия исходной DFM применяется, 3 top-level tabs и 177px боковая панель
  подтверждены, но **полного 1:1 пиксельного сравнения с работающей Win32
  MVKView 1.0.47 на одном оригинальном BIN/Y/окне/DPI ещё нет**.
- Графики CI основаны на СИНТЕТИЧЕСКОМ BIN, а не реальном оригинальном файле.
  Никаких новых original x32dbg/FIR full Y или аппаратных проверок не было.
  Исходные PAS/DFM/IDP/EXE/BIN/снимки пользователя НЕ опубликованы.

## Следующий крупный P0, не распыляться

1. Устранить расхождение между настоящим Windows GUI-render и offscreen QA:
   добавить диагностическую проверку нативного Windows шрифта/физических
   прямоугольников; не путать автоматические glyph boxes с EXE.
2. На **уже имеющемся оригинальном эталоне** проверить физические
   рамки TQGrapher, тики, курсовую координату и самое главное **реальное
   поведение X/Y, dense/sparse и Copy/Save**. Same-BIN/same-channel/same-window/
   same-mode/same-FRange, иначе DATA_GATE.
3. После доказанной нормальной страницы спектра закрыть original envelope
   post-FIR/full Y при том же окне, затем GetSignal/временной сигнал,
   приборные показатели и остальные страницы. Не начинать заново FFT
   131072/131072 Power→Y, FRange writer/reader, Hann, исходные 10×512 FIR
   и Native R6.1; их прежние принятия сохраняются.

**Без разрешения оператора не запускать оригинальный прибор и не выполнять
Upload/Download/Reset/CalibStart/Write/Register.**
Данный отчёт и последующий handoff — ТОЛЬКО DOCS; не новый EXE SHA.
