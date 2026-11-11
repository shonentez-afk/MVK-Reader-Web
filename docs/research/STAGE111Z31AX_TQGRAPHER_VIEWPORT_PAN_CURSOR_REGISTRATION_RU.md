# Stage111Z31AX — синхронизация растрового TQGrapher, прокрутки и курсора по источнику

Дата: 11.11.2026. Рабочая ветка: \`research/stage111-mvkview-desktop-20261029\`.
База: Stage111Z31AW, последний успешный source \`52490051137ca3e0c09e3e435e7827a44b67e40c\`.
Приоритет пользователя: TQGrapher/TCo2Draw график целиком прежде Config/Calib.

## Обнаруженный реальный разрыв
Старый \`_sync_source_tqgrapher_grid_candidate\` сравнивал только список делений/надписей 10×10, флаги растрового/совместного режима и размер картинки. При панорамировании на 1 Гц и неизменном наборе подписей внутренний пиксельный растр и подписи TCanvas оставались от старого диапазона. Это некорректно: Source PixelRect и TQGRSeries должны быть переотображены для нового ScrLeft/ScrBottom. Независимый \`_sync_source_tqgr_series_candidate\` уже кэшировал точные границы, но сам общий bitmap — нет.

Курсор \`_spec_at_scene_pos\` раньше всегда строил геометрию с \`PixelLeft=0\`, \`PixelRight=width(ViewBox)\`, тогда как исходная \`_Unit115.pas\` вычисляет внутренний \`PixelLeft=Margin+TextWidth('0')+TextWidth('0.000000')\`, \`PixelRight=CanvasWidth-Margin\`, исходные \`stoiM/stoiC\` и независимые \`itosM/itosC\`. В совместном оригинально-ориентированном растре курсор не соответствовал нарисованной кривой; область подписей ошибочно могла выбираться как FFT-бин.

## Изменения
- \`core/tqgrapher_viewport_sync_source.py\`: проверяемая сигнатура точного viewport/raster/combined, преобразование координаты Qt scene-local X → source PaintBox X, возврат уже имеющегося \`cursor_geometry_from_canvas\`, source candidate преобразование позиции XOR по \`itosM/itosC/ytosM/ytosC\`.
- \`desktop/main_window.py\`: в raster-кэше учитываются все четыре границы Scr, ширина/высота и режим. Оригинальный composite возвращает *тот же* source canvas для курсора. При попадании в боковые подписи/поля исходного canvas курсор стирается вместо подстановки нулевого FFT-бина. Вертикальная линия и горизонталь XOR проецируются на реальные source-координаты растровой линии, а не на предыдущее \`(frequency_hz,raw_y)\` всего Qt ViewBox. При обычном нерастровом режиме сохранён старый Qt путь.
- \`tests/test_stage111z31ax_viewport_cursor_source.py\`: чистые синтетические граничные проверки; \`test_stage111z31ax_qt_pan_cursor.py\`: четыре инварианта — 1 Гц пан без изменений подписей перестраивает картинку; старая ImageItem удаляется; курсор внутри source PixelRect совпадает с проекцией рисунка; Float32 массива спектра не меняются.

## Ворота приёмки
PASS требуется по Linux Core, Windows Core/Qt DPI150%, verified autonomous EXE. Самого исходного оригинального Windows TCanvas font/DPI/pixel-perfect screenshot тут НЕ сравнивали; паритет всего окна MVKView НЕ ЗАКРЫТ. Исходные приватные IDP/PAS/BIN/PNG и GigaCode capture ZIP не публикуются; повторных live x32dbg/F9 нет. Проверенная численная цепочка Code20/LOG0 — отдельный прежний результат для одного окна 0 ULP; FIR/FFT/LOG/Native R6.1 не менялись.

## Следующий функциональный пакет
Оригинальные runtime TextWidth/Font/PPI/PixelRect на DPI150%, точные ScanLine/Font/GDI пиксели для графика и compare same-window screenshots (при наличии оператора), затем source grid/PageConfig/Calib только с read-only подтверждённой семантикой. Не объявлять 1:1 до фактического pixel diff.
