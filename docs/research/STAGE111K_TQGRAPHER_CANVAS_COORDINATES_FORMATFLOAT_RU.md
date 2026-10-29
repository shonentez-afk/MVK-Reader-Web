# Stage 111K — геометрия оригинального TQGrapher и числовая маска Delphi

Дата: 29.10.2026. Ветка: research/stage111-mvkview-desktop-20261029. Архитектура: самостоятельная Windows Qt программа MVKView Compatible Desktop, никаких обращений к прибору.

**Статус:** структура исходных геометрических преобразований и динамической маски проверена по приватным Delphi/DFM; исследовательская реализация и синтетические тесты. **Реальное совпадение оригинального изображения/Delphi RTL/числовой FFT-паритет НЕ доказано.**

## 1. Исходный анализ настоящего MVKView (приватный оригинал)

Из доступных пользовательских Projects.7z прочитаны локально _Unit115.pas, _Unit114.pas, _Unit128.pas и mvkform.dfm. Оригинальные IDP/PAS/DFM, коэффициенты FIR и измерения приборов в репозиторий не отправлены.

- TQGrapher.Create:007CA37E — Margin=10; ScrLeft=-1,5; ScrWidth=2; ScrBottom=-1,5; ScrHeight=2; PixelWidth/Height=200 при конструировании (позднее устанавливаются реальные размеры виджета).
- mvkform.dfm — вкладка PageSpectrum, pnSpecTools шириной 177, pnSpecGraph шириной 807 (динамический Align), исходный pbSpectrum = 767 × 716, справа вертикальный ScrollBar 24, сверху горизонтальный ScrollBar 24. Это только размеры проектной формы; текущие размеры зависят от окна/DPI.
- TQGrapher:007CA4C8–007CA70D — независимая инициализация реальной графической PixelRect и шести коэффициентов, каждый результат записывается как Single.
- PixelRight = PixelWidth - Margin; PixelTop = Margin.
- PixelLeft = Margin + TextWidth("0.000000") + TextWidth("0").
- PixelBottom = PixelHeight - Margin - TextHeight("0") - TextWidth("0"); если XName или YName непустые — ещё минус TextHeight("0") + TextWidth("0").
- Перед вычислением Margin повышается минимум до 10, PixelWidth/PixelHeight не меньше 3×Margin; при слишком узкой или низкой области PixelLeft/PixelBottom сбрасываются к соответствующим границам Margin. Минимальные Screen spans и отрицательные X масштабы оригинал нормализует; исследовательское ядро для непроверенных краевых случаев работает fail-closed.
- Пусть W = PixelRight - PixelLeft, x0 = Series.XStart, dx = Series.XScale, L = ScrLeft, S = ScrWidth. По адресам 007CA62F–007CA6C9:
  - itosM = Single(W × dx / S)
  - itosC = Single(PixelLeft + (x0 - L) × W / S)
  - stoiM = Single((S / W) / dx)
  - stoiC = Single((L - x0) / dx)
- Независимость itos и stoi существенна: их Single stores и округление запрещают использовать одну как точную математическую обратную другой.
- Для Y, где H = PixelBottom - PixelTop, B = ScrBottom, T = ScrHeight, исходные 007CA6CA–007CA6FE:
  - ytosM = Single(-H / T)
  - ytosC = Single(PixelBottom + H × B / T).
- 007CABE4: индекс = clamp(TRUNC((CursorPixel - PixelLeft)×stoiM + stoiC), 0, Series.DataSize-1).
- 007CAB94: snapped_pixel = @ROUND(clamp(Single(index×itosM + itosC), PixelLeft, PixelRight)). Курсор невидим на внешних границах.
- 007CA903 и 007CAA14: отображаемое X/Y отдельно вычисляется из исходного индекса, Series.XScale/Start, YScale, формируется локализованная строка.
- 00848297–008482D1 из Stage111J сохраняется: видимая Spectrum серия равна TRUNC((N/2)/1,28), тогда как полная мощность N/2 остаётся в GetSpectrum.

## 2. Числа и Delphi FormatFloat

В приватном _Unit114.pas:007B2090–007B21DE уточнён алгоритм форматирования:

1. Входной x — Single. При NaN выдаёт строку NAN, нуль выдаёт 0.
2. Изначально шаблон FormatFloat — строка «0.».
3. Повторять v := Single(abs(x)×10), дописывая нуль в шаблон, пока v меньше 10^(significant_digits-1). Для спектрального курсора significant_digits=4, для оригинального Copy три поля имеют 3/4/4.
4. Передать исходный Single, преобразованный в Extended, полученную динамическую маску и глобальный TFormatSettings в Delphi RTL (0042EE10); затем удалить конечные нули и десятичный разделитель.
5. Конкретное двоичное округление FormatFloat, Windows-локаль, Unicode и исключения RTL **ещё не доказаны**: наличие source-подобного построителя маски не является подтверждением точного текста работающей MVKView.

