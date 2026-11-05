# Stage111Z31M — Windows GDI TextOut + офлайн попиксельная сверка спектра

**Дата:** 05.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. Цель: полная автономная копия оригинальной MVKView; **СПЕКТР до конца**, затем временной сигнал, расчётные данные и только потом страницы.

## Как ускоряем разработку без потери достоверности

Вместо десяти мелких коммитов/запусков GitHub Actions внесены **10 связанных файлов ОДНИМ** Git tree commit `3800580598ed9dfeded649f7060d383b63a5f968` с **одним полным циклом CI и одним EXE**. Подтверждённый в Stage111Z8 оригинальный N262144 Float32 FFT `131072/131072` **не трогали и не проверяли заново**. Новые исследования ведём только по открытым вопросам spectrum graphics / other-N / envelope.

## Независимое подтверждение исходного принципа

В локальном приватном `Projects.7z` изучен реальный дизассемблированный `_Unit115.pas`. **Исходники PAS/DFM/IDP/бинарные измерения в GitHub/CI не загружались.**

- `_Unit115 007CACB3..007CACF9`: `TQGrapher.Draw` создаёт внутренний `TCo2Draw` и `TBitmap pf32bit`, устанавливает `Brush.Style=bsClear`, копирует настоящий `TPaintBox.Canvas.Font` через `TFont.Assign`. Подписи рисуются **VCL TCanvas.TextOut**, не Qt.
- `mvkform.dfm`: базовый дизайн `Tahoma`, `Font.Height=-13`, `DEFAULT_CHARSET`, `PixelsPerInch=96`; `pbSpectrum` в дизайне `767×716` px. **Не доказано, что runtime на Windows 150% использует именно -13 px или размеры 767×716 физических пикселей**. Исходный процесс может быть DPI-aware или виртуализирован Windows.
- Исходный порядок слоёв не изменён: белый 32-bit холст → серые линии → оригинальные TextOut координаты → чёрная min/max per-column TQGRSeries → рамка. Расчёт спектра и Float32 исходный Power/Y не менялись.

## Что сделано

**Код пакетом:**
1. `mvk_compatible/desktop/win32_gdi_source_candidate.py` — настоящий Windows `CreateFontW`/ `GetTextExtentPoint32W` / `TextOutW`, прозрачный текст на top-down RGBA/32bpp DIB. И ширина текста, и `TextHeight`, и глифы берутся из **одного и того же** native GDI font. Управление ресурсами DC/HFONT/HBITMAP с освобождением, безопасные границы изображения и символов, входные RGBA не изменяются. Диагностика содержит запрошенный DFM font и измеренные GDI значения, но **оригинальный runtime font и PPI не объявляются проверенными**.
2. `desktop/main_window.py` — при исследовательском сочетании трёх УЖЕ существующих опций для локального SHA-verified оригинального Power/Y под Windows используется единый `GDI TextOut`-кандидат; на Linux остаётся прежний безопасный Qt QPainter fallback. Отдельные Qt подписи скрываются только на время единого растра и возвращаются при отключении. Архив, Go Native R6.1, FFT, меню/страницы и стандартный режим не менялись.
3. `core/tqgrapher_composite_source_candidate.py` и `core/tqgrapher_textout_source_candidate.py` — отдельное имя provenance `gdi_reconstructed_from_dfm`; **не смешивать** его с `original_runtime_verified`. Qt прежние тесты и входные контракты сохранены.
4. `core/spectrum_bitmap_diff.py` — Python/NumPy для двух RGB(A) кропов **одинакового физического пиксельного размера**, считает exact пиксели, ошибки на непустых (небелых) участках, пороги 1 и 8, необязательный сдвиг до ±5 px. Пустой белый график не считается успехом. Результат только агрегаты, никаких исходных картинок/имен/путей.
5. `desktop/spectrum_screen_diff_cli.py` — читает **исключительно локальные PNG** через QImage, принимает две независимые прямоугольные обрезки и выдаёт JSON-проверку без сети или записи user screenshot на сервер.
6. Новые тесты: `test_stage111z31m_gdi_and_bitmap_diff.py`, `test_stage111z31m_qt_win32_gdi.py` (четыре спектральных режима на реальном Windows GDI), `test_stage111z31m_screen_diff_cli.py`. Новые Windows GDI UI тесты выполняются также при проверенном Qt DPR=1.5. Рабочий repo code SHA выше.

