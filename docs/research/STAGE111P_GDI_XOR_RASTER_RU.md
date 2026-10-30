# Stage 111P — оригинальный GDI XOR TQGrapher: исходная растеризация и независимый эталон

**Дата:** 30.10.2026  
**Исследовательская ветка:** `research/stage111-mvkview-desktop-20261029`  
**Исходный программный SHA:** `38a895fd797e300fbc967f7e97700828c4330106`  
**Архитектура:** единая автономная Windows Qt/PySide6, `mvk_compatible/`; никакого возврата Web, никакого соединения с МВК.

## 1. Подтверждено непосредственно приватным оригиналом

Оригинальные `Projects.7z`, `mvkview.idp` остаются приватными, исходные файлы и содержимое IDP в GitHub не публиковались. Исследованы оригинальные реконструированные инструкции `_Unit115.pas`:

- `007CA75C–007CA76B`: `TQGrapher.UpdateCursor` при неизменном Integer X сразу возвращается.
- `007CA793–007CA7AB`: цвет пера `0x00008000` (VCL `clGreen`) и режим `TPen.pmXor` (`0x0E` как enum VCL).
- `007CA7B6–007CA7D2`: прежде всего повторно рисуется и стирается сохранённая вертикаль `CursorDrawnX`, `PixelTop→PixelBottom`, затем снимается `CursorDrawn`.
- `007CA7D6–007CA80F`: по индексам 0 и 1 повторно рисуются старые горизонтали `PixelLeft→PixelRight` при установленном per-series `CursorDrawn`, после чего сбрасываются отдельные флаги.
- `007CA811–007CA832`: проверка строго внутренней области `PixelLeft < CursorPos < PixelRight`; при выходе очищается CursorString, новая линия не создаётся.
- `007CA8D4–007CA900`, `007CA9BA–007CA9F0`: построение новой вертикали и горизонтали; подпись при averaging=3 остаётся независимой от исходного raw Y.
- `007CAAFB–007CAB03`: возврат режима пера в `pmCopy` (`0x04` как enum VCL).

Спецификация Win32 GDI от Microsoft подтверждает: `LineTo` закрашивает линию **до, но без конечного пикселя**; режим `R2_XORPEN=7` выполняет побитовое XOR цвета текущего пикселя и пера, а два применения к одному пикселю восстанавливают его.
Документы: https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-lineto и https://learn.microsoft.com/en-us/windows/win32/gdi/binary-raster-operations

## 2. Реализовано в независимом приложении

1. `mvk_compatible/core/tqgrapher_gdi_xor_idr_candidate.py`: независимая 24-битная RGB uint8-модель рисования 1px `MoveTo/LineTo` с **exclusive endpoint** и маской `(R,G,B)=(0,128,0)`. Исполняет SOURCE-порядок erase-old-vertical → erase-old-Y0/Y1 → draw-new-vertical → draw-new-Y0/Y1. Совпадающий Integer X — no-op, выход за экранный X скрывает линии; повторный XOR восстанавливает исходное изображение.
2. Предусмотрены два Y-ряда, даже если текущий Qt график спектра показывает один. Модель принимает структуру от `original_cursor_crosshair` и **не** использует усреднённое значение `CursorString` для высоты горизонтали.
3. Проверяются происхождение исходных структур, непрямоугольные/внекадровые линии, габариты, типы пикселей, смена размера изображения. Ошибочная новая линия не должна повреждать предыдущий кадр и состояние. Нет скрытого масштабирования/антиалиасинга.
4. `mvk_compatible/gdi_xor_reference_compare.py`: **приватная** диагностическая сверка локальных RGB `.npy` кадров Canvas ДО и ПОСЛЕ одного `UpdateCursor`. Отчёт содержит SHA256 локальных входов, число различающихся пикселей/каналов, но **не** пиксели или приватные original-координаты. Отвергает symlink, pickle, большие входы и разные размеры.
5. Новый synthetic Windows-only `test_tqgrapher_gdi_xor_win32.py`: настоящий `gdi32.CreateDIBSection` 32-bpp top-down, `SetROP2(R2_XORPEN)`, `MoveToEx/LineTo`; попиксельное сравнение с собственной моделью на синтетическом изображении. На Linux этот тест пропускается.