Отдельная функция cursor_decimal_mask_candidate() возвращает маску, количество знаков и original_delphi_rtl_verified=false, а существующий formatter использует тот же общий механизм. Отдельные тесты охватывают границы, очень малые Single, нуль и NaN.

## 3. Новые исходники и интеграция

- mvk_compatible/core/tqgrapher_canvas_idr_candidate.py — чистый source_canvas_geometry() с обязательными ширинами/высотами TCanvas, исходными полями ScrLeft/Width/Bottom/Height и координатами серии, отдельными Single itos/stoi/yto, абсолютными PixelLeft/Right/Top/Bottom. Входы/калибровка не угадываются. cursor_geometry_from_canvas() связывает реальные абсолютные координаты с существующим отбором пика.
- mvk_compatible/core/cursor_format_candidate.py — source-matching cursor_decimal_mask_candidate() с динамической маской 0.00… и контрольным Single; итоговые цифры Python остаются численным кандидатом Delphi RTL.
- mvk_compatible/canvas_reference_compare.py — offline CLI для оригинальных локальных JSON метрик Canvas и эталонных координат/коэффициентов: считает поимённые абсолютные ошибки, не делает интерполяцию или fit, показывает только ошибки и SHA-256, никогда исходные снимки. Даже при PASS флаги original_delphi_pixel_parity_verified и original_font_metrics_parity_verified всегда false.
- mvk_compatible/desktop/main_window.py — кнопка «Геометрия Canvas (Qt-кандидат)». Использует фактически измеренные метрики текущего Qt-шрифта, а не произвольную ширину букв, и показывает исходные формулы/коэффициенты только как диагностический предпросмотр. Текущий Qt график и курсор не маскируются под измеренный Delphi Canvas.
- mvk_compatible/tests/test_tqgrapher_canvas_idr_candidate.py, test_canvas_reference_compare.py, test_cursor_format_candidate.py, test_desktop_qt.py — синтетические проверки Canvas bounds, текстовых отступов, source Single коэффициентов, fail-closed, безопасности приватного эталона и реального Qt callback.
- .github/workflows/stage111-desktop-offline.yml — запускает новые тесты и весь предшествующий регрессионный корпус отдельно на Linux, Windows и Qt, затем собирает Preview EXE.

## 4. Формат приватной сверки в Stage111K

Локальный файл canvas-metrics.private.json должен иметь ровно 14 полей (все явно):
pixel_width, pixel_height, margin, zero_text_width, six_decimals_text_width,
zero_text_height, x_name_present, y_name_present, scr_left, scr_width,
scr_bottom, scr_height, series_x_start, series_x_scale.

Второй оригинальный файл canvas-reference.private.json содержит минимум одно из:
pixel_left, pixel_right, pixel_top, pixel_bottom, itos_m, itos_c,
stoi_m, stoi_c, ytos_m, ytos_c.

Все данные можно собирать на частном компьютере офлайн, **оригинальное изображение прибора/технический скриншот не отправлять в публичный GitHub**.

Команда (в синтаксисе Windows PowerShell, без реальных промышленных имён):
python -m mvk_compatible.canvas_reference_compare --metrics "C:\private\canvas-metrics.private.json" --reference "C:\private\canvas-reference.private.json" --pixel-tol 0 --coefficient-tol 0.00001 --report-json "C:\private\canvas-diff.private.json"

Если нет оригинальных метрик TCanvas, можно проверить только формулы на синтетике; даже численное PASS не сертифицирует совпадение реального оригинала. В отчёт попадают абсолютные ошибки, хеши и предупреждения, но не исходные числа или скриншоты.

## 5. Что ещё не закрыто и следующий этап Stage111L

1. Получить оригинальный скриншот того же MVKView с разрешением окна, DPI, шрифтом и состоянием осей; измерить TextWidth("0"), TextWidth("0.000000"), TextHeight("0") и реальные PixelRect для количественной сверки.
2. Сопоставить конкретное место курсора на таком скриншоте с индексом исходного FFT и двумя независимыми трансформациями, затем доработать обработчик мыши Qt на точной оригинальной базе.
3. Исследовать Delphi FormatFloat 0042EE10, TFormatSettings и края округления x87; нужен золотой оригинальный текст 3 полей и CursorString для той же частоты.
4. Провести численную сверку полного FFT, OutputMean/Peak и GetNarrowbandValue на **одинаковой** записи/окне/FRange, отдельно проверяя происхождение Native BIN vs оригинального float ring.
5. Продолжить трёхвкладочную визуальную и функциональную приёмку, затем архив/Live только через единственный Native R6.1 Collector и отдельное разрешение пользователя.

**Безопасность:** main/v0.3.40/старая исследовательская ветка не изменены; реальный MVK, TCP/10230, команды устройства не используются; никакие оригинальные IDP/DFM/PAS/BIN/PCAP не публикуются.

**Следующий чат:** начать с обоих ADR, docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md, этого Stage111K отчёта, матрицы совместимости и последнего завершённого GitHub Actions. SHA и точное число PASS внести после завершённого CI (не предполагать автоматически).
