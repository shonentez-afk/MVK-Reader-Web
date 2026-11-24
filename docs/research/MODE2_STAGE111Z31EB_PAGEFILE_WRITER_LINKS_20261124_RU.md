# Stage111Z31EB — PageFile: общий выбор каналов, WriteData/WriteValues и границы записи

Дата: 24.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.
Кодовый SHA: `a6a5f744d4a2b60df8ce921abc6372431511c04e`.

## Исходная причинность и повторная проверка

Локально прочитаны _Unit128.pas / mvkform.dfm из Projects.7z, SQLite-индекс функций и проверен SHA256 mvkview.idp: `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Приватные источники не включены в GitHub.

- 0084845C (PageFile): tcFileActions выбирает SPEC/VALUES или параметры ADC.
- 0084853C..0084856C: SPEC/VALUES доступны только при WriteValues=False.
- 00848572..00848598: общий cbFileChannels разрешён только при WriteData=False И WriteValues=False.
- 0084859E..00848678: префикс, XML, имя прибора/папки блокируются WriteData; соответствующий edit также зависит от checkbox.
- 0084C954: cbFileChannelsClick вызывает только 008486F4 (pnMeasure); не tcAnyChange / ADC графиков.
- 0084E914: bWriteAdcClick фиксирует время старта и 10 checked channels, выставляет WriteData; выключение снимает WriteData.
- 0084E988: bWriteValuesClick фиксирует время, 43 SPEC, 6 RESULT + 24 BAND + 6 TACH, 10 checked channels, выставляет WriteValues; выключение снимает WriteValues.
- 008486F4: pnMeasure зависит от checked channels и flags; оригинальный таймер также отображает длительность hh:nn:ss (отдельная оставшаяся UX-проверка).
- 00847248: active page dispatch then pnMeasure.

## Реальные исправления

1. `original_live_pagefile.py`: единая source_live_file_edit_policy для каналов/SPEC/VALUES/параметров файлов, включая совместимый запрет новых изменений при Stop. Исправлена ошибка: WriteValues без WriteData ранее оставлял общий список каналов редактируемым. Подсчитываются применимые к выбранным ADC/TACH реальные колонки (SPEC43+RESULT6+BAND24 для ADC; TACH6 для тахоканала). 73 флага в legacy IPC — не 73 пункта VALUES в оригинальном UI; видимых VALUES 36. Названия и единицы берутся из source_ru_cell_title/live_get_units, как в PageStatus и CSV.
2. `original_live_write_stages.py`: ledger отклоняет новый overlapping writer с отличающимся общим выбором каналов; не открывает пустой VALUES по неприменимым параметрам. `plan_for_frame_mark` возвращает исходную BEGIN selection для END; изменённые независимые флаги другого writer не попадают в END frame mark. Существующий Go frame-mark, RAW, закрытие файлов и source export не переделывались.
3. `original_shell.py`: реальные item flags и обработчик itemChanged используют ту же policy; прямой/запоздалый сигнал не меняет locked mask. При периодическом статусе обновляются существующие QListWidgetItem, а не clear/rebuild. LIVE cbFileChannels не переключает tcAdc/tcSpectrum и не зависит от их текущего ADC. Offline выбор графика/сессии сохранён. pnMeasure обновляется непосредственно при изменении flags.
4. `original_measure_controls_ui.py`: bWriteValues требует хотя бы одну применимую исходную колонку, а не произвольный отмеченный checkbox.
5. `main_window.py`: actual END IPC mark получает latched BEGIN plan. Исправлена подпись LIVE FIR/IQ в том самом видимом lbSpecMeanPrimary (spec_core_triplet), не заменяя вычисленный N/RMS/peak. DSP, source gate и локальные данные не изменены.
6. Тесты расширены в test_stage111z31cx_original_live_pagefile_core.py (матрица locks, реальные поля, latched masks, независимые writers) и test_stage111z31cz_qt_live_write_buttons.py (реальные Qt itemChanged/disabled checks, неизменная идентичность списка, независимый ADC, применимость TACH-only).

## PageConfig / PageCalib — граница проверки

008472D0 в оригинале разделяет Mode4/5 (ConfigIp/ConfigCalibCellList) и Mode6 (расширенные config grids); не является вычислительной страницей обычного Mode2. 00846D24..00846D84 раскрывает Status/Adc/Spectrum/File и pnMeasure; 00846D64..00846D74 отдельно проверяет флаг +628 для PageCalib. Не нужно показывать PageConfig как обязательную страницу Measure. 00848688 переключает исходную grid/log PageCalib. В совместимом приложении Task0 — отдельный согласованный read, явно запрещённый во время активного измерения; upload/reset и запуск генератора выключены. Калибровочная модель использует проверенную неизменённую исходную локальную конфигурацию и создаёт только проект поправок. Эти связи сверены, физический запуск калибровки и изменение конфигурации не выполнялись. Продолжить восстановление отдельных режимов и проверки их жизненного цикла; не включать реальные записи прибора по статическому индексу.

## CI / история и границы

Предыдущий Stage111Z31EA `e53cb8d44e792809fe50cf6723faefb643754160`: [CI #45306170600](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45306170600) завершился FAILURE. Linux Core 2700 PASS/149 skip, Go PASS, Windows DPI PASS; Windows Core **2947 passed, 15 skipped, 1 failed**. Остался один старый Qt FIR-test: реальный FIR graph и N2048 уже построены, но lbSpecMeanPrimary содержал "локальный результат" вместо "локальный FIR/IQ". Исправлено в текущем SHA. EXE предыдущего этапа не сформирован.
Новый [CI #45307882905](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45307882905) соответствует Stage111Z31EB; проверять фактический итог. Последний ранее подтверждённый 5/5 код `8bdd85cf` (Stage111Z31DY), не текущая версия.
Не заявлять восстановление всех связей 1:1 до проверки GUI и физического same-RX MVK01/Win32. В частности: реальные WriteData/WriteValues/Stop, исходные BIN/TSXML/VALUES/TABLE и численные GetSignal/GetSpectrum x87/FRange остаются не аттестованы. main, Go TCP, оригинальные файлы и коэффициенты не изменены. Следующий этап: проверка нового CI, устранение только фактических regressions; довести управление Stop/текущими writer state и исходные имена/время файлов, PageStatus chart/scale, отдельные Config/Calib modes и реальную приёмку.
