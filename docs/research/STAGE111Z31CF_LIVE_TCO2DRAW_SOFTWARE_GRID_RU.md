# STAGE111Z31CF — настоящий TCo2Draw software-grid в обычных PageAdc/PageSpectrum

**Дата:** 13 ноября 2026 · **Приёмка:** принята часть графического восстановления. Полная копия оригинального Win32 MVKView 1.0.47 НЕ доказана.

## Подтверждённая база

Локально изучены приватные операторские `Projects.7z` (`_Unit115.pas` TQGrapher/TCo2Draw, `_Unit128.pas` обработчики, `mvkform.dfm` обе страницы). Исходный `TQGrapher.Draw` в 007CAC68..007CB4AA рисует белый bitmap, программную TCo2Draw #C0C0C0 сетку горизонталь→вертикаль, затем TCanvas TextOut, далее чёрную серию, рамку и bitmap в видимый TPaintBox. Сама software-линия берётся из разобранных `007C9808/007C98B4/007C9A30`: три соседних пикселя на шаге, factor=min(1,sqrt(abs(distance))), исходный Float32 blend. Эти модули уже были в репозитории как **исследовательский** reference растр. Live Qt до CF рисовал серые линии простым QPen, что не соответствует программному антиалиасингу оригинала.

## Код — общий Core + действующий Qt

- Новый `mvk_compatible/core/original_live_software_grid.py`: один безопасный bitmap-contract на текущих двух диапазонах ViewBox, размерах в **Qt logical px**, с ограничением 2,5 миллиона пикселей. Использует источник `original_live_grid_cursor.py`, `tco2draw_raster_candidate.py`, фон RGB255, software gray RGB192 и исходный порядок Y grid перед X grid; возвращает RGBA, checksum SHA256 и явные неподтверждённые Win32 parity-флаги. Функция не принимает BIN, FFT, GetSignal или калибровочные параметры.
- `mvk_compatible/desktop/source_live_grid.py`: рабочий `SourceLiveGridOverlay` у настоящего ViewBox **обеих** страниц делает QImage из RGBA source raster (правильное переворачивание строк при Qt +Y вверх), отрисовывает **под** кривой, хранит сигнатуру текущего range+логического размера. `QTimer(0)` сворачивает повторные геометрические события и запрещает дорисовывать старый bitmap при pan/zoom/resize. При неподходящем размере остаётся безопасный прежний Qt кандидат. `SourceLiveFrameOverlay`: чёрная рамка после данных, до XOR курсора; на данный момент Qt cosmetic candidate, а не единый scanline-битмап оригинала.
- `mvk_compatible/desktop/source_plot_geometry.py`: обе рабочие `SourceGeometryPlot` постоянно хранят grid/frame даже после `PlotItem.clear`. Переключение отдельного research composite скрывает **оба** live слоя, чтобы исключить двойную сетку/рамку; возврат включает их. Ни оффлайн-кривая, ни полный N/2 FFT/Power/Y не заменены bitmap-данными.
- Новые `test_stage111z31cf_software_grid_core.py` и `test_stage111z31cf_qt_live_software_grid.py`: исходная последовательность software blend и формат RGBA, fail-closed при 0/oversize, действительные живые PageAdc/PageSpectrum с синтетическим ZIP, смена масштаба, сигнатура cache, отсутствие старых изображений, SHA ZIP и битовая неизменность Float32 FFT. Qt E2E включён в обязательный Windows DPI150 workflow.
- Исправление тестов: TCo2Draw дробно окрашивает пиксель между RGB192 и белым. Проверка ровно RGB192 была ложной; сохраняется уже принятая формула исходного alpha-blend и проверяется RGB192≤value<255 хотя бы на одном пикселе. **Никакой** пересчёт спектра/FIR/FFT или изменённый Source-код из-за QA не потребовался.

## Приёмка CI и EXE

Исполняемый `4d87093c7dbcfb1e218c8b62cfd2adf2e17df066`. [Actions #43382496581](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43382496581) **3/3 SUCCESS**:
- Linux Core **1855 passed / 98 skipped**, Windows Core **2007 passed / 7 skipped**, обычный Windows Qt **49 passed**, Windows Qt при проверенном 150% DPR **123 passed**.
- [Windows autonomous EXE #14018035147](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43382496581/artifacts/14018035147) — ZIP **68 953 857 байт**, до **27.11.2026**. EXE SHA256 по проверенному манифесту `371618c5bce34287f64dca85b6448dc77c856b98d28be45e0f705722b81e7c05`. ZIP SHA256 `f1b41f3568758d9d6f070337468d50195894fd06c1c8e3f4bd6588f49517d2d8`; GitHub PE/header and build manifest verification passed. Перескачанный ZIP отдельно в этой сессии не сравнивался.
- [Synthetic UI screenshots DPI150 #14016858220](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43382496581/artifacts/14016858220) — **668 682 байта**, до **20.11.2026**.
- Производительность: Windows Core этап занял **172.65 с** против ранее **87.03 с**, Qt DPI150 **128.19 с** против **54.11 с**. Это не измерение интерактивной FPS; причина/величина замедления в отдельных draw/resize ещё не профилированы. Не считать увеличение продолжительности приёмки признаком равенства оригиналу.

## Что ещё нельзя утверждать

Рисуется исходный software grid **внутри Qt plot ViewBox**, а не полный оригинальный TBitmap+TCanvas. Оригинальные серии, шрифты Tahoma/GDI TextOut, четыре scanline стороны рамки, физический DPI=150%, Win32 clGreen/pmXor пиксели, x87 Float32 tie-rounding, actual screen-to-PaintBox mouse mapping и same-window original vs recreated numerical/PPI comparison не доказаны. Настоящего запущенного оригинального MVKView/прибора в GitHub CI не было; synthetic PNG и исходный IDP не выдают за эталон оригинала. Приватные PAS/DFM/IDP/BIN/Power/Y не коммитились.

## Следующий КРУПНЫЙ связанный пакет

Согласовать исходные текстовые метрики GDI + рамку + живую серию с одним графическим источником, улучшить производительность при drag/scroll/resize кэшем по исходным входам и подтверждёнными сценариями; одновременно проверить недостающие операции PageAdc/PageSpectrum, остальные семь страниц и три формы, вести Core и Qt вместе. Численная original-run приёмка требует одинакового локального BIN и реально запущенного оригинального Win32 процесса, не заменять синтетикой.
