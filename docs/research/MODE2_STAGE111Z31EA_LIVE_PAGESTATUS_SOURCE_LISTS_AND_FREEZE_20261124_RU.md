# Stage111Z31EA — исходные связи LIVE PageStatus, RESULT/BAND/SPEC/TACH и Freeze/Stop

Дата: 24.11.2026. Рабочая ветка: `research/stage111-mvkview-desktop-20261029`. Кодовый SHA: `e53cb8d44e792809fe50cf6723faefb643754160`.

## Повторная проверка трёх приватных источников

Из доступного локального `Projects.7z` прочитаны _Unit128.pas, _Unit125.pas, _Unit115.pas и mvkform.dfm. В локальном `mvk_idr(1).sqlite` найдены адреса функций, DFM events и их привязки. SHA256 локального mvkview.idp: `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Архив, IDP и SQLite не загружались в GitHub.

- 00847248: диспетчер текущей страницы, затем pnMeasure.
- 008475E8..008475EF: PageStatus не перерисовывается при TMVKThread.FreezeUpdate.
- 0084761A..008476B2: 15 системных полей.
- 008476B7..00847797: 8 каналов x 8 контрольных зон x 3 поля.
- 0084779C..008479F8: ResultAdcCellList(6) + выбранный ResultAdcBandCellList(24) + ResultTachCellList(6), 12 колонок (имя, АЦП1..8, тахометр1..2, единицы).
- 008479FD..00847D53: отдельный АЦП, SpecSeries43 отдельно от ResultAdcCellList6 + 24 строк BAND, последние одновременно по трём спискам СКЗ/пик/пик-пик. Исходные единицы GetUnits, отдельные nominal frequencies.
- 00847D58..00847E4A: 6 тахометрических полей, заполняются col1 и последняя колонка единиц в пятиколоночном tabResult.
- 00845307..00845498: инициализация исходных колонок tabResult/tabAllResult.
- _Unit125:00804A30/00804DEC/008053B8: конструкторы RESULT/BAND/TACH. Первые три Advanced RESULT читают тот же полный DWORD +0x120; оставшиеся +0x00, +0x5E, +0x5C.
- 0084F708 tcAnyChange синхронизирует только tcAdc и tcSpectrum; tcStatus выбирает собственный режим/АЦП.
- 0084DEA4 — bFreezeUpdateClick. Qt совместимо удерживает последний принятый снимок при переключении tcStatus во время паузы, явно подписывает паузу. Это не утверждение пиксельного поведения Win32.

## Реализованные изменения

1. `core/original_live_operator_status.py`: новый операторский view для всех 14 несистемных режимов; отдельно от прежней RAW/исследовательской проекции. Все каналы — 36x12; АЦП — 30x5 + 43 исходных полосы; TACH — 6x5. Режим Control остаётся 24x9. Используются исходные названия и GetUnits, существующий кандидат GetValueText; пропуски и nonfinite остаются «—». Не подставлять локальный FFT или выдуманные значения.
2. `LivePageStatusBinding`: один принятый snapshot привязан к session_id и TCP connection count. Удерживает snapshot при Freeze, учитывает подтверждение Go. Запрещает rollback accepted PARAM frame counter; сбрасывает значения при ошибке, stale/silence, Stop и смене источника. Системное состояние отделено от локального FFT. Новая принятая копия создаётся один раз, а неизменный source/mode не перестраивает таблицу на каждом 20ms tick.
3. `original_shell.py`: реальный PageStatus использует эту модель и публикует receipt session/socket/accepted_param_frames. Все исходные 15 режимов сохранены. Третьоктавный график с 43 отдельными значениями и номинальными частотами, курсор из того же PARAM. Старые offline-архивные модели и экспорт не менялись.
4. `original_live_result_registers.py`: проверка всех трёх алиасов +0x120, включая несовпадение valid/missing. В новой схеме явные RESULT6 и sensor_status не могут противоречить друг другу; legacy схема без RESULT6 поддержана.
5. `main_window.py`, `original_measure_controls_ui.py`: PageStatus получает даже событие ошибки во время Freeze и не сохраняет ложное активное состояние. На Freeze сбрасываются курсоры, на thaw берётся новый принятый snapshot.

## Предыдущий Stage111Z31DZ: точная причина красного CI

[CI #45302838035](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45302838035) код `4c4dca955b74`: Linux Core 2692 passed/149 skipped; Go RX/export PASS; Windows QPA PASS; Windows Core 2938 passed/15 skipped, **1 FAIL** в `test_source_selected_envelope_fir_qt.py::test_qt_live_fir_iq_from_exact_2m_source_ring_not_plain_fft`; автономный EXE skipped. Новый строгий gate отвергал синтетический fixture без полных source-ring полей. Исправлен fixture с domain/FRange/rx_pos_64/first_readable_pos_64/next_device_sample_index, отдельно проверяется допуск исходного окна и запрет окна без доказательства. Тест требует полный post-FIR FFT2048/N/2=1024, source SHA, выбранный bSpecLines4096, df16. Маркировка LIVE FIR/IQ возвращена в summary. Production gate не отключался.

## Новая проверка

[GitHub Actions #45306170600](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45306170600) соответствует именно `e53cb8d44e792809fe50cf6723faefb643754160`. Тесты: `test_stage111z31ea_live_operator_status.py`, расширенный `test_mode2_original_page_status_param_qt.py` (все режимы, реальные поля/единицы/разные ADC, Freeze, возобновление, silence, Stop и поздние события). Проверять итог CI; не присваивать 5/5 до завершения. Предыдущий подтверждённый Windows EXE — Stage111Z31DY, `8bdd85cf`, [artifact 14853087405](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45240889385/artifacts/14853087405), НЕ новый код.

## Граница и продолжение

Все изменения касаются локального UI/core и synthetic проверок; не изменены main, Go TCP, DSP/FIR-коэффициенты, исходные приватные материалы, WriteData/WriteValues или форматы файлов. Нет реального подключённого MVK01, оригинального Delphi Win32 same-RX и байтового численного паритета. Следующий блок: проверить source PageStatus chart scale, единицы/локализацию и PageFile связи с тем же принятым регистровым набором, затем режимы PageConfig/PageCalib и общую реальную аппаратную приёмку. Не переделывать уже восстановленные формы только косметически.
