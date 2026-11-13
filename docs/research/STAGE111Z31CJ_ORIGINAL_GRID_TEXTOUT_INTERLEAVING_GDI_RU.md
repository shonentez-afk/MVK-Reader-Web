# STAGE111Z31CJ — оригинальное чередование линий и подписей TQGrapher, быстрая GDI-растеризация

**Дата:** 13 ноября 2026. **Статус:** приняты Core + действующие Qt PageAdc/PageSpectrum + автономный EXE. Это НЕ полный оригинальный MVKView 1.0.47 с проверенной Win32/GDI/x87 1:1 совместимостью.

## Источник: проверенные частные операторы оригинального Draw

Операторский `Projects.7z/_Unit115.pas` извлечён ЛОКАЛЬНО через libarchive для анализа и НЕ опубликован. Исходный `TQGrapher.Draw` содержит:

- `007CAD77..007CAE35`: каждый горизонтальный TCo2Draw stroke и сразу соответствующий Y tick `TCanvas.TextOut`; исходные NoVText/Source HLineSpacing управляют выводом
- `007CAEA9..007CAF6B`: для положительного `ScrWidth` каждый вертикальный stroke сопровождается своим X tick `TextOut`, индекс возрастает
- `007CAFBE..007CB080`: при отрицательном `ScrWidth` свой отдельный цикл — индекс убывает; это важно для обратного времени PageAdc
- `007CB086..007CB129`: после циклов YName, затем XName; далее `007CB12F..007CB3E5` — исходные min/max TQGRSeries, `007CB3FF` — чёрная рамка

CI до CJ исполнял все линии, затем все GDI tick labels в одном batch — конечный bitmap не учитывал микропорядок. **Новый CJ исполняет чередование в одной RGBA-памяти**, что устраняет этот конкретный разрыв. Параметр формата подписи `007B2090`/Delphi FormatFloat и реальный native GDI x87 округления остаются отдельными открытыми вопросами.

## Реальное внедрение, без разрыва Core и интерфейса

`mvk_compatible/core/original_live_whole_paintbox.py`: source-derived `WholePaintboxPlan` сохраняет пары grid line / matching tick event по исходным float32 source values. При `ScrWidth<0` разворачивается именно X loop, не полный числовой массив. `WholePaintboxTask` исполняет этапы **Y grid line → Y TextOut, X grid line → X TextOut, YName, XName, full per-column series, black frame**; ограничивает число tick-операций за порцию; перед публикацией формирует проверяемые `source_draw_trace`, исходный Float32 SHA, RGBA SHA и явно ложные флаги original pixel parity. Строки и source samples не модифицируются. `close()` освобождает GDI на finish/cancel/failure.

`mvk_compatible/desktop/source_live_composite.py`: на реальных обычных PageAdc + PageSpectrum сохраняет общий Source PaintBox, рисует не более 4 native grid/tick пар за Qt event-loop turn; series/frame идут порциями до 128 strokes; старый кадр и подписи удаляются при zoom/pan/new source, Qt fallback остаётся безопасным. Остальные страницы и исследовательский оригинальный Power/Y не подменяются данными растрового кандидата.

**Защита производительности:** первоначальный `bf9fc7ce` делал много полных копий 32-bit bitmap, по одной на каждую подпись; собственный GDI-глиф часто становился дороже всего исходного ряда. Принятый `5766c337`: `desktop/win32_gdi_source_candidate.py` получил `draw_incremental_text` — один DIB, Font/DC на кадр и ограниченная padded-by-3px область вокруг глифа. Пиксели GDI сопоставляются со старым ПОЛНЫМ Win32 DIB на синтетическом фоне (включая кириллицу, пересечение сетки и частичный выход за край). Прежний исследовательский `draw_text` не меняется. `desktop/source_whole_canvas_adapter.py` использует новый renderer, `WholePaintboxTask` допускает безопасную поэтапную запись в собственный ещё не опубликованный буфер, GDI DC уничтожается при отмене/cancel/finish.

## QA, производительность и EXE

Новые `test_stage111z31cj_core_interleaved_ticks.py`, `test_stage111z31cj_qt_interleaved_ticks.py`, `test_stage111z31cj_win32_incremental_gdi.py` в обязательном CI вместе с историческими CF/CG/CH/CI и семью страницами/тремя формами. Проверено: исходная последовательность Y и X, обратный X при PageAdc, bitmap byte-for-byte при делении на 1/4/13/256 strokes, cancel GDI ровно один раз, неизменный FFT Float32, SHA входного synthetic ZIP, pass-through курсора, Windows incremental ROI == существующему СОБСТВЕННОМУ GDI full DIB. Отдельного запущенного MVKView оригинала на GitHub нет.

**Принятый исполняемый SHA:** `5766c3379c8bfd08db9e6cdd7aa907baf401d338`. [Actions #43401431941](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43401431941) **3/3 SUCCESS**: Linux Core **1907 PASS / 105 SKIP**, Windows Core **2071 PASS / 7 SKIP**, Qt smoke **49 PASS**, Qt DPI150 **135 PASS** (реальный DPR 1.5).

Времена CI на отдельных Windows runners (НЕ измерения FPS): первая CJ `bf9fc7ce` — Core **248.59 с**, Qt smoke **50.78 с**, DPI150 **183.76 с**; оптимизированная `5766c337` — Core **155.59 с**, Qt smoke **27.03 с**, DPI150 **107.83 с**. Улучшение на 37%, 47%, 41% соответственно только для этих наборов/запусков.

[Автономный Windows EXE #14026415128](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43401431941/artifacts/14026415128), ZIP **69 005 572 байта**, доступен до 27.11.2026, содержит встроенный Go Native R6.1. SHA256 ZIP `34f3b9100f4e11bf76678da3b53884cfbf2da881f9f4533cd5810aef829519b5`; PE/EXE SHA256 по проверенному build manifest `2bf879553d9e01dc66519a3214a9b77d1d17a0bc5b0262c71192c4e8c846977f`. GitHub Actions подтверждает PE-заголовок/manifest и SHA match; `original_delphi_compatibility_verified=false`. [Synthetic Qt UI DPI150 #14024784995](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43401431941/artifacts/14024784995), 643 896 байт, срок до 20.11.2026.

## Что ещё не закрыто и следующий крупный пакет

Нет динамического original Win32 TCanvas/FormatFloat/Font/PPI/TextOut/GDI 1:1, исходного native XOR-пиксельного соответствия при DPI150 и оригинальной пиксельной mouse mapping. ROI 3px — исследовательский кандидат, хотя сопоставлен с нашим полным Win32 DIB на синтетике; **НЕ** доказательство native оригинала. Не подтверждены полные x87/Float32 0 ULP и одинаковое окно GetSignal/FIR/FFT/Power/Y/FRange в оригинале и в копии.

Для оригинальной структуры UI дополнительно прочитаны ЛОКАЛЬНЫЕ `mvkform.dfm`, `mvkeditform.dfm`, `WindowManForm.dfm`: **89 + 5 + 1 = 95** назначений обработчиков `On*`, всего **53 уникальных имени** по трём формам. Их наличие в DFM не означает реализованность в GUI. **Следующий большой связанный пакет** — реальная карта всех событий, проверка операций каждой из семи страниц и трёх форм, устранение несоответствий одновременно в автономном Core и GUI и сквозной E2E без повторов одних скриншотов. Опасные приборные WriteData/Reset остаются выключенными до разрешённой operator-acceptance. Закрытые PAS/DFM/IDP/BIN/оригинальный EXE не опубликованы.
