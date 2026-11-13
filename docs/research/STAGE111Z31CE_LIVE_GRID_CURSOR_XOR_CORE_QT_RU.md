# STAGE111Z31CE — живая сетка и cursor/XOR/clipping на PageAdc + PageSpectrum

**Дата:** 13.11.2026. **Статус:** принят связанный функциональный пакет Core + действующий Qt + Windows EXE; оригинальная MVKView 1.0.47 НЕ признана полностью восстановленной.

## 1. Проверенные исходные зависимости

Доступный только локально операторский `Projects.7z/_Unit115.pas` подтверждает `TQGrapher.Draw` (007CAC68..007CB129): сетка TCo2Draw рисуется перед сериями, основные горизонтальные/вертикальные линии привязаны к уже принятой модели исходных 10 делений и к текущему ScrLeft/ScrWidth/ScrBottom/ScrHeight. Исходный цвет software-grid — #c0c0c0, белый фон. `TQGrapher.UpdateCursor` (007CA75C..007CAB03) игнорирует повторное целочисленное X; 007CA811..007CA825 допускает курсор только при `PixelLeft < CursorPos < PixelRight` и непустой первой серии; 007CA793..007CA803 удаляет ранее проведённые pmXor вертикальные/горизонтальные линии; 007CA8D4..007CA9F3 выбирает raw sample, ограничивает Y и рисует вертикальный+горизонтальный XOR. Второй источник series и исходный TextOut исходным процессом здесь не воспроизводились.

## 2. Реальная совместная реализация ядра и видимого Qt

- `mvk_compatible/core/original_live_grid_cursor.py`: независимый контракт `source_live_grid_frame` для текущего ViewBox с исходными Single делениями и строками, `source_live_cursor_hit` для strict source PixelRect (без дополнительного коэффициента Windows DPR) и `source_live_clip_crosshair` для fail-closed X/Y клиппинга **только представления**. Численные GetSignal/FIR/FFT/Power/Y/FRange и физическая калибровка не менялись.
- `mvk_compatible/desktop/source_live_grid.py`: единая Qt `SourceLiveGridOverlay` для настоящих графиков; цвет #c0c0c0, позади обеих кривых, `QPainter.setClipRect` по текущему ViewBox. Это **Qt QPen** с косметическим размером, не оригинальный антиалиас TCo2Draw/FPU blending.
- `mvk_compatible/desktop/source_plot_geometry.py`: создание overlay напрямую у реального ViewBox обеих страниц; обычный `PlotItem.clear` обновляет сигнал, сохраняя источник сетки. Возможность временно скрыть overlay для отдельного исследовательского software-bitmap.
- `mvk_compatible/desktop/main_window.py`: `PageAdc` (раньше только оранжевая вертикаль) получает из полной проверенной wave/FIR выборки **реальное видимое** кандидатное pmXor clGreen перекрестие; техническое состояние прежней `InfiniteLine` сохранено невидимым для старых обработчиков. У `PageSpectrum` прежний полный FFT + raw signed horizontal crosshair не заменён. Общий source X-hit по текущей `source_canvas_model` строго очищает курсор при достижении краёв; при изменении viewport стираются устаревшие линии. Исследовательский TCo2Draw bitmap по-прежнему независим и при его активации обычная source-Qt сетка скрывается.
- `mvk_compatible/desktop/xor_cursor_overlay.py`: вертикальное/горизонтальное перекрестие клиппируется по текущему Qt ViewBox, экстремальная Y насыщается только при отображении. Цифры и исходный отсчёт не меняются; native Win32 pmXor pixel parity не утверждается.

## 3. Регрессия и принятая сборка

Новые `test_stage111z31ce_live_grid_cursor_core.py` проверяют Single ticks, strict PixelRect, пределы, неизменность raw numeric Y, invalid viewport fail-closed. Новые `test_stage111z31ce_qt_live_grid_wave_xor.py` проверяют реальное отображение обоих живых графиков на синтетическом архиве, обновление grid при масштабировании, строгие крайние значения, исчезновение курсора при pan, сохранность полного N/2 спектра и SHA файла, сохранение сетки при refresh, независимость PageStatus. В обязательном CI остаётся предыдущий маршрут семи страниц/трёх форм — он **не** доказывает исчерпывающего покрытия всех обработчиков.

- Проверенный **исполняемый** source SHA `1090492192ee49c594e681e94a1793e0a7d9fb78`.
- [GitHub Actions #43371262445](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43371262445): **SUCCESS 3/3**, Linux Core **1844 passed / 97 skipped**, Windows Core **1994 passed / 7 skipped**, Windows Qt Smoke **49 passed**, Windows Qt DPI150 **121 passed** (фактический DPR=1.5).
- [Windows EXE artifact #14013250268](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43371262445/artifacts/14013250268): **68 948 620 байт**, до 27.11.2026; ZIP SHA256 `f1aaea7470db97f4368ec81d0bb750988dde47ccd5e5781ec826b701b882d473`; сам EXE SHA256 из сверенного PE-манифеста `77ce2719907a148ec92d1dd58cc09fb67e39a8492dbde637148b54cb57de9005`.
- [Synthetic UI/DPI150 artifact #14011974962](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43371262445/artifacts/14011974962): **639 182 байта**, до 20.11.2026.
- Первичная попытка `3c0ecadd` — Windows Core **1993 PASS / 1 новый E2E FAIL**: новый сценарий теста не выбирал короткое source окно и ожидал valid GetSignal из дефолтного исследовательского 1-с окна. В проверенной финальной версии сначала выбирается реальный source H=20 мс и добавлена диагностическая строка отклонений. Текущий CI прошёл, численное ядро не изменялось.

## 4. Границы доказательства и продолжение

По локальным PAS восстанавливаются формулы и условия, но **не** запущенная оригинальная Windows MVKView. Сетка видимого Qt использует QPainter и не повторяет битовый TCo2Draw rasterizer; зелёный XOR в Qt не доказан byte/pixel-identical Win32 pmXor при разном DPI, шрифте, clipping и GDI. Форматы подписей, TextWidth/Height, native считывание по исходному BIN, x87 0 ULP и калибровка прибора остаются открытыми. Закрытые PAS/DFM/IDP/BIN/Power/Y и оригинальный EXE не публиковались; x32dbg или прибор без нового разрешения не запускались.

**Следующий крупный пакет:** сверка исходного TCanvas Font/PPI/PixelRect, поведения clipping/событий всех остальных источников/страниц, расширенный E2E безопасных реальных операций семи страниц и трёх форм. Настоящее Win32 same-window сравнение допустимо только с отдельным оригинальным процессом и парой идентичных записей; синтетические результаты не подменяют его.
