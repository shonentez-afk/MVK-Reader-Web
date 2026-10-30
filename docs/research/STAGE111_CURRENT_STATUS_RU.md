# MVKView Compatible — текущий статус Stage 111Q (30.10.2026)

**Ветка:** research/stage111-mvkview-desktop-20261029  
**Программный SHA:** 1baf980e611f55d38618b4dc170e8662089eaf62  
**Продукт:** полноценный автономный Windows Qt/PySide6 аналог оригинальной MVKView. main и Web v0.3.40 не изменять.

## Подтверждено источником / реализовано

- Stage111P: independent GDI XOR model с 1px native LineTo endpoint exclusive, один/два ряда; Windows synthetic CI и EXE #41 SUCCESS.
- Stage111Q: исходная формула min(Width div 53, Height div 30), минимум Margin=10 и виртуальный Canvas 3×Margin подтверждены оригинальным приватным Delphi для обоих PaintBox. Исправлена Qt-диагностика, добавлены source scrollbar anchors и Windows memory GDI font probe по независимому явно выбранному HFONT.
- Синтетические локальные 26 pure-core tests PASS. [Linux #49](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/49) SUCCESS; [Windows Core+Qt #48](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/48) SUCCESS. **Windows Preview EXE и его скачанный SHA256 на момент составления ещё не подтверждены**.
- Приборные штатные DSP показатели только из AUX4700/VALUES, локальный FFT не заменяет их. Без сетевого подключения к МВК.

## Непроверенное / блокеры

Нужен приватный оригинальный TPaintBox Canvas размер+Font.Name/Height/Style+TextWidth/Height+DPI на идентичном окне; пока Qt QFontMetrics не следует принимать за исходный Delphi. Нет оригинальных эталонных CursorDrawnX/Y, 2-series CursorString, реальных x87/FormatFloat и численного GetSpectrum/GetNarrowbandValue/FRange паритета. GDI XOR на живой Qt PlotWidget не интегрирован без проверки устройства и DPI; оригинальная пиксельная идентичность НЕ доказана. Скачанный Preview EXE и SHA256SUMS ещё не сравнивались.

## Продолжение

[Отчёт Stage111Q](STAGE111Q_PAINTBOX_FONT_DPI_RU.md), [Матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md), [Handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md), [Инструкция нового чата](../../START_NEW_CHAT_RU.md).

**Stage111R:** проверить весь CircleCI и файл EXE/SHA, затем приватная регистрация оригинальных Font/DPI/PixelRect и сопоставление с Qt+GDI, RTL/x87/FFT. Никаких PAS/DFM/IDP/BIN/PCAPNG в GitHub или CircleCI. Не менять main/v0.3.40 и не подключать реальный прибор без разрешения.
