# Stage111Z31FG — проверка Harness gain/units и безопасная интеграция Core + Qt

Дата: 2026-11-17. Репозиторий: `shonentez-afk/MVK-Reader-Web`, ветка `research/stage111-mvkview-desktop-20261029`.

## Что прислал Harness

- `STAGE111Z31FB_EVIDENCE.json` — отчёт о новом source gain/units fallback.
- `STAGE111Z31FB_CHANGES_AND_TESTS.md` — описание двух новых локальных файлов (коммит в GitHub в отчёте не заявлен).
- `original_mode2_gain_fallback.py` + `test_stage111z31fb_source_gain_fallback_core.py` — автономная модель + заявленные 32 теста.

## Прямая сверка всех трёх оригинальных приватных источников

1. `Projects.7z`: содержимое `_Unit125.pas`, `_Unit128.pas`, `_Unit115.pas`, `_Unit123.pas`, `mvkform.dfm` извлечено через libarchive в локальной среде; SHA-256 каждого совпадает с `mvk_idr(1).sqlite:source_files`. Оригинальные файлы в GitHub НЕ загружаются.
2. `mvk_idr(1).sqlite`: `functions` содержит `00806964` и `008069AC` в `_Unit125.pas` (строки 12875–12931). Для обоих индекс помечает `commented_stub`: это **исходный восстановленный ассемблер в комментарии**, а не скомпилируемый Pascal.
3. `mvkview.idp`: заголовок `IDR proj v.3`, Delphi 2014, base `00400000`, entry `008C1DC0` согласуется с метаданными SQLite; факт является проверкой заголовка, а НЕ полным разбором символов/RTTI `.idp`.

### Прямые источники из `_Unit125.pas`

- `00806965 CMP EDX,8; 00806968 JGE 00806988` — для source channel 8/9 пропуск ADC cell list, `00806988 MOV [ESP],3F800000` ⇒ **unity 1.0f**.
- Для 0..7: `00806971` — чтение соответствующего `TMvkCellList`, `00806978 EDX,0E` / `0080697D GetFloatByAddr`; исходное значение нельзя вывести из отсутствия ячеек в Compatible.
- `0080698F..008069A5` — сравнение с нулём через x87, `JP` при NaN не исправляет NaN, обычный ноль/минус-ноль заменяется на `1.0`.
- `008069B3 CMP EBX,8; JGE 008069DF; 008069E1 @UStrClr` — пустые **storage units** для source TACH 8/9. Для ADC `008069C8 EDX,10; 008069CD TMvkCellList.GetIndexByAddr` (**НЕ GetIndexByID**), затем `008069D8 GetValueText`.
- `00808617..00808682` — эти два source helper вызываются при инициализации storage существующих каналов после PARAM Stage0→1.

### Коррекция отчёта Harness

1. Его `source_gain_fallback(ADC)` всегда возвращал `1.0`, если не было runtime cell list. Это **НЕ** эквивалент оригинальному `GetFloatByAddr` и может выдать вымышленную калибровку. В новой модели отсутствующий gain/units ADC = `None`; при наличии уже проверенного значения применяется zero-guard.
2. `GAIN_REGISTERS` из `original_calibration_workbench.py` относятся к другому рабочему процессу (подготовка калибровки). Это не доказательство, что runtime `TMvkCellList` «не имеет gain».
3. Пустые `TMvkChannelStorage` units тахометра **не отменяют** исходные поля `ResultTacho`, `ResultTachoDelta` с единицами `Гц` в `PageStatus` (`original_pagestatus_source.py`). Результаты TACH в Гц не переименовываются; RPM не изобретается.
4. Фраза «Qt слой не обновлён» подтверждена для присланных файлов. Добавлена прозрачная передача статического fallback к существующему Qt `PageStatus` и `PageFile` через *метаданные*, без нового пользовательского исследовательского элемента и без изменения captured Float32.
5. Локальные PASS из отчёта Harness — **его собственные тесты**. Полный CI GitHub не подтверждается этим отчётом; нужен отдельный запуск после коммита.

## Внесённые изменения

- `mvk_compatible/core/original_mode2_gain_fallback.py` — исправленный source-only fallback, честное неизвестное значение для ADC.
- `mvk_compatible/core/native_r6_tach_evidence.py` — в SHA-проверенный RAW TACH receipt добавлены только source metadata `original_source_storage_gain_units`, без перерасчёта отсчётов и без утверждения physical RPM.
- `mvk_compatible/desktop/original_shell.py` — свойство `sourceOriginalTachStorageGainUnits` на PageStatus и PageFile (только когда имеется валидная native TACH evidence). Текущие видимые оригинальные таблицы, подписи/единицы измерения/размеры не меняются.
- `mvk_compatible/tests/test_stage111z31fg_source_storage_gain_core.py` — синтетические проверки границ, NaN, нулевого gain, отсутствующей калибровки ADC, двух каналов TACH, receipt Core.
- `mvk_compatible/tests/test_stage111z31cy_qt_tach_file_and_status.py` — сквозные проверки новых source metadata на настоящих Qt-виджетах (синтетический ZIP), отсутствие ложного RPM.

## Что НЕ выполнено и не заявляется

- Нет доказательства исходного runtime `GetFloatByAddr` для ADC из текущих live данных, поэтому `None` остаётся корректным исходным состоянием.
- Нет подтверждения FRange, числового равенства Delphi DSP/FFT/RPM, побайтового BIN/VALUES и полного GUI-паритета с запущенной MVKView.
- Отсутствуют новые аппаратные TCP/Modbus-команды и операции записи в физический прибор.
- В оригинальных EXE, IDP, SQLite, Projects.7z и Ghidra ничего не менялось.