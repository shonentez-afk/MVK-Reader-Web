# STAGE111Z31CD — source 10×10 тики/подписи на реальных PageAdc/PageSpectrum

**Дата:** 13.11.2026. **Статус:** ПРИНЯТ как часть большого восстановления, оригинал 1:1 не заявлен.

## Независимая исходная база

В предоставленном оператором локальном архиве `Projects.7z/_Unit115.pas` проверен `TQGrapher.Draw`: `007CAC89..007CACAF` задаёт `HLineSpacing = Single(ScrHeight/AutoHSpacing)`, `VLineSpacing = Single(abs(ScrWidth/AutoVSpacing))`; `007CAD2F..007CAD67` задаёт границы кратных с допуском 0.0001. Исходная временная ось PageAdc имеет отрицательный `ScrWidth`, поэтому диапазон для тиков упорядочивается, но сама исходная обратная ось НЕ переставляется. Численные подстановки и текстовые кандидаты `_Unit114` уже были проверены в `core/tqgrapher_grid_idr_candidate.py` и переиспользуются, без нового анализа FFT/FRange.

## Реализация (одновременно Core + действующий Qt)

- `mvk_compatible/core/original_live_axis_ticks.py`: новый автономный контракт для конкретного текущего source screen, Float32 Single, 10 делений, обратного X, 0.0001 integer-k gate и 3-значного текста-кандидата с десятичной запятой; указывает отсутствие original Win32 GDI/x87 аттестации.
- `mvk_compatible/desktop/source_plot_geometry.py`: `SourceTickAxis(pg.AxisItem)` для обеих настоящих `SourceGeometryPlot`. `tickValues/tickStrings` читают текущие `minVal/maxVal` от Qt ViewBox, а не фиктивные данные или отдельный скриншот. Оригинальный графический источник остаётся единственным; физические единицы, GetSignal и N/2 FFT не подменяются.
- `mvk_compatible/tests/test_stage111z31cd_live_axis_core.py` и `test_stage111z31cd_qt_source_ticks_live.py`: проверки исходной Single-модели (включая отрицательный X), отказа при некорректных пределах, действительных Qt осей двух страниц при zoom/resize, неизменного FFT и SHA файла. Research/Status графики не переведены на исходные 10×10 тики.
- CI включает новый Qt-тест в Windows DPI150. Попытка `5579f4ef` выявила неверное тестовое ожидание Float64 на узком обратном диапазоне; итоговое сравнение использует source Single и принято в SHA `eb5f8f19...`. Эта поправка касается проверки, а не FFT/операторской математики.

## Проверенная сборка

- [GitHub Actions #43366482014](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43366482014): **SUCCESS 3/3**, проверенный исполняемый SHA `eb5f8f1988b0194e0d4736ea29a6ff6d3d6f12e9`.
- Linux **1833 passed / 96 skipped**, Windows Core **1980 passed / 7 skipped**, Windows Qt Smoke **49 passed**, Windows Qt DPI150 **118 passed**.
- [Windows EXE ZIP artifact #14009954473](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43366482014/artifacts/14009954473) **68 940 195 байт**, до **27.11.2026**; GitHub Actions artifact ZIP SHA256 `22212245a35d4203347819dee116b5f38e29e157fe3f741f859ec96b5912aff2`.
- [Synthetic DPI150 #14011045780](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43366482014/artifacts/14011045780) **635 837 байт**, до **20.11.2026**.

## Что НЕ принято

Delphi TCanvas TextWidth/TextHeight, фактические пиксели Win32 GDI, XOR clipping/font parity, FormatFloat locale/x87 0-ULP для исходного оригинального процесса, специфические отрицательные ScrWidth Win32 runtime edge cases и все пользовательские операции семи страниц/трёх форм. В Qt по-прежнему используется измеренный Qt FontMetrics, а не оригинальный Win32 GDI. Same-window исходная GetSignal/FIR/FFT/Power/Y/FRange сверка на парном оригинальном BIN остаётся открытой. Ни оригинальный EXE, ни приватный PAS/DFM/IDP/BIN, ни x32dbg запуск не понадобились и не публиковались.

## Следующий большой связанный пакет

Доделать source точные тики/подписи + реальное clipping/XOR/GDI поведение/курсор на PageAdc/PageSpectrum одновременно с моделью данных, затем покрыть не только маршрут, но и все безопасные операции семи страниц и трёх форм. Оригинальную Win32 same-window численную приёмку выполнять только при реальном доступе к идентичной записи и проверяемому оригинальному процессу; synthetic/CI не подменяет эталон.
