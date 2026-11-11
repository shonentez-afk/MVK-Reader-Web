# Stage111Z31AY — исходный GDI pmXor прямо в общем TCo2Draw bitmap

**Дата:** 2026-11-11. **Ветка:** `research/stage111-mvkview-desktop-20261029`.  
**База:** Stage111Z31AX, source `0c5a2fe2bd4f33dd50439757083629f5f44f2bb3`, CI #42949383047 SUCCESS.

## Причина этого пакета

После AX курсор находил правильные FFT-бины по внутреннему Source PixelRect, но при активном едином программном TCo2Draw его **линии продолжали рисоваться отдельным QtSpectrumXorCursor**, то есть в физическом QPainter RasterOp поверх изображения. При Windows DPI 150% этот путь **не гарантирует исходные логические 1-пиксельные GDI линии**. Qt также мог рисовать курсор на всю ViewBox, включая поля подписи осей, вместо source PixelLeft/Right/Top/Bottom.

Приватная операторская `_Unit115.pas` была проанализирована только локально; оригинальный текст/IDP/DFM не копируются в GitHub. Проверенный source-контрольный поток:
- `007CA793..007CA7AF` TCanvas.Pen.Color = VCL clGreen (RGB 0,128,0), Mode=pmXor.
- `007CA7B6..007CA7D2`: стереть прошлую вертикаль (X, PixelTop -> X, PixelBottom).
- `007CA7DB..007CA80F`: стереть предыдущие горизонтали двух серий (PixelLeft -> PixelRight).
- `007CA811..007CA900`: новый X, поиск точного FFT-бина и вертикаль; `007CA9D8..007CA9F0`: горизонталь raw Y, а НЕ усреднённый CursorString.
- `007CAAFB..007CAB03`: возврат Pen.Mode=pmCopy.

## Код

1. `mvk_compatible/core/tqgrapher_bitmap_xor_cursor.py` — рисование XOR в *точном том же* 32bpp RGBA-графике, на основе уже проверенного `GdiLineTo`/`xor_gdi_line` Stage111P. Каждая линия имеет **исключённый terminal pixel**; точка пересечения XOR-ится **дважды** и остаётся фоновой, как в GDI. Изображение неизменяемо на входе, оригинальный FFT и исходные данные никогда не трогаются. Каждый кадр создаётся заново из чистого TCo2Draw base, чтобы смена окна, zoom/resize/brush не оставляла скрытый след от прошлого курсора.
2. `mvk_compatible/desktop/main_window.py`: при активном исследовательском composite-режиме обратное изображение с XOR показывается через ТОТ ЖЕ `pg.ImageItem.setImage`. Отдельная Qt RasterOp линия скрывается; координаты определяются уже восстановленным AX PixelRect/itos. При выходе мыши за PixelRect восстанавливается исходный bitmap; при новой шкале/панорамировании/resize сбрасывается mouse X cache, поэтому тот же X после zoom пересчитывается по новому ScrLeft/Width. При обычном архивном Qt-режиме остаётся прежний путь.
3. Синтетические тесты: `tests/test_stage111z31ay_tco2draw_cursor_bitmap.py` проверяет clGreen/pmXor и исключение конца GDI LineTo, double-XOR пересечение, чёрную кривую, неподвижность исходного RGBA, восстановление при смене позиции и некорректные входы. `tests/test_stage111z31ay_qt_bitmap_cursor.py` проверяет реальное Qt ImageItem для Tag0/Tag3, выход курсора из PaintBox, отмену при zoom, исключение дублирующего Qt-кроссхейра. В `.github/workflows/stage111-desktop-offline.yml` тест включён в **Windows 150% DPI** прогон.

## Граница достоверности

Это точнее соответствует **алгоритму source TQGrapher/TCo2Draw**, но **НЕ заявляет pixel-to-pixel равенство с работающей Delphi**: шрифт runtime PaintBox.Canvas, DPI awareness оригинала, FontMetrics, фактическая ширина PaintBox и Win32 TBitmap Scanline orientation без same-window оператора не сверены. Те же оригинальные Code20/LOG0 данные ранее численно 0 ULP в одном окне, но это отдельный результат. Финальный показ AX в Qt пока также является исходным **кандидатом**.

**Запрещено:** публикация оригинального IDP/PAS/DFM/BIN/скриншотов, повтор x32dbg/F9 без отдельного разрешения, изменение приборного протокола, переписывание FIR/FFT/LOG/Native. После графической parity-приёмки разрешён следующий пакет Config/Calib только с доказанной read-only семантикой.

## Критерий приёмки

Linux Core PASS; Windows Core/Qt + DPI150 PASS (включая AY-тесты); Native build и автономный Windows EXE PASS. Итоговый CI и source SHA добавляются ПОСЛЕ фактического результата; до этого статус **не принят**.

## Заключительная приёмка по GitHub Actions (11.11.2026)

- **Source commit:** `5f8dc3b855725a2432e7d96504d3b4185ae49b16`.
- **Workflow:** [#42952035819](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42952035819) **SUCCESS**. Все три jobs PASS: Linux — all offline core tests, Windows — offline core and Qt smoke tests (включая original TQGrapher/bitmap cursor при `QT_SCALE_FACTOR=1.5`), Windows — verified autonomous EXE artifact.
- **Artifact:** [MVKViewCompatible_Stage111_Windows_Preview #13825751703](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42952035819/artifacts/13825751703); 68 609 126 байт, срок доступа до 2026-11-25. Контрольные суммы EXE проверены workflow. Операторская Windows копия автоматически не заменяется.
- Во время тестов обнаружили и устранили отложенное `sigResized`, сбрасывавшее курсор; теперь source pointer X перепроецируется на новый PixelRect при перерисовке. Отдельно исправлен тест Tag3: координаты выхода должны браться из актуального `sceneBoundingRect`.
- **Граница:** оригинальный Windows Delphi процесс и GDI PaintBox реального окна не запускались; real same-window pixel diff и фактический TCanvas Font/PPI ещё не приняты. Код FIR/FFT/LOG/Native не меняли.
