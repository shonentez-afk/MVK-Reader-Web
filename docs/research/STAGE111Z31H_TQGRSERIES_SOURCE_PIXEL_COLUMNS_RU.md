> **STAGE111Z31H FINAL CI/EXE VERIFIED, 05.11.2026.** Exact tested code SHA `1a72595542c97059bad8bb1482b6f52c2767435f`; [GitHub Actions #41970251042](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41970251042) **3/3 SUCCESS**: Linux Core **1342 passed,35 skipped,1 warning,30 subtests**; Windows Core **1373 passed,4 skipped,1 warning,30 subtests**; Windows ordinary Qt **49 passed**; Windows Qt at independently confirmed **DPR 1.5: 28 passed**. Native Go R6.1 built/tested from unchanged source and embedded into verified onefile EXE. [Windows artifact #13389124491](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41970251042/artifacts/13389124491), ZIP **68 528 612 bytes** SHA256 `272499ab90a818732da96328090381464a190bd7e3e7a943cbd66719bc636cfb`; `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `ce0d4593125ba69aa51c675fad55756275543053da8ddcb272438b67db9ae60d`; receipt/PE/checksum independently verified; expires **19.11.2026**. All tested changes covered Core+Windows Qt; docs-only commits after tested code do not change EXE. Source-derived minmax is not certified native Win32 pixel parity; no private originals uploaded.

# Stage111Z31H — восстановлена экранная свёртка спектра TQGRSeries

Дата: 05.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.

## Из оригинального дизассемблирования (приватно)

Исследован оригинальный `_Unit115.pas` из пользовательского `Projects.7z`. **Оригинальные PAS/IDP/EXE и пользовательские измерения не публиковались.**

- `TQGRSeries`: `Data` = Single, `DataSize`, `XStart`, `XScale`, `YScale`, `Color`, `Solid`; `TQGrapher.Draw` перебирает две серии, пропуская пустые.
- `007CA4C8..007CA6C6`: affine-преобразования Single `stoi`, `itos`, `ytos` из экранного диапазона, XScale/YScale и Canvas PixelRect.
- `007CABE4`: `stoi(X)` использует `@TRUNC` и ограничивает индекс 0..DataSize-1. `007CAC18`: обрезает проецированный Y на PixelTop..PixelBottom.
- **`007CB1C9..007CB3E5`: вместо простого соединения FFT bins исходная серия `Solid=False` группирует множество исходных Single в каждый экранный столбец, находит экранные min/max и проводит до двух штрихов в порядке ближайшего к предыдущей конечной точке экстремума.** Для положительной ScrWidth окно индексов `(stoi(x),stoi(x+1)]`; для отрицательной — обратный проход.
- Из исходного DFM: дизайн `pbSpectrum=767×716` px, `Tahoma -13` при `PixelsPerInch=96`. При Windows 150% реальные runtime размеры/FontMetrics НЕ выведены из этих данных.

## Реализовано

- `mvk_compatible/core/tqgr_series_source_candidate.py`: чистая модель per-column min/max и последовательности штрихов, Single коэффициенты, клиппинг, ограничения размеров, без FFT/сетевых действий/изменения Y.
- `mvk_compatible/tests/test_stage111z31h_tqgr_series_source.py`: 23 локально пройденных варианта; включая одиночный пик среди **131072 Float32** и отрицательную развёртку X.
- `desktop/main_window.py`: **только для проверенного оригинального Power/Y** добавлен переключатель `Кривая TQGRSeries · минимум/максимум по пикселям`. Подлинный `PlotDataItem` сохраняется и временно скрывается; исходные штрихи рисуются отдельным `PlotCurveItem(connect='pairs')`. При отключении или возврате к архиву оригинальный график возвращается. Обычная работа приложения не меняется.
- `test_stage111z31h_qt_tqgr_series.py`: синтетические эталоны Tag0..3, неизменность полных Float32 Y и summary, zoom, обратимость, независимость от Stage31G сетки/растра, отсутствие утечки в архив.
- Дополнили CI запуском нового Qt-тестового файла под Windows `QT_SCALE_FACTOR=1.5`. **Зелёная CI и новый EXE подтверждаются только последним успешным запуском Actions; на момент первого коммита результаты ещё открыты.**

## Чего пока нет

Используются пиксели **логического Qt ViewBox**, не оригинального runtime `TQGrapher.PixelRect` и не точный программный `TCo2Draw` для кривой. Точные Win32 Font/FontMetrics/DPI, x87 округления, 1:1 screenshot/pixel diff не приняты. Численное совпадение четырёх ранее проверенных оригинальных GetSpectrum/Power/Y и Native Go R6.1 не менялось.

**Stage111Z31I:** объединить штрихи TQGRSeries с программным TCo2Draw в едином Bitmap-секвенсоре, затем выполнить одинаковый Tag0 screen-to-screen с измеренным physical DPI. Отдельно продолжать GetSignal и остальные функции по master plan. Не переделывать готовый FFT и не запрашивать повторные Tag0..Tag3 Power/Y.

## Сверка полноты главного интерфейса оригинала

Оригинальный приватный `mvkform.dfm` содержит **7** `TTabSheet`: `PageStart`, `PageConfig`, `PageStatus`, `PageAdc`, `PageSpectrum`, `PageFile`, `PageCalib`. В текущем автономном `MainWindow` регрессионный контракт фиксирует только **3** вкладки («Задачи», «Временной сигнал», «Спектр»). Следовательно, полная копия MVKView требует отдельной поэкранной функциональной реконструкции недостающих режимов и переходов — даже после достижения пиксельного паритета спектра. Сначала восстановить работу, затем сверять UI/UX с DFM и оригинальным EXE. Никакие приватные DFM/IDP/измерения для этой сверки в GitHub не помещались.
