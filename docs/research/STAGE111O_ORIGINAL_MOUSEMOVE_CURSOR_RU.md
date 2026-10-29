# Stage111O — оригинальный TQGrapher MouseMove и быстрый GetSignal hover

**Дата:** 2026-10-29. **Ветка:** `research/stage111-mvkview-desktop-20261029`.  
**Точный программный SHA:** `aa3a0dd0a11e9821dfbfd350f16dfbb8bcc19fde`.

## 1. Подтверждено приватным оригинальным Delphi

- `_Unit128.pas:0084B4AC–0084B4E4`: `pbAdcMouseMove` передаёт X и Canvas в `TQGrapher.UpdateCursor`, затем отображает `CursorString` в `lbAdcHint`. Это движение мыши, не click.
- `_Unit128.pas:0084C918–0084C950`: `pbSpectrumMouseMove` аналогично вызывает `UpdateCursor` и обновляет `lbSpecHint`.
- `_Unit115.pas:007CA75C–007CA76B`: если новый целый X равен сохранённому `CursorPos`, оригинал ничего не пересчитывает и не рисует.
- `_Unit115.pas:007CA793–007CA7B0` и `007CAAFB–007CAB03`: оригинал задаёт цвет пера `0x00008000` (VCL clGreen), режим `pmXor` (0x0E) для повторного стирания линий, затем возвращает `pmCopy` (0x04).
- `_Unit115.pas:007CA811–007CA832`: курсор очищается при выходе по X за PixelLeft/Right. В обработчике UpdateCursor Y мыши не применяется.

Это SOURCE-STRUCTURE VERIFIED, **не** оригинальная GDI-пиксельная приёмка. Приватные PAS/DFM/IDP не опубликованы.

## 2. Реально реализовано

- `desktop/main_window.py`: `scene().sigMouseMoved` теперь подключён к графикам «Временной сигнал» и «Спектр». Курсор следует за движением X без обязательного клика. Старые обработчики клика оставлены для совместимости.
- Повторное целое X пропускается; Y не влияет на выбор бина, выход за горизонтальные границы скрывает линии/подпись.
- Спектр по-прежнему использует **непрореженный полный FFT**, а горизонтальная линия строится по raw signed peak, а не по подписи averaging=3; две серии искусственно не добавляются.
- Новый `core/waveform_hover_idr_candidate.py`: кэширование одного локального окна оригинального GetSignal-кандидата; дальнейший выбор отдельного отсчёта O(1), без повторного чтения всего BIN и вычитания DC на каждом пикселе. Поддерживаются AC/AC+DC и оба порядка GetSignal. При неаттестованной огибающей курсор не подменяет отсутствующий оригинал.
- Qt Plot ViewBox pixel mapping остаётся **кандидатом**, не зарегистрированным оригинальным Delphi TCanvas. Qt InfiniteLine не является оригинальным GDI XOR.

## 3. Новые проверки

`test_waveform_hover_idr_candidate.py`: synthetic AC/AC+DC и reverse, запрет некорректных координат, однократное чтение подготовленного окна, сравнение с существующим `OfflineSession.exact_sample`.

`test_desktop_qt.py`: три новых offscreen сценария MouseMove для обоих графиков, повторного X и отказа от неподтверждённой огибающей.

**CircleCI на одном программном SHA:**

| Проверка | Итог | URL |
|---|---|---|
| Linux Core #30 | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/30 |
| Windows Core + Qt #31 | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/31 |
| Windows Preview EXE #32 | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/32 |

Полные счётчики pytest и побитовая контрольная сумма скачанного EXE пока отдельно не получены. Артефакт в настройке CI: `MVKViewCompatible_Stage111_PREVIEW.exe`, `SHA256SUMS.txt`, `BUILD_INFO.txt`.

## 4. Что НЕ подтверждено

Оригинальный Delphi Canvas/Font/DPI и GDI XOR-пиксели, математическая идентичность x87/FormatFloat/CursorString, реальные FFT/FRange/GetSpectrum/Narrowband на том же BIN и окне, оригинальный двухрядный курсор и UX всех трёх вкладок. Оригинальные AUX4700 не заменялись локальным FFT, реальный прибор не использовался.

## 5. Продолжать с Stage111P

1. Извлечь Windows Preview из CircleCI Artifacts, сверить EXE с `SHA256SUMS.txt` и SHA `BUILD_INFO.txt`.
2. Восстановить оригинальную последовательность рисования/стирания clGreen/pmXor и точно измеренный Canvas Font/DPI без притворного пиксельного паритета Qt.
3. Приватно сравнить настоящий original CursorString/DrawnX/DrawnY с текущим кодом на идентичном окне; развивать Original FFT/FRange и три вкладки.
4. После каждого изменения проверять CircleCI Linux, Windows Qt, EXE; отчёты/матрицу/handoff/статус поддерживать. Не менять main, v0.3.40 и не подключать прибор без разрешения.
