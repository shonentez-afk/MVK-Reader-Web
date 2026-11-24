# Stage111Z31DZ — LIVE PageSpectrum: полная цепочка отображения, шкал и курсора

**Дата:** 24.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.

## Конкретный найденный разрыв

В прежней production-функции `MainWindow._render_live_spectrum` вычислялся локальный GetSpectrum (включая исходный FIR/IQ при наличии подходящего кольца и IDP), но после рисования обнулялись `_full_spectrum`, `_spectrum_summary`. Обработчики X/Y, прокрутки и пиксельного курсора были связаны с `_full_spectrum`, поэтому в LIVE фактически не имели текущего полного массива. Обычный `provisional_spectrum` по умолчанию возвращал уже редуцированную для графика серию, а курсор и summary нельзя корректно извлекать из такой серии.

## Повторная сверка оригинала — только локально

Из `/mnt/data/Projects.7z` извлечены `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas` и `mvkform.dfm`. В `mvk_idr(1).sqlite` проверены функции, адреса и DFM события:
- `TMvkChannelStorage.GetSpectrum 007D13D4`;
- `Tmvkform.mSpecHScale1Click 0084C3AC`;
- `Tmvkform.mSpecLines1Click 0084C4C8`;
- `Tmvkform.mSpecType1Click 0084C514`;
- `Tmvkform.mSpecVScale1Click 0084C5AC`;
- `Tmvkform.pbSpectrumMouseMove 0084C918` (передача X в TQGrapher);
- DFM `PageSpectrum/tcSpectrum/pnSpecTools`, `pnSpecGraph/pbSpectrum`.

Локально подтверждён SHA256 `mvkview.idp`: `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Ни исходные PAS/DFM, ни IDP/SQLite, ни приборные данные не загружались в GitHub.

## Восстановленный маршрут в приложении

Кодовый SHA `4c4dca955b741b777b847c2ec226b5b05cdb881e`:
1. `native_r6_live_preview.provisional_spectrum(..., full_bins=True)` сохраняет N/2, не меняя существующий legacy API.
2. Новый `original_live_spectrum_view.bind_live_spectrum_view` проверяет selected ADC/mode, окно/его SHA, PRE-FIR bSpecLines и POST-FIR N/Fs при FIR, сплошной частотный ряд и summary; хранит неизменяемые массивы. Раздельное `live_spectrum_plot_points` показывает только исходную TQGRSeries (Trunc((N/2)/1.28)), ограничивает отрисовку до 5000 точек с сохранением extrema и раскрывает исходные бины при zoom.
3. `MainWindow._render_live_spectrum` привязывает один полный расчёт к текущему LIVE сеансу, АЦП, SHA, режиму, фильтру, Fs и N. X/Y presets и scroll работают через существующие source-derived обработчики без повторного FFT. Курсор берёт полный массив, а не LOD; summary — из того же вычисления. Y не наследует ручной FRange старого архива.
4. При новом Go статусе перепроверяется пригодность уже показанного окна; меняется АЦП — обновляется доступность FIR по текущей частоте. При недостоверности, Stop, завершении или выборе другого режима на Freeze старые значения не должны оставаться текущими. Задержанный результат не подтверждает аппаратный паритет.
5. `Copy/Save` как **оригинальные аттестованные файлы** остаются запрещены для предварительного LIVE; ранее принятый offline путь не изменён. `PageStatus` остаётся отдельным потоком полных PARAM DWORD и не подменяется локальными FFT результатами.

## Проверки

В существующие файлы тестов добавлены проверки полного FFT во всех 4 режимах, min/max LOD, zoom из исходных бинов, запрета смешения АЦП и неполного массива; native Qt тест проверяет X/Y без замены полного результата, cursor SHA и N/2, смену АЦП и очистку при остановке.

Новый [GitHub Actions #45302838035](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45302838035) проверяется по этому SHA. Не присваивать 5/5 до завершения; предыдущая зелёная сборка Stage111Z31DY не подтверждает данный код.

## Граница

Это восстановление **реальных связей внутри приложения**, не измерение физического прибора. Ветку main, Go TCP, исходный DSP и формат файлов этим пакетом не меняли. Открыто: подлинный единый MVK01/Win32 RX, полные численные x87/FRange/FIR/FFT и GDI сравнения, исходные LIVE Copy/Save и все связи остальных страниц/форм. При продолжении не подменять 15 приборных режимов PageStatus расчётом Qt.
