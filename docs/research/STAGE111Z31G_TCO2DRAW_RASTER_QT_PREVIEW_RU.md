> **STAGE111Z31G FINAL CI/EXE VERIFIED (05.11.2026):** source commit `3b9baaccb2a1a690bd1c536f244dd6a8e4012971`; [GitHub Actions #41968796605](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41968796605) **3/3 jobs SUCCESS**. Linux Core **1319 passed /29 skipped /1 warning/30 subtests**, Windows Core **1344 passed /4 skipped /1 warning/30 subtests**, Windows Qt **49 passed**, Windows Qt at verified `DPR=1.5` **22 passed**. Go Native R6.1 compiled and tested unchanged; independent PE/SHA/manifest copy-verification PASS. [Latest Windows preview artifact #13389122017](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41968796605/artifacts/13389122017), ZIP **68 521 789 bytes**, GitHub ZIP SHA256 `cbb5e046e26487a3a54542b022de404031f737459dd9a006a80bb26716c0543d`, embedded `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `9faf74c58fc50cc57f1996494f976eb403f37350c3058c42f6af3efa93e2dd9c`, expires 19.11.2026. Current Qt sprite raster is source-derived research, not original Delphi physical pixel parity. Two earlier Stage31G CI failures were invalid test assumptions about interpolated grid ink and PlotItem clipped data after zoom; code raster/FFT unchanged when fixing those assumptions.

# Stage 111Z31G — программная отрисовка сетки

Дата: 05.11.2026. Ветка: research/stage111-mvkview-desktop-20261029.

## Сделано
- Добавлен независимый модуль `mvk_compatible/core/tco2draw_raster_candidate.py`.
- Реализованы проходы по X/Y, три соседних пикселя, смешивание оттенков, отсечение по границам и защита от больших изображений.
- Исследовательский график может показывать RGBA-растр под неизменённой исходной спектральной кривой. Обычный режим остаётся прежним.
- При изменении масштаба перестраивается изображение, а при возврате в архив все исследовательские элементы удаляются.
- Добавлены core и Qt-тесты. В GitHub Actions включена проверка Qt при масштабировании 150%.

## Достоверность
Исходные данные пользователя не публикуются. Работа выполнена по восстановленной логике графического компонента, но абсолютное совпадение пикселей оригинальной Windows-программы пока **не подтверждено**: неизвестны размеры Canvas, FontMetrics, DPI и некоторые граничные особенности округления.

Не изменялись FFT, четыре подтверждённых спектральных режима, FRange, Native Go R6.1 и основная ветка.

## Далее — Stage 111Z31H
1. Сверить координаты и размеры области графика оригинала с нашим Qt ViewBox.
2. Восстановить оригинальную отрисовку подписей и графической серии.
3. Сравнить растровые изображения по одному исходному измерению, не повторяя уже выполненные захваты Power/Y.
4. Продолжить функциональную приёмку временного сигнала, расчётных данных и автономной записи.
