# Stage 111L — исходный двухрядный TQGrapher.UpdateCursor и стенд сверки курсора

**Дата:** 29.10.2026. **Целевой проект:** MVKView Compatible Desktop, исследовательская ветка `research/stage111-mvkview-desktop-20261029` репозитория `shonentez-afk/MVK-Reader-Web`. **Внимание:** этот пакет создан локально, пока GitHub connector недоступен; наличие файла в ZIP **не означает коммит**.

## 1. Что дополнительно подтверждено по оригиналу

Непосредственно из пользовательского `Projects.7z` локально извлечены `Projects/_Unit114.pas`, `Projects/_Unit115.pas`, `Projects/_Unit128.pas`, `Projects/mvkform.dfm`; **оригиналы не включены в пакет** и не предназначены для публикации.

Исходная процедура `TQGrapher.UpdateCursor`, `_Unit115.pas:007CA76C–007CAAFB`:

- `007CA811–007CA832`: вне строгого интервала `PixelLeft < CursorPos < PixelRight` либо если первичная `Series[0].DataSize=0` — **очистить CursorString**, не пытаться извлечь FFT-бин.
- `007CA843–007CA870`: `CursorPos` — целое число пикселей исходного Delphi `TCanvas`. Сохраняется в Single перед вычислением `index=TRUNC((pixel-PixelLeft)*stoiM+stoiC)`; `end=index(pixel+1)-1`. Применяется saturating clamp к 0..DataSize-1.
- `007CA873–007CA8BE`: при `FindPreciseXValue` выбирается **наибольшая signed float32 амплитуда**, не модуль. При равенстве остаётся первый FFT-бин.
- `007CA8D4–007CA8E8`: координата вертикальной линии вычисляется **через независимые** `itosM/itosC`, Single-store и Delphi `@ROUND`. Подпись X отдельно получается из `index*Series0.XScale+Series0.XStart` и `007B2090(4)`.
- `007CA94A–007CAAF5`: исходный виджет поддерживает **ровно две серии**. Вторая проходит проверку длины и независимо выбирает собственный signed-максимум **в том же интервале FFT-бинов**, что первичная серия; совпадение координат найденного пика двух серий не требуется.
- **Исправление исследовательского предположения предыдущих этапов:** в исходном коде обе строки Y форматируются с **общим** `TQGrapher.YName` (`007CAA2C` и `007CAAD4`). Никакого отдельного имени оси второго ряда в этой процедуре нет.
- `007CAA47–007CAABB`: `CursorAveraging=3` вычисляет `sqrt(sum(v[k]^2))*YScale` **без деления на три**; граница исходного циклического массива при максимальном индексе может включить `DataSize` (выход за допустимый индекс в исходной реализации). Наш кандидат при таком крайнем случае **отказывает**, не эмулирует опасное чтение и не скрывает несовместимость.
- `007CA903–007CAAEE`: строка курсора: `fmt4(X) + ' ' + XName + CRLF + fmt4(Y0) + ' ' + YName [+ CRLF + fmt4(Y1) + ' ' + YName]`. Истинная локаль и Delphi RTL FormatFloat ещё **не доказаны**.

**Разделение трех величин:** mouse pixel, selected FFT-bin и snapped vertical line pixel — три разные операции с разными правилами округления. Qt-пиксель внутри PlotItem нельзя считать абсолютным Delphi TCanvas pixel без явного смещения и метрик оригинала.

## 2. Реализация в передаваемом пакете

1. `mvk_compatible/core/tqgrapher_multiseries_idr_candidate.py` — source-derived полный путь исходного mouse cursor для одной/двух float32-серий; общая YName, независимый peak каждого ряда, отдельный исходный snapped-pixel, fail-closed на опасных граничных усреднениях. **Только офлайн.**
2. `mvk_compatible/cursor_reference_compare.py` — CLI для локального оператора: приватные 14 метрик Canvas в JSON, один/два ряда спектра в `.npy` без pickle и оригинальный `CursorString` в TXT, координата исходного клика в абсолютных пикселях. Отчёт содержит только совпадение/индексы расхождений/хэши, **не сам сигнал, не оригинальную строку**. Даже при численном и текстовом совпадении флаги Delphi RTL/pixel/source parity остаются `false`.
3. `mvk_compatible/tests/test_tqgrapher_multiseries_idr_candidate.py` и `test_cursor_reference_compare.py`: 25 локальных синтетических тестов, включая два ряда, разные пики, безопасные края, signed максимум, правильную YName и безопасность приватных эталонов.

**Состояние тестирования:** выполнены `25 passed` локально на Python 3.13 с NumPy, pytest и минимальной копией интерфейсов Stage111K (`cursor_format_candidate`, `source_canvas_geometry`). **Полная регрессия репозитория и Windows EXE для Stage111L не выполнены; нельзя переносить цифры Stage111K.**

## 3. Как прогнать локальную сверку на ПК

После добавления файлов в рабочую ветку и установки зависимостей `mvk_compatible`:

```powershell
python -m mvk_compatible.cursor_reference_compare --metrics "C:\private\canvas-metrics.private.json" --series0 "C:\private\spectrum0.npy" --reference "C:\private\original_cursor.txt" --pixel 456 --averaging 3 --x-name "Гц" --y-name "м/с²" --decimal "," --line-pixel 457 --report-json "C:\private\cursor-diff.private.json"
```

Для второй серии добавить `--series1 "C:\private\spectrum1.npy"`; если исходный `TQGrapher.FindPreciseXValue` отключён — `--no-precise`. Важно: `--pixel` и `--line-pixel` — **абсолютные координаты в оригинальном Canvas**, не координаты относительно PlotItem Qt. `original_cursor.txt` — текст с исходными **CRLF** и оригинальной запятой/точкой. Содержимое приватных файлов не отправлять в публичный GitHub.

Коды CLI: `0` — совпадают строки/пиксель в заданном эксперименте, `1` — есть расхождения, `2` — некорректный/небезопасный ввод. Даже `0` **не** доказывает, что первоначальные исходные данные, font, sampling, локаль и Delphi x87 были действительно идентичны.

## 4. Что осталось и Stage111M

- Внести этот пакет в GitHub через исправно работающее соединение **без дублирования файлов**. В `stage111-desktop-offline.yml` добавить оба новых файла тестов в Linux и Windows core (сохранить остальные).
- Сравнить с **реальным оригинальным** `CursorString` и измеренными `TCanvas.TextWidth/Height` при том же размере окна, шрифте, DPI, X/Y диапазоне, DataSize и режиме FFT.
- При подтверждённых координатах внедрить источник-подобный двухрядный алгоритм в Windows Qt; пока не использовать его результат как оригинальный pixel-perfect cursor.
- Доказать двоичное округление Delphi `0042EE10` и `@ROUND`, затем корректно разбирать возможные различия TFormatSettings и x87.
- Провести полную CI на GitHub и собрать Windows EXE; только после этого указать новые числа PASS/artefact.
- `main`, v0.3.40 и прежняя ветка Stage110B остаются нетронутыми; никаких приборных TCP/10230 команд и публикаций оригинальных PAS/DFM/IDP/BIN/PCAP.
