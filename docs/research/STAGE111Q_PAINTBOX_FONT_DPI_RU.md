# Stage 111Q — TPaintBox Margin, Canvas.Font и DPI

**Дата:** 30.10.2026

**Ветка:** research/stage111-mvkview-desktop-20261029

**Проверенный программный SHA:** 1baf980e611f55d38618b4dc170e8662089eaf62

**Архитектура:** только автономная Windows Qt MVKView Compatible (mvk_compatible/). Не возвращаться к старой Web-архитектуре.

## Подтверждено оригинальными Delphi-инструкциями (приватно)

- _Unit128:0084B40F–0084B42D: на вкладке «Временной сигнал» первоначальный Margin = min(trunc(pbAdc.Width/53), trunc(pbAdc.Height/30)).
- _Unit128:0084C840–0084C864: вкладка «Спектр» рассчитывает тот же Margin по фактическим pbSpectrum.Width/Height.
- _Unit115:007CA4DB–007CA4E1: TQGrapher нормализует Margin минимум до 10. _Unit115:007CA571–007CA593 допускает виртуальное увеличение PixelWidth/PixelHeight до 3*Margin.
- _Unit115:007CA4E8–007CA5FA: оригинал получает TextWidth("0"), TextWidth("0.000000") и TextHeight("0") с переданного TPaintBox.Canvas. Это самостоятельные метрики, их нельзя подменять коэффициентом DPI.
- _Unit115:007CACE4–007CACFC: TQGrapher.Draw копирует Font исходного Canvas во вспомогательный bitmap методом TFont.Assign.
- _Unit128:0084C8A6–0084C8CF: sbSpecHScroll.Left=PixelLeft, Width=PixelRight-PixelLeft. _Unit128:0084C8CF–0084C8F8: sbSpecVScroll.Top=PixelTop, Height=PixelBottom-PixelTop. Прочие координаты исходных полос данным обработчиком не назначаются.

Исходные PAS/DFM/IDP, производственные BIN/PCAPNG, оригинальные коэффициенты — только приватно, не коммитить и не отправлять в CI.

## Обнаруженное расхождение

Предыдущая Qt-диагностика принудительно использовала Margin=10. Исходный Delphi использует динамический Margin.

Синтетический Canvas 800 × 500, TextWidth("0")=8, TextWidth("0.000000")=64, TextHeight("0")=14:

| Поле | Старый fixed margin | Source-derived original formula |
|---|---:|---:|
| Margin | 10 | 15 |
| PixelLeft/Right | 82 / 790 | 87 / 785 |
| PixelTop/Bottom | 10 / 446 | 15 / 441 |
| HScroll Left / Width | не выводились | 87 / 698 |
| VScroll Top / Height | не выводились | 15 / 426 |

Эти численные значения получены из синтетических исходных метрик и НЕ являются измерениями оригинальной MVKView.

## Реализовано

1. mvk_compatible/core/tqgrapher_paintbox_registration_idr_candidate.py — исходная целочисленная формула min(width div 53,height div 30), TQGrapher clamp и оригинальные относительные координаты горизонтальной и вертикальной полосы; сохранены независимые Single коэффициенты из Stage111N.
2. mvk_compatible/desktop/main_window.py — диалог Canvas использует корректный размерный Margin и отображает исходные якоря scrollbar, фактические Qt font family, logical DPI и devicePixelRatioF отдельно. Метрики остаются из Qt viewport; НЕ считать исходным TPaintBox.
3. mvk_compatible/win32_canvas_font_probe.py — автономное измерение в настоящем Windows GDI через CreateFontW, GetTextExtentPoint32W, GetTextFaceW, GetDeviceCaps на одном memory HDC. Явно запрашиваемый HFONT не признаётся автоматически оригинальным Delphi шрифтом.
4. Новые тесты PaintBox/Win32 и отдельный Qt offscreen тест проверяют формулы, маленький Canvas, необычные шрифты, неверные входы и маркировку неподтверждённого оригинала.

## Тесты и текущий CI

**Локально:** 26 синтетических проверок pure-core PaintBox и font-spec validation прошли (Linux; фактический Win32 API проверяется в CI Windows).

**Программный SHA:** 1baf980e611f55d38618b4dc170e8662089eaf62

- Linux Core: https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/49 — SUCCESS.
- Windows Core + Qt: https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/48 — SUCCESS.
- Windows Preview EXE: проверить последующее задание и фактический SHA256SUMS из Artifacts.

При изменении документации последующий HEAD может отличаться; источник тестируемого кода указан выше.

## Приватная процедура уточнения оригинального шрифта

На Windows пример *независимой* GDI-пробы оператора:

python -m mvk_compatible.win32_canvas_font_probe --font-family Tahoma --font-height-px -14 --report-json C:\Private\gdi-font-candidate.json

Здесь «Tahoma» и «-14» — примеры, не установленные параметры оригинальной MVKView. Для честной сверки нужны фактические TPaintBox.Canvas.Font.Name, Height, Style, оригинальные TextWidth/TextHeight и DPI того же окна. В приватный canvas_sweep_reference_compare передавать Margin=max(10,min(W//53,H//30)), не старое фиксированное 10.

## Что не доказано

Реальные размеры и Font/DPI исходной MVKView, координатное соответствие Qt viewport/scene ↔ Delphi TPaintBox Canvas, оригинальный GDI XOR в Qt, CursorString/FormatFloat/x87, Original FFT/GetSpectrum/GetNarrowbandValue/FRange, UX трёх вкладок и численная/пиксельная идентичность оригинала. Реальный прибор не подключался, AUX4700/VALUES не подменялись локальным FFT. Скачанный EXE/SHA пока не сверены.

## Следующая точка — Stage 111R

Сначала проверить CI полного нового HEAD и Windows EXE/SHA256. Затем собрать приватные настоящие TCanvas Font/DPI/PixelRect и CursorDrawnX/Y на одинаковом окне, сопоставить с новым PaintBox и GDI XOR модулем, и только затем внедрять pixel-accurate Qt/GDI изменение. Продолжать RTL/x87/FormatFloat и FFT отдельно. Стабильные main и v0.3.40 не изменять.
