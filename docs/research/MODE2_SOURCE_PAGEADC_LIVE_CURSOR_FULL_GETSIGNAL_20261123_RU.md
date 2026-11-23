# MVKView — PageAdc LIVE курсор: полный GetSignal, исходный индекс, FIR, XOR

**Дата:** 23.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.

## Исходная атрибуция (только локальные приватные материалы)

Из архива владельца `Projects.7z` по его локальным `_Unit115.pas`, `_Unit128.pas` и `mvkform.dfm` плюс `mvk_idr(1).sqlite` подтверждены **SHA256 и адреса обработчиков** (архив/исходники/IDP/SQLite не публиковались):

- `_Unit128.pas:0084B4AC` — `Tmvkform.pbAdcMouseMove` передаёт только X в `ADCGrapher.UpdateCursor` и переносит `CursorString` в `lbAdcHint`.
- `_Unit115.pas:007CA75C` — `TQGrapher.UpdateCursor` пропускает неизменившийся `CursorPos`. `007CA76C` проверяет строгие `PixelLeft < X < PixelRight`; при выходе за границы очищает строку курсора; XOR перо clGreen, pmXor.
- `_Unit115.pas:007CA44F..007CA469` — при создании `CursorAveraging=1`, `FindPreciseXValue=False`; `007CABE4` использует `TRUNC` для сопоставления пикселя индексу; `007CA9A5` выбирает наибольшее **знаковое**, не абсолютное значение в текущем пиксельном столбце.
- `_Unit115.pas:007D0C30` — `GetSignal`: NoDC/AC, AC+DC и обратный массив Float32; исходное вычисление RMS независимо от графических LOD.
- `_Unit128.pas:0084B2F8` — `ScrWidth<0`, ось X меняет мс на с при H≥10 с, вертикальная ось зависит от текущего `GraphDefaultVScale` и типа АЦП.

**Ограничение:** статически известный TQGrapher алгоритм не подтверждает реальное совпадение всех пикселей Qt/Delphi, `stoiM/itosM` с округлением Win32/x87, абсолютную физическую калибровку или оригинальные временные часы. Итоги ниже честно маркируют кандидатность.

## Исправления общего пакета

1. `mvk_compatible/core/offline_export.py`: опциональный `include_full_cursor=True` добавляет исходный полный перевёрнутый массив `GetSignal` Float32 с SHA256. Обычные офлайн-результаты, FFT, BIN/TSXML и запись не меняются.
2. `mvk_compatible/core/native_r6_live_preview.py`: после однократного GetSignal формирует source-ориентированный Peak-preserving LOD **только для рисования**, одновременно сохраняет полный read-only Float32, исходное окно, Go SHA, частоту и единицу X. Не открывает второй TCP и не умножает уже откалиброванный BIN повторно.
3. `mvk_compatible/core/original_live_adc_cursor.py`: проверяет входной SHA Go, выходной SHA GetSignal, один session/ADC/HTag, запрошенную длину Fs·ms//1000 и абсолютные `uint64` границы окна. При MouseMove выбирает по полному обратному буферу, в том числе после rollover исходного 32-битного индекса. Дополнительный логический соседний X позволяет выбрать знаковый максимум в пиксельном столбце (отдельно маркированный Qt-кандидат), а не значение прореженного графика.
4. `mvk_compatible/desktop/main_window.py`: для LIVE PageAdc раньше было **нет нефильтрованного курсора** и ось обычного preview рисовалась по абсолютному индексу, хотя оригинальный GetSignal возвращает обратный буфер. Теперь `invertX(True)`, исходная шкала 20с…1мс и курсор в `lbAdcHint/lbAdcHintPrimary`, зелёный XOR overlay; при смене H/AC/source/Freeze/Stop, ошибке или чужой сессии курсор сбрасывается, не продолжает показывать чужую кривую.
5. `mvk_compatible/core/original_live_getsignal_fir_processing.py`: для FIR cursor Y берётся только из full Float32, один пиксель выбирает максимум со знаком. Длинные HTag≥10с в LIVE FIR теперь показывают ось в секундах вместо ошибочного «20 000 мс». Обратная совместимость: старый прямой вызов `source_live_filtered_cursor(result,x_ms)` сохраняется.
6. UI FIR рисует зелёный XOR, проверяет Stop/Freeze/session/ADC/HTag/filter/mode и не использует старые данные после смены условий. Любой GUI курсор — только read-only.

## Тестирование

- `test_stage111z31cw_live_wave_cursor_core.py`: AC/AC+DC, Fs65536/HTag20мс, длинный Fs512/HTag10с, 32→64 rollover, SHA-подмена, чужой ADC, пустая история, подписанные пиксельные FIR-пики, отсутствие Device I/O.
- `test_stage111z31cw_live_wave_cursor_qt.py`: реальные Qt события мыши по синтетическому окну Go, перевёрнутая ось X, XOR, full-array readout, переключение вертикального масштаба без GetSignal, запрет stale session/Freeze, FIR cursor.

Полный CI для последнего **кодового** коммита отслеживать по GitHub Actions workflow. На дату составления отчёта реальной общей парной приборной сессии Win32/MVK01 и аппаратного паритета нет. Не утверждать 1:1 из synthetic тестов.

## Что дальше

Не дробить восстановление на новые страницы: после прохождения CI провести **один оригинальный общий capture** на одном и том же приборе/сеансе: `IP → Измерить → Task2 → RX → PageAdc GetSignal/AC/DC/H/V/фильтр/XOR → PageSpectrum → WriteData/WriteValues → Stop` с полной проверкой ошибок, пунктов меню, `GetValueText` и форматов. Для идентичности курсора дополнительно нужны реальные Win32 PixelLeft/Right, `FindPreciseXValue` и x87-округление на том же фрагменте. Не публиковать частные файлы и не изменять `main`.
