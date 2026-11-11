# STAGE111Z31BF — точная карта типов MVK, регистры, исходные списки и парная Windows-приёмка

Дата: **11.11.2026**. Ветка: `research/stage111-mvkview-desktop-20261029`.
Исходная база: **Stage111Z31BE** — [CI #42992104138](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42992104138), Linux/Windows Qt/standalone EXE **SUCCESS** для source `4fe9ddd87e0d81574871f9b7f2085d63d844e327`. Последующие BE docs-only коммиты не меняли эту сборку.

**BF:** новый крупный пакет source reconstruction + автоматизированный пассивный Windows QA. До завершения новой CI НЕ считать FULL CI PASS. Оригинальная runtime 1:1 совместимость **НЕ доказана**, аппаратные операции/калибровка **НЕ проверены и заблокированы**.

## 1. Прямо проверенный private IDP, не догадки

В рабочей приватной среде распакован пользовательский `Projects.7z` (SHA `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`) и независимо проверен `mvkview.idp` (SHA `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`). **Исходные PAS, DFM, IDP, BIN, EXE, PNG не добавлялись в GitHub.**

В IDP найден точный сегментный VA→file-offset `offset=VA-0x400ED8`, проверен по подлинному машинному коду `00802EB7: 6A 00 BA 54 32 80 00`. Это позволяет воспроизвести исходную память **без запуска MVKView/x32dbg/F9**. Сняты и снабжены SHA256 следующие маленькие таблицы в виде производных числовых констант (без приватных байтов):

- `0x008D2AD8`: `TMvkCellList` `FmtChar` для **30 типов**, точная последовательность `fiw!!!vacshz!qpmbbbbbbbb!!!!hh`. Исходные неизвестные `!` сохраняются, не называются допустимыми форматами.
- `0x008D2B18`: **30 размеров ячеек в байтах**, значения в том числе тип 0 → 4, 9 → 32, 13 → 32, 14 → 64. _Unit115:007CE5B1 `LastAddr += bytes/2`: это доказательство, что конфигурационные адреса — **16-битные регистры, не байтовые смещения**. SSID 0x50, 32 байта, завершается у 0x60; Password 0x60, 64 байта. Без расширения ячейки до произвольного «UINT32 пароля».
- IDP-таблицы `0x803254` NumGroups **[0,1]**, `0x8032A0` Option **[0,1,2,3]**, `0x80330C` WiFiMode **[0,1,2]**, `0x8044D4` AlarmBand **[0,1,48,47]**, `0x802610` AlarmState **[0,1,2,3,4,5,17,18,19,20,21,255]**, `0x80267C` AlarmAlert **[1,2,4,8]**, `0x8048DC` TachoFunction **[0,1]**, `0x804BD4` ResultOverload **[0,1]**, `0x804C40` ResultBuffers **[0,1,3,7]**, `0x804C94` ResultSensorState **[0,1,2,3]**. Это исходные UInt32 ID. Ключи из _Unit125:0080250C строятся `PREFIX + Cell + IntToStr(ID)`. **Значений реальных переведённых locale strings по-прежнему нет.**
- `0x008D2F90`: **43 оригинальных Float32** третьоктавных номинальных частот, от 0.63 до 10000 Гц, ID 1..43, исходный Off ID0. Точные IEEE-754 представления и SHA256 (`fb84a7a4b3e8d6a679357082fe114e9f606a1f3d9d90b9feed6529760bc905f6`) сохранены в производной таблице и проверяются тестами. Частотные названия, вычисляемые совместимой программой, являются **fallback**, не пиксельно проверенными строками оригинального Delphi.

## 2. Что записано в репозиторий

- `mvk_compatible/core/original_config_idp_tables.py`: IDP-derived FmtChar, размер ячейки, **исходные enum ID**, точные Float32 частоты, SHA256/числовые тесты. Оригинальные приватные данные не публиковались.
- `mvk_compatible/core/original_config_semantics.py`: восстановленные ID-схемы `SOURCE_ADVANCED_OPTIONS` для NumGroups/Option/WiFiMode/Octave; `source_section_rows` теперь содержит `source_format_char`, `source_storage_bytes`, диагностику совпадения формата локального файла. **Текст локального файла не выдаётся за живую конфигурацию устройства.**
- `mvk_compatible/core/original_config_register_image.py`: безопасный автономный reader явного локального *регистрового* снимка; по _Unit115:007CF328/360 `byte_offset=2*source_address`, 32-bit LE и точный Float32 bit reinterpret; _Unit115:007CF4F6..50D битовая выборка из UInt32, bounds/domain checks, маркированный source preview, запрет записи. Длинные SSID/Password не выдаются как неверные 4-байтные числа; пароль не возвращается в логах.
- `mvk_compatible/desktop/original_config_readonly_ui.py`: столбец исходного типа/символа/ширины в Mode4/5, без приборных операций.
- `mvk_compatible/core/original_parity_regions.py`: достоверные метрики пиксельных прямоугольников на одном native pixel grid, без resize/align/OCR и без изменения исходного массива.
- `tools/research/compare_running_mvkview_windows.py`: расширен существующий прямой **read-only** GetDC/BitBlt snapshot двух **уже запущенных** PID — optional `--scenario-id`, `--rois-json` (ручные ROI в native coords), `--operator-data-sha256` (метка пользователя, **не верифицирует original session**), SHA256 двух PNG и локальная запись. Никакой автоматической навигации/пуска/кнопок, F9, x32dbg, device I/O.
- `tools/research/summarize_private_mvkview_parity.py`: автоматическая проверка SHA256, PID, read-only safety receipts, геометрии, ROI и агрегирование приватной серии по сценариям; проверка включает отказ на symlink, подмену PNG, пропущенные доказательства. Отчёт содержит только числовые метрики, имена сценариев и хеши — НЕ сами снимки.
- Новые синтетические тесты: `test_stage111z31bf_config_register_image.py`, `test_stage111z31bf_idp_source_tables.py`, `test_stage111z31bf_original_parity_regions.py`, `test_stage111z31bf_private_series_parity.py`. Предыдущие Stage BD/BE тесты не удалены.

## 3. Как получить прямое сравнение с оригиналом

Только на рабочем ПК Windows оператора, где **обе программы уже запущены**. Оригинал не запускать и не возобновлять через x32dbg без отдельного согласия. На каждой итерации вручную открыть **одно и то же** локальное измерение/страницу/канал/режим; убедиться, что оба окна полностью прорисованы, одинаковы DPI/размеры клиентской области.

Создать приватную папку **вне Git checkout**, например `C:\MVK_LOG\paired_qa`, и при необходимости `rois.json` как JSON-массив `[{"name":"graph","xywh":[x,y,width,height]}]` с операторски измеренными нативными координатами; координаты шаблона не принимать за измеренные.

Запуск из корня рабочего дерева:

```powershell
python tools\research\compare_running_mvkview_windows.py --original-pid ORIGINAL_PID --compatible-pid COMPATIBLE_PID --private-output-directory C:\MVK_LOG\paired_qa --scenario-id config_ip_adc1 --rois-json C:\MVK_LOG\paired_qa\rois.json
```

Для нескольких страниц и каналов повторить с новым `--scenario-id` после **ручного** перехода в обеих программах. Затем построить суммарный проверяемый отчёт:

```powershell
python tools\research\summarize_private_mvkview_parity.py --private-captures C:\MVK_LOG\paired_qa
```

Операторский `--operator-data-sha256` привязывает метку файла к отчёту, но сам по себе не доказывает, что original runtime реально использует этот файл/ADC. Отсутствие различных пикселей в некоторых ROI не доказывает полное функциональное 1:1. Все приватные PNG/JSON/BIN остаются локально.

## 4. Что всё ещё открыто (приоритет)

1. Новая приёмка CI Linux Core/Windows Qt150/verified standalone EXE для BF.
2. Реальный операторский paired Windows original↔compatible на одном файле, 7 страниц, PageConfig Mode4/5/6, Tmvkeditform, третья форма; переносить только подтверждённые расхождения в следующую реализацию, не «чинить на глаз».
3. Расшифровка всех остающихся типов `TMvkCellList` (мы восстановили **символ, размер и адресацию**, но для 30 типов не доказаны все правила парсинга/форматирования), полные runtime locale strings и безопасный source config/device protocol.
4. Физическая калибровка с генератором, весь UI/62 обработчика, настоящие device parity и полное закрытие спектров/временного сигнала по всем режимам. **Никаких записей или калибровочных действий без отдельного разрешения/стенда**.

Критерий принятия: исходный код + тесты + CI + оригинальная same-run приемка, отдельно от аппарата. Все Stage BF результаты **частичные**, не заявлять полное восстановление MVKView или 1:1 до исчерпывающей приёмки.


## Финальная CI-приёмка source BF

**ОФИЦИАЛЬНАЯ ПРИЁМКА BF (2026-11-11):** исходный source SHA `10319ca736e2fd1aedf28b292a2bb6b45815c4f7`; [GitHub Actions #42995021324](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42995021324) **SUCCESS**: Linux Core PASS, Windows Core + Qt DPI150 PASS, verified autonomous Windows EXE with bundled Native R6.1 PASS. [Артефакт #13843333202](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42995021324/artifacts/13843333202), `MVKViewCompatible_Stage111_Windows_Preview`, 68 680 818 байт, expires 2026-11-25T09:30:55Z. Дополнительные документационные коммиты не входят в source SHA и не меняют проверенную сборку. **НЕТ** оригинальной 1:1 Win32 runtime приёмки (нет парного снимка/измерения с оригиналом); конфигурационные device writes/Calib/F9 не запускались.