**Локальное сравнение PNG:** при наличии оригинального Tag0 и PNG именно текущей сборки, по два одинаковых прямоугольника `W×H` в **физических** пикселях:

```powershell
python -m mvk_compatible.desktop.spectrum_screen_diff_cli --original "C:\PRIVATE\tag0_original.png" --candidate "C:\PRIVATE\tag0_clone.png" --original-crop "X,Y,W,H" --candidate-crop "X,Y,W,H" --shift-radius 3
```

`X,Y,W,H` заменить реальными целыми координатами окон одинакового размера; если PNG уже содержит ровно график, аргументы `--original-crop` и `--candidate-crop` можно опустить. Не сравнивать картинки разного DPI/размеров без явной согласованной шкалы и не выдавать автоматический shift за доказательство верного исходного PixelRect. Команда проверяет только два локальных пользовательских файла, сами PNG никуда не уходят.

## Проверенная регрессия и EXE

**Тестированный КОД SHA:** `3800580598ed9dfeded649f7060d383b63a5f968`.

[GitHub Actions #41985004267](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41985004267): **3/3 SUCCESS**.

| Gate | Итог |
|---|---:|
| Linux Core | **1424 pass /48 skip /1 warning /30 subtests** |
| Windows Core (включая native GDI+bitmap diff) | **1469 pass /7 skip /1 warning /30 subtests** |
| Windows Qt | **49 pass** |
| Windows Qt DPR=1.5 | **41 pass**, реальный Qt DPR подтвердился как 1.5 |
| Go Native R6.1, PyInstaller, manifest/SHA/PE | **PASS** |

[Windows EXE artifact #13395094848](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41985004267/artifacts/13395094848): ZIP **68 556 134 B**, SHA256 ZIP `29d25e1334d39d64af4ee13395a67c65d22bb10ccda9e0ffa47757b883d2c943`. Внутри `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `3b6550003ce57b5a9d0b2d4aac5e4c311220acf74057f11ff03160ba7a7e73b9`. EXE source commit independently verified, артефакт истекает **2026-11-19T07:13:12Z**.

## Строгие незакрытые спектральные ворота

**Не объявлять spectrum 1:1 только по этому коммиту.** GDI-кандидат лучше предыдущей Qt-подписи, но **известен только дизайн DFM**, не фактические original `TPaintBox.Canvas.Font`/PPI/физический размер на 150%, и не получен same-input original/clone screenshot diff. Единый растр по-прежнему размещается в Qt Plot ViewBox, поэтому отдельная проверка полного исходного `PaintBox` без двойных Qt осевых полей необходима. Дальше Stage111Z31N: одна пара исходный/новый **Tag0 одного диапазона**, физический ROI и объективный diff, по нему исправлять вместе (1) original runtime PixelRect/font/scale, (2) физические GDI глифы и TCo2Draw, (3) курсор/zoom/xor, (4) clipboard/bitmap export. Затем mode envelope original same-window / другие N/Fs. Не переснимать и не переделывать уже принятые original FFT N262144, 4×Power/Y и summary.

**Строгий порядок разработки: СПЕКТР полностью → ВРЕМЕННОЙ СИГНАЛ → РАСЧЁТНЫЕ ДАННЫЕ → ОСТАЛЬНЫЕ СТРАНИЦЫ.** Старую Web архитектуру и стабильный main не менять.
