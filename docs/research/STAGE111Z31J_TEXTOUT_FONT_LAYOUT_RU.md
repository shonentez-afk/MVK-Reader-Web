# Stage111Z31J — восстановление TextOut-подписей в едином спектральном TQGrapher

Дата: 05.11.2026. Рабочая ветка: `research/stage111-mvkview-desktop-20261029`.

## Результат (код реализован и CI успешно завершён)

**Исходный код проверен на приватном операторском `Projects.7z`**, в котором имеется независимая реконструкция Delphi `_Unit115.pas` и `_Unit128.pas`. **Никаких оригинальных PAS/DFM/IDP, x32dbg-двоичных массивов, исходных измерений или скриншотов в GitHub не загружалось.**

**Адреса оригинала:**
- `_Unit115:007CACEE..007CACF9`: `TQGrapher.Draw` копирует исходный `TPaintBox.Canvas.Font` через `TFont.Assign` на внутренний `TBitmap.Canvas`. **DFM `Tahoma, Height=-13, PixelsPerInch=96` не доказывает фактический runtime `TCanvas.Font` на Windows 150%.**
- `007CA4E8..007CA4F4`: `TextOffset=TextWidth('0')`.
- `007CADF1..007CAE29`: подписи Y после горизонтальных линий: `x=PixelLeft-TextWidth(label)-TextOffset`; `y=Round(ytos(tick))-TextOffset`.
- `007CAF1E..007CAF5F` (и отрицательный диапазон `007CB02B..007CB074`): подписи X после вертикальных линий: `x=Round(xtos(tick))-TextWidth(label) div 2`; `y=PixelBottom+TextOffset`.
- `007CB095..007CB0CF`: YName слева внизу; `007CB0E4..007CB129`: XName центрировано внизу. `NoVText/NoHText` выводятся из исходной fallback-геометрии при слишком широких подписях.
- `_Unit128:0084C801`: `SpecGrapher.XName` устанавливается в исходный `Гц`; `YName` зависит от типа спектра, поэтому в исследовательской визуализации источник YName — `_full_spectrum['unit']`, а не одна жёсткая единица для всех четырёх режимов.

**Реализация:**
1. `mvk_compatible/core/tqgrapher_textout_source_candidate.py` — независимый от Qt вычислитель source TextOut placements с переданными `TextWidth/TextHeight`, x87 Single-кандидатами, аккуратной нормализацией, безопасными пределами, original font/DPI parity = **False**.
2. `mvk_compatible/desktop/tqgrapher_textout_qt_candidate.py` — программное рисование кандидатов глифов внутри того же `RGBA8888` через `QImage/QPainter`. Прозрачная кисть, чёрный текст, аппаратные FontMetrics **не утверждаются**. Входной RGBA оригинал не мутируется.
3. `core/tqgrapher_composite_source_candidate.py`: инъекция `source_textout_layout` и необязательного **исследовательского** Qt TextOut-слоя между сеткой и TQGRSeries. При отсутствии callback исторический вариант остаётся прежним.
4. `desktop/main_window.py`: для проверенного SHA/Float32 оригинального Power/Y при совместном включении уже существующих сетки/растра/серии все деления и названия осей рисуются внутри единого bitmap. При этом Qt axis labels/ticks временно скрыты, при возврате восстанавливаются. Источники Y, FRange, FFT, Native R6.1, архив и Web/main не изменены. Метрики берутся из ОДНОГО `QFont('Tahoma', pixelSize=13)` как приближение к DFM. `QFontMetrics` — **не** оригинальный GDI `TextWidth`.
5. Новые тесты: `test_stage111z31j_tqgrapher_textout.py`, `test_stage111z31j_qt_textout.py`; Windows Qt DPR1.5 gate запускает новый файл. Проверены исходные x/y/axis names, fallback, `Qt RGBA`, 150% и отсутствие мутации original Float32.

## Подтверждённый CI/Windows EXE

Протестированная ревизия кода: `80848403bc954298216bbabcabbb6762527b19d4`.

[GitHub Actions #41974751644](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41974751644): **3/3 SUCCESS**.
- Linux Core: **1379 passed / 44 skipped / 1 warning / 30 subtests**.
- Windows Core: **1419 passed / 4 skipped / 1 warning / 30 subtests**.
- Windows ordinary Qt: **49 passed**.
- Windows Qt при измеренном `DPR=1.5`: **37 passed**.
- Автономный Win EXE собран с протестированным старым Native Go R6.1, сверен с независимым PE/SHA manifest.

[Windows artifact #13391791165](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41974751644/artifacts/13391791165): ZIP **68 547 535 bytes**, GitHub ZIP SHA256 `c52ce3fda94d4ddc1a84a7affc80884ee16b0e6ad49e59bdabd49aef3a26aef9`, embedded `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `b636bdfc4fa307a351db3c7ad4c1b62322f3a129c014cb0ae3341079af371a75`, срок хранения до **19.11.2026**.

## Блокирующие условия полной копии спектра

Это подтверждение модели TextOut-координат и его Qt-предпросмотра, **не Win32 GDI pixel parity**. Следующий Stage111Z31K — восстановить **фактический runtime Font/PPI/PaintBox PixelRect** оригинального процесса, внедрить проверяемый Win32 GDI raster (или измерить отличный Qt), зафиксировать один и тот же исходный Tag0 спектр и выполнить объективный bitmap pixel-diff с координатами/метриками. Отдельно необходимы точный курсор/XOR, масштабы, вторая TQGRSeries, контекстные действия, экспорт и envelope. Нельзя объявлять полноценное восстановление спектра без этих ворот.

**Приоритет не изменять:** СПЕКТР полностью до оригинала → ВРЕМЕННОЙ СИГНАЛ/GetSignal → РАСЧЁТНЫЕ ДАННЫЕ → ПОЛНОЕ ВОССТАНОВЛЕНИЕ СТРАНИЦ/UX. Не повторять принятые 4 режима GetSpectrum или Native Stage109; в GitHub не публиковать операторские оригинальные файлы.