**Это НЕ внедрение оригинального GDI поверх живого Qt PlotWidget.** Qt InfiniteLine продолжает давать совместимый по смыслу курсор; смешивать прямые GDI HDC-записи с независимой Qt перерисовкой без явной регистрации устройства/шрифтов было бы неверно.

## 3. Регрессия и доказательства

Приватно локально: 9 синтетических проверок ядра XOR — PASS, 3 проверки частного сравнения — PASS; Windows Win32-тест не исполняется на Linux. В GitHub добавлены также проверки независимого 1/2-series crosshair и fail-closed интерфейса.

**CI для программного SHA `38a895fd797e300fbc967f7e97700828c4330106`:**
- Linux Core: [CircleCI #39](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/39) — SUCCESS по GitHub status.
- Windows Core и Qt: [CircleCI #40](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/40) — SUCCESS; включён оригинальный Win32 GDI synthetic benchmark.
- Windows Preview EXE: [CircleCI #41](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/41) — SUCCESS (job); бинарный SHA скачанного EXE ещё НЕ сравнивался с SHA256SUMS.txt.

Предыдущий успешно проверенный HEAD до Stage 111P: `8c4d199c115168a31fe21248c33d328b35ddef3f`, [Linux #34](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/34), [Windows Core+Qt #33](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/33), [EXE #35](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/35): SUCCESS. Цифры количества pytest и SHA скачанного EXE по одному GitHub status API **неизвестны**.

## 4. Неподтверждённое / ограничения

- Нет подтверждённых оригинальных screenshots `before/after` с одинаковым приватным архивом/Canvas; реальный Delphi пиксельный паритет остаётся **NOT VERIFIED**. Даже положительный синтетический Windows GDI тест доказывает только Win32 raster mode, **не** оригинальное TQGrapher окно.
- Нет оригинальных Font/TextWidth/TextHeight, DPI, PixelRect регистрации относительно Qt / координат панели, графика и ScrollBar.
- До точного оригинального экрана не переносить в рабочий Qt режим рискованный GDI XOR; возможен research-only offscreen mode.
- Не закрыты x87/FormatFloat, оригинальные CursorString, двухрядный UX, FFT/GetSpectrum/GetNarrowbandValue/FRange на одном приборном окне.
- AUX4700/VALUES — единственный штатный источник приборных DSP значений. Локальный FFT остаётся исследовательским кандидатом, прибор не подключался.

## 5. Инструкция приватной сверки

Снимки исходного Canvas до/после движения **одного** Integer X необходимо превратить локально (вне GitHub!) в `np.uint8 RGB [height,width,3]`, сохраняя точные 1:1 пиксели. В `canvas.json` — только source Canvas geometry, в `crosshair.json` — предсказанные точки из source-селектора. При строго одинаковой подложке:

```powershell
python -m mvk_compatible.gdi_xor_reference_compare --before C:\Private\before.npy --after C:\Private\after.npy --canvas C:\Private\canvas.json --crosshair C:\Private\crosshair.json --mouse-x 120 --confirm-identical-canvas --report-json C:\Private\xor-errors.json
```

**Не загружать** оригинальные screenshot/IDP/PAS/DFM/BIN/PCAPNG в GitHub или CircleCI. Даже нулевая ошибка при синтетической паре не доказывает Delphi-паритет.

## 6. Следующая точка — Stage 111Q

1. Проверить текущую полную CircleCI на точном source SHA (Linux Core, Windows Core/Qt, Windows EXE), скачать Preview и независимо сравнить SHA256SUMS.
2. Сделать полностью offscreen pixel reference через настоящий оригинальный TCanvas same-window: Font/DPI/PixelLeft/Right, CursorDrawnX/Y, две строки и исходный CursorString.
3. Только после измерения оригинала рассмотреть настоящую Qt реализацию данного XOR/клиппинга; впоследствии продолжить FormatFloat/x87, GetSpectrum/FRange, UX трёх вкладок. **main** и v0.3.40 остаются неизменными.
