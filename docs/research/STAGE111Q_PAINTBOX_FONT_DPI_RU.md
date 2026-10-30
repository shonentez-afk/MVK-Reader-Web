# Stage 111Q — TPaintBox Margin, Canvas.Font и DPI

**Дата:** 30.10.2026

**Ветка:** research/stage111-mvkview-desktop-20261029

**Актуальный программный SHA после анализа DFM:** d8c44318a09d328ecfd14a3a92f1bb987209999b. Предыдущий проверенный код: 1baf980e611f55d38618b4dc170e8662089eaf62.

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

**Локально:** 38 синтетических проверок pure-core PaintBox, DFM design-profile и font-spec validation прошли (Linux; фактический Win32 API проверяется в CI Windows).

**Базовый протестированный SHA:** 1baf980e611f55d38618b4dc170e8662089eaf62. После восстановления проектных DFM-параметров актуальный code SHA — d8c44318a09d328ecfd14a3a92f1bb987209999b; [Linux #55](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/55) SUCCESS, [Windows #54](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/54) проверяется, EXE ещё не подтверждён.

- Linux Core: https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/49 — SUCCESS.
- Windows Core + Qt: https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/48 — SUCCESS.
- Windows Preview EXE: проверить последующее задание и фактический SHA256SUMS из Artifacts.

При изменении документации последующий HEAD может отличаться; источник тестируемого кода указан выше.

## Приватная процедура уточнения оригинального шрифта

На Windows пример *независимой* GDI-пробы оператора:

python -m mvk_compatible.win32_canvas_font_probe --font-family Tahoma --font-height-px -13 --report-json C:\Private\gdi-font-candidate.json

Здесь «Tahoma» и «-13» — подтверждённые свойства шрифта исходной ФОРМЫ на этапе проектирования DFM; фактическая гарнитура Canvas при запуске ещё не измерена. Для честной сверки нужны фактические TPaintBox.Canvas.Font.Name, Height, Style, оригинальные TextWidth/TextHeight и DPI того же окна. В приватный canvas_sweep_reference_compare передавать Margin=max(10,min(W//53,H//30)), не старое фиксированное 10.


## Дополнение Stage111Q — найден приватный оригинальный DFM

В том же архиве Projects.7z обнаружен и локально прочитан оригинальный mvkform.dfm. Исходник DFM **не публиковался**. Непосредственно подтверждены следующие *свойства дизайна*, а не измерения работающей MVKView:

| Объект/свойство | Подтверждённое проектное значение |
|---|---|
| Форма mvkform Font.Name | Tahoma |
| Форма Font.Height / Style | −13 / normal (пустой Style) |
| Форма PixelsPerInch | 96 |
| pbAdc (TPaintBox) Width × Height | 791 × 740 |
| pbSpectrum (TPaintBox) Width × Height | 767 × 716 |
| Original DFM sbSpecHScroll | Left 24, Width 553, Height 24 |
| Original DFM sbSpecVScroll | Top 0, Width 24, Height 400 |

Оба PaintBox используют Align=alClient. После запуска размеры могут измениться; шрифт формы не доказывает фактический шрифт дочернего PaintBox при всех состояниях, Windows DPI и подменах GDI. После Draw исходная Delphi-программа **переназначает** Left/Width горизонтального и Top/Height вертикального скроллбаров по PixelRect, так что начальные DFM Left/Width/Top/Height не являются финальными runtime координатами.

При исходных *проектных* размерах первый Margin равен 14 как для ADC, так и для Spectrum. При условных, сугубо синтетических TextWidth('0')=8, TextWidth('0.000000')=64, TextHeight('0')=14 получаются: ADC PixelRect=(86,14)-(777,682), Spectrum=(86,14)-(753,658). Без оригинальных runtime TextWidth/TextHeight/Font/DPI эти числа нельзя считать реальными пикселями MVKView.

Добавлен независимый модуль mvk_compatible/core/tqgrapher_dfm_design_idr_candidate.py — компактный **производный проектный профиль** и расчёт Canvas с отдельно задаваемыми метриками; ни DFM, ни свойства закрытых коэффициентов туда не копируются. В Qt-диалоге показаны отдельно проектные Tahoma/−13/PPI96/767×716 и текущие Qt-метрики, с явными флагами «runtime font not verified». Новые тесты проверяют различия ADC/Spectrum, source Margin=14 и отсутствие ложной приёмки; Windows CI отдельно замеряет GDI Tahoma−13 только на синтетическом HDC.

## Что не доказано

Фактические размеры и Font/DPI оригинальной MVKView при запуске, координатное соответствие Qt viewport/scene ↔ Delphi TPaintBox Canvas, оригинальный GDI XOR в Qt, CursorString/FormatFloat/x87, Original FFT/GetSpectrum/GetNarrowbandValue/FRange, UX трёх вкладок и численная/пиксельная идентичность оригинала. Реальный прибор не подключался, AUX4700/VALUES не подменялись локальным FFT. Скачанный EXE/SHA пока не сверены.

## Следующая точка — Stage 111R

Сначала проверить CI полного нового HEAD и Windows EXE/SHA256. Затем собрать приватные настоящие TCanvas Font/DPI/PixelRect и CursorDrawnX/Y на одинаковом окне, сопоставить с новым PaintBox и GDI XOR модулем, и только затем внедрять pixel-accurate Qt/GDI изменение. Продолжать RTL/x87/FormatFloat и FFT отдельно. Стабильные main и v0.3.40 не изменять.
