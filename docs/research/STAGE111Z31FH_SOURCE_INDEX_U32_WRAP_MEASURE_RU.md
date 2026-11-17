# Stage111Z31FH — Source uint32 rollover после «Измерить»

Дата: 17.11.2026. Исправления Go + Core + Qt + offline regression, без дополнительных команд промышленному прибору.

## Три оригинала, проверенные совместно локально

- `mvkview.idp`: исходный IDR v3, размер 42094126 байт, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`, совпадает с `meta.idp_header` в SQLite.
- `Projects.7z`: реальные `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm` извлечены библиотекой libarchive; все четыре SHA256 и размеры совпали с записями SQLite.
- `mvk_idr(1).sqlite`: `PRAGMA quick_check=ok`; 95 событий, 25404 функций, 92767 вызовов. `_Unit115.pas`: `TMvkChannelStorage.FRxPos/FValidPos` и `TMvkChannelStorageCalcParams.LastProcessedPos` имеют тип **UInt64**. `GetSignal 007D0C30`, `CheckDataAvailability 007D1998`. `_Unit128.pas`: `bTaskConnectClick 00848E78` → Mode2 `00846AD4`, `PageAdc 00847EAC` берёт исходные параметры окна. Исходные тексты остаются только в приватной среде.

## Реальный дефект

Go декодирует `SampleHeader.Index` как **uint32** и при естественном переходе через `0xFFFFFFFF` записывает корректные `first_sample_index` и `next_sample_index` с оборачиванием. Core `native_r6_live_preview.py` и `original_live_view_gate.py` ошибочно требовали `end > first`. Qt `_render_live_wave` требовал, чтобы очередной `next_index` численно превосходил предыдущий. Поэтому продолжительное реальное измерение могло навсегда скрыть новые корректные окна после rollover, несмотря на целые RAW/Float32 и продолжающийся локальный приём.

## Точное изменение ядра и UI

- Go manifest каждого ADC получает `captured_samples` — отдельный локальный **uint64**, который уже отслеживается существующим единственным TCP reader. Сами калиброванные отсчёты, RAW/BIN, сеть, SetRate и приборные регистры не изменены.
- Независимый Core `original_sample_cursor32.py` проверяет длину исходного окна по modulo `2^32`, а отставание от подтверждённого Native status сверяет **точно** с разностью локальных capture-counters, если новый receipt присутствует. Legacy ZIP без счётчика отклоняется, если период неоднозначен.
- Core и передняя проверка Qt используют одну и ту же модульную арифметику; для графика вычисляется ограниченная локальная 64-битная реконструкция только по подтверждённым индексам, не DSP-часы.
- В Qt `bAdcHScale/GetSignal` новую страницу можно рисовать после rollover, но только если **и** локальный RX, **и** индекс на устройстве действительно продвинулись. Повторение прежнего SHA-валидированного ZIP не становится новым измерением.
- Никакие аппаратные записи, флэш/перезапуск и не подтверждённые исходные поля не активированы. `original_delphi_compatibility_verified=false`.

## Регрессия и открытые вопросы

Добавлены: Go 2 кадра через `0xFFFFFFFF` с byte-identical BIN и 64-битным счётчиком в ZIP; Python Core validates wrap/newer/forged/stale/legacy epoch; Qt реальный QWidget с переходом `0xFFFFF000 → 0x0000F000` и запретом повторного кадра. Проверять **все четыре** Jobs CI и автономный Windows EXE до приёмки. Физический MVK01, оригинальный 2^21 storage ring, исходящий hardware WriteData/WriteValues, точный TQGrapher/x87/Delphi parity остаются OPEN.
