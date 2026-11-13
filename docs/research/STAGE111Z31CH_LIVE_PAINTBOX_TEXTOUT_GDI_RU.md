# STAGE111Z31CH — оригинальная разметка PaintBox и Win32 GDI TextOut на обеих рабочих страницах

**13 ноября 2026 · Принят связанный Core+Qt пакет; полный оригинал MVKView 1.0.47 НЕ восстановлен и 1:1 НЕ заявлен.**

## Исходная база, проверенная в ЭТОЙ приёмке

В user-private `Projects.7z` прочитаны `_Unit115.pas`, `_Unit128.pas` и `mvkform.dfm` без добавления закрытых исходников в GitHub. `TQGrapher.Draw`, дизассемблированные строки `007CAC68..007CB4AA`: после программной сетки белого/серого TCo2Draw оригинал берёт `PaintBox.Canvas.Font` через `TFont.Assign` (`007CACE4..007CACF9`) и `TCanvas.TextOut` выводит X/Y тики и подписи (`007CAE29`, `007CAF5F`, `007CB074`, `007CB0CF`, `007CB129`) в тот же offscreen 32-bit TBitmap перед чёрной серией и рамкой. DFM главной формы: Tahoma, Font.Height=-13, PixelsPerInch=96; оригинальные `pbAdc` 791×740 и `pbSpectrum` 767×716 — design-time логические размеры, не измеренные физические пиксели Windows 150% runtime. Для исходной PageAdc `ScrWidth < 0` подтверждён ранее; источник FormatFloat/RTL tie-rounding остаётся кандидатом.

## Реальные изменения Core + ЖИВОЙ Qt

1. Новый `mvk_compatible/core/original_live_paintbox_text.py`: source-derived модель полного PaintBox, использующая уже аудированные `source_paintbox_registration`, `source_tqgrapher_grid_candidate`, `source_textout_layout`. Допускает ADC reverse-X, измеренные TextWidth('0')/TextWidth('0.000000')/TextHeight('0'), tick labels и names, Source Single преобразования и явную provenance метрик. Ограничения на геометрию, длины имени, типы, конечные значения и 3 млн пикселей; ни BIN, ни FFT, ни прибор не читается.
2. Новый `mvk_compatible/desktop/source_paintbox_text_overlay.py`: QWidget поверх **полного поля** реальных Qt PageAdc/PageSpectrum; мышь проходит сквозь него, а пиксели рисунка в координатном прямоугольнике кривой полностью прозрачны, чтобы не закрывать старый XOR-курсор. Нативная Windows ветка повторно использует существующий `Win32SourceTextCanvas` (`GetTextExtentPoint32W`/`TextOutW`, DFM Tahoma -13), формирует действительные GDI glyph RGB в белом offscreen image и переносит серые/чёрные глифы как alpha только в поля осей; НЕ смешивает GDI с численными FFT или GetSignal. Non-Win32 fallback — явно помеченный Qt `QFontMetrics`/glyph candidate. Fail-closed возвращает штатные оси; `source_textout_receipt` честно отмечает provenance и НЕ устанавливает оригинальный runtime parity.
3. `mvk_compatible/desktop/source_plot_geometry.py`: два обычных `SourceGeometryPlot` создают/включают этот слой только при наличии **проверенной** CG source-серии, на Windows исходные размеры осей определяются native GDI FontMetrics (Qt на других ОС), при смене названия/zoom/resize синхронизируются координаты и подписи. При включении research-режима обычный слой отключается; полные Core данные и Qt PlotDataItem остаются прежними. Исправлен реальный конфликт с независимым исследовательским source bitmap: **выводимый слой восстанавливает только оси, которыми сам владел.**

### Тесты

Новые `test_stage111z31ch_core_paintbox_text.py`: исходные формулы PaintBox, подписи 10×10, Tahoma/96PPI provenance, инверсия PageAdc X, отсутствие данных/FFT и отказ некорректным координатам. Новые `test_stage111z31ch_qt_live_paintbox_text.py`: действительно открытые PageAdc/PageSpectrum на synthetic ZIP, source-derived TCanvas label plane, настоящая GDI ветка Win32 при DPR1.5, отсутствие дублей Qt tick labels, сохранность XOR/исходного SHA, возвращение осей после отключения и независимость PageStatus/research. CI обязательный `.github/workflows/stage111-desktop-offline.yml`.

Первая попытка `36df0db8`: Linux green, Windows Core **2042 passed + 1 failed** в старом `test_stage111z31j_qt_textout.py`. Причина: двойная собственность на Qt label visibility при исследовательском Power/Y. Реальный **исправленный** `a5ac86e0`: ownership bitmap overlay, старые QA и исследовательская функция сохранены, все тесты SUCCESS.

## Подтверждённые CI/EXE

**Исполняемый код:** `a5ac86e000cc8b38387e03c1dfbcc4c1d755fcbf`.

[GitHub Actions #43391087969](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43391087969): **3/3 SUCCESS**.
- Linux Core **1886 passed / 100 skipped**, Windows Core **2043 passed / 7 skipped**, Windows Qt Smoke **49 passed**, Windows Qt DPI150 **128 passed** (фактический DPR=1.5).
- [Autonomous Windows EXE artifact #14020539441](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43391087969/artifacts/14020539441): ZIP **68 982 728 байт**, до **27.11.2026**. SHA256 uploaded ZIP `b0252e37413473aa9533e89ce8b25d8b745730fe88dde2ef29e546e775c8c14a`. Внутренний EXE SHA256 по проверенному PE-манифесту: `4959c8178ca6f8993cae7efc7fcd47aa3b250996e5584cfac731fd8a1d8ee0f8`. PE заголовок и равенство manifest SHA проверены Actions, оригинальный Delphi compatibility флаг **false**.
- [Synthetic Qt UI/DPI150 #14021052304](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43391087969/artifacts/14021052304): **689 502 байта**, до **20.11.2026**.

## Открытые ограничения и приоритетный крупный блок

**НЕ ПУТАТЬ:** GDI glyphs теперь реально рисуются на обычных экранах в прозрачном полнопольном слой PaintBox. Это **НЕ** тот же GDI offscreen TBitmap, в котором лежат source CG grid+series+frame — оригинал рисовал TextOut до линий данных, CG сейчас в отдельном нижележащем software bitmap, а поле подписей в верхнем прозрачном слое. Нет доказательства оригинального native Windows DFM font/PPI, DPI-awareness, полного GDI TextOut по краям графика, RTL decimal/Float32 ties/x87, системного скриншота и побитовой совместимости. В случае ошибки пользователь видит исходный предшествующий Qt график.

Наблюдение производительности: Windows Qt DPI150 stage CG **72,55 c** против stage CH **139,53 с**, Windows Core CG 115,56 против CH 192,05; это CI длительности разных сборок, НЕ benchmark кадра, нужен измеренный runtime profile mouse-pan/scroll и GDI canvas caching. **Следующий крупный совместный пакет**: финализировать единый source offscreen bitmap **включая** TCanvas TextOut с точной последовательностью сетка→текст→серия→рамка и устранить дублирование/перерисовку; одновременно продолжать оставшиеся локальные обработчики всех семи страниц/трёх форм и safe E2E. Same-window оригинальные GetSignal/FIR/FFT/Power/Y/FRange и физический DPI сравнивать только при доступе к оригинальному запущенному Win32 EXE и идентичным операторским данным. Приватные исходники/IDP/BIN не переносились на GitHub.
