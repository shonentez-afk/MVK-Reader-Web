# Stage111Z31F — TCo2Draw source grid/ink/blend and reversible Qt source overlay

Дата: 05.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.

## Прочитано приватно и НЕ опубликовано

Исходные IDR-дизассемблированные `_Unit115.pas`, `_Unit128.pas` из предоставленного `Projects.7z` проверены локально. Ни один оригинальный PAS/IDP/DFM/EXE, пользовательские PNG/Power/Y/BIN и содержимое прибора не записываются в GitHub или CI.

**Ключевая поправка Stage31F:** исходная сетка — **НЕ Win32 GDI pen**. `TQGrapher.Draw:007CACB3..007CACD4` создаёт собственный `TCo2Draw` с RGB `FFFFFF`; `007CACFC..007CAD0B` устанавливает RGB `C0C0C0`. `TCo2Draw` хранит собственный `TBitmap` и адреса `ScanLine` строк, рендерит `MoveTo/LineTo` программно до рисования series (`007CB12F+`). Участки `007C98B4/007C9A30` используют геометрию линии и `sqrt(abs(distance))` для 3 соседних по перпендикуляру пикселей; `007C9808` смешивает каналы с коэффициентом `min(1,sqrt(abs(distance)))` по `TRUNC(ink + (old - ink) * factor)`. При факторе 0 получается краска C0, при 1 — прежний пиксель. Точная native x87 округлённость всех координат/пикселей остаётся OPEN.

**Подписи — другой тракт.** `007CACE4..007CACF9`: оффскрин `TCanvas.Brush.Style=bsClear`, `TFont.Assign` исходного `TCanvas.FFont`. `007CADE1..007CAE29` рисует подписи Y в `(PixelLeft - TextWidth - TextOffset, Round(ytos) - TextOffset)`; `007CAF09..007CAF5F` подписи X — `(Round(xtos) - TextWidth/2, PixelBottom + TextOffset)`. `TextOffset` берётся из ширины символа «0» того же `TCanvas` в `007CA4E8..007CA4F4`. Runtime шрифт/FontMetrics/Windows DPI и реальный PixelRect оригинальной VCL не измерены. DFM Tahoma -13 PPI96 — только дизайн.

## Реализовано в нашем коде

- `mvk_compatible/core/tco2draw_grid_source.py`: единственный реестр исходной палитры, порядок сетка→кривая, источник TextOut и независимые чистые кандидаты смешивания RGB и координат подписи; есть честные флаги неподтверждённого runtime-паритета.
- `mvk_compatible/desktop/main_window.py`: при включении **уже существующего исследовательского** переключателя TQGrapher 10×10 на **проверенном локальном исходном Power/Y** оси используют прежние source-derived 10×10/Unit114 подписи, а сетка теперь имеет отдельные 22 линии RGB `#c0c0c0` на белом фоне под кривой; обычная полупрозрачная сетка pyqtgraph отключается. Это не смешивает два набора линий.
- При изменении zoom Qt-линии перестраиваются по текущим диапазонам source Single без дублирования. При отключении, переходе в архив или выходе из эталона все исследовательские QGraphicsItem удаляются и стандартные Qt сетка/подписи восстанавливаются.
- Qt InfiniteLine width1 — **только изображение исходных мест и цвета**. Он **НЕ воспроизводит** точный `TCo2Draw` coverage, сдвиги Font/TextOut и оригинальную физическую DPI-пиксельную геометрию. Всё это остаётся явным OPEN, режим по умолчанию OFF.
- Спектр, 4 режима GetSpectrum, исходный Float32 131072/131072, summary, курсор, Native Go R6.1, `main`/Web, 8ADC/TSXML/RAW не менялись.

## Регрессия / приёмка

- `tests/test_stage111z31f_tco2draw_source.py`: цвет/порядок, исходная формула RGB, границы и fail-closed, TextOut anchoring, отсутствие ложного статуса pixel parity.
- `tests/test_stage111z31f_qt_tco2draw_grid.py`: синтетический original-reference-shaped JSON/Power/Y, ровно 22 линии и исходный RGB, Y/summary неизменны, zoom без двойных линий, выход в архив чистый.
- В основной Windows Core suite включены все тесты, а в шаг `QT_SCALE_FACTOR=1.5` добавлен новый Qt test file. Нужны подтверждённые PASS всех трёх GitHub Actions jobs и проверка нового EXE SHA; **при написании отчёта SUCCESS для нового коммита ещё не заявляется**.

## Следующий Stage111Z31G — технический и визуальный gate

1. Прочитать исходные `TCo2Draw` scanline clipping/rounding и отдельно восстановить deterministic bitmap-raster (без изменения FFT и обычного графика).
2. На Windows со старой MVKView и нашей новой PREVIEW сравнить **одинаковый Tag0** с закрытой research-панелью, одинаковым viewport/FRange/mode/X/Y и измеренным масштабом каждого процесса; отдельными скриншотами проверить tick labels и 1px grid. Без доказанных 1:1 canvas/dpi/font нельзя включать исследовательский цвет/сетку в обычный спектр.
3. Перейти затем к исходному TQGrapher series plotting, координатам/cursor/scrollbars; завершить GetSignal same-run, PageStatus и аппаратные длинные тесты по master plan.

**Обязательное:** не запрашивать повторные Tag0..Tag3 Power/Y, FFT, Z8/Z10 или Stage108–109 для уже сверенного случая. Источники и файлы пользователя остаются приватными.
