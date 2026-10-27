

## 27.10: verified counter cadence from four PCAPNG
Direct offline parse of all four captures: 4700-frame counter (+20) increments 130 each interval, while each ADC sample stream advances 32768 samples (+12 counter increments 256 per ADC frame), demonstrating a **0.5 s / 2 Hz calculated-frame cadence**, independent of the (unknown) DSP averaging window. Frames: realtime83 59, realtime84 60, record83 60, record84 60. No parsed ADC counter discontinuities across all eight channels in each capture. Known 847-byte TCP gap in record83 and malformed recording tails remain quality caveats. Different ADC channels may be one packet (256 samples = 3.90625ms) out of phase at the exact 4700 packet insertion; this is interleaving, not proven channel-specific DSP latency. Details docs/STAGE13_ADC_4700_COUNTER_CADENCE_AUDIT_20261027_RU.md. Next: distinguish calc and ADC clock epochs via affine counter alignment and examine true DSP lag. Frozen v0.3.40 untouched.



## 27.10 Stage13: frozen MVK-LAB06 lag sweep
Реально проверены сдвиги -2..+2 с в Live83/84 (выбор АЦП 4/5/6/8), отдельно -1/0/+1 с в записи №84 (АЦП5/6). Коэффициенты не изменялись. Для АЦП6 №84 отклонение остаётся -8..-13% на проверенных сдвигах: одна задержка проблему не объясняет; для АЦП4 №84 Live median absolute error уменьшилась с 5.48% при 0 до 1.11% при +0.5 с, но это НЕ доказанная задержка DSP. Подробности docs/STAGE13_LAG_SWEEP_FROZEN_MODEL_20261027_RU.md. Не делать повторный fit на №84; продолжить привязку счётчиков и independent holdout. Freeze v0.3.40.

# MVK Reader Web — начать новый чат

**Этот файл — единая точка входа.** Не начинать разработку с нуля и не подменять базовую программу упрощённым прототипом.

## Порядок чтения
1. `START_NEW_CHAT_RU.md` — текущая инструкция.
2. `docs/PROJECT_STATUS_RU.md` — базовая версия, известные результаты и открытые задачи.
3. `docs/PROTOCOL_CALIBRATION_RU.md` — подтверждённые сведения о TCP/10230 и FC03 TCP/502.
4. `docs/DECISIONS_RU.md` — принятые архитектурные решения.
5. `docs/TEST_ASSETS_INDEX_RU.md` — тестовые инструменты, источники и фикстуры.
6. `MVK_Reader_Web/README_v0_3_40_RU.md` и исходники `MVK_Reader_Web/`.

## Важный временный запрет (до отдельного согласования)
**Не запускать новую версию и не активировать живой приём TCP/10230.** Не считать, что TCP handshake гарантированно запускает поток: пассивные тесты двух приборов уже проведены 26.10.2026 без send() (см. `docs/PASSIVE_TCP10230_TEST_20261026_RU.md`); для любых **новых** подключений требуется отдельное разрешение пользователя. Не подключаться к реальным приборам и не посылать команды без прямой просьбы пользователя.

## Основная версия
`MVK_Reader_Web/` — сохранённый импорт программы **v0.3.40 CALCULATED MODES OFFLINE**, не новый релиз. Не присваивать новым изменениям статус проверенного релиза без тестов. Полная побайтовая сверка с локальным исходным архивом пока не заявлена как завершённая.

## Обязательные принципы
- Сохранять существующий интерфейс: вкладки «Временной сигнал», «Спектр», «Расчётные данные», общий выбор прибора, Live/Archive, SQLite и экспорт.
- TCP/10230: 8 каналов временных отсчётов, спектры рассчитывает приложение.
- TCP/502: только безопасное FC03-чтение расчётных величин и калибровки; не смешивать данные разных приборов.
- Для проверенных АЦП4 двух приборов: `a_m_s2 = tcp10230_raw_float32 * K_modbus`. Экспортированный BIN уже содержит м/с² — второй раз не масштабировать.
- Сервер по умолчанию слушает `127.0.0.1`.
- Каждую новую диагностическую программу и тест добавлять в `tools/` или `tests/`, с README, командой запуска и записью в индексе.
- Не загружать рабочие PCAPNG, BIN, SQLite, секреты и производственные данные в историю Git.

## Последнее проверенное исследование (27.10.2026)
- Stage13: BIN АЦП6 `MVK00000050-ADC6-2026-10-27--10-34-14.bin` повторно получен под именем с `(1)`; SHA256 `1eccd0857c4c222299a7c9a09d67bfd316adc76616acd730a93ffa2049aba41d` **совпадает**. Не считать независимой новой записью.
- В текущей загрузке девять TABLE CSV (не одиннадцать): медианы ускорения 10–1000 / 10–2000 / 10–3000 Гц = 1.626 / 2.221 / 3.602 м/с². Полный BIN при независимом PSD даёт 1.673664 / 1.917813 / 2.860116 м/с²; расхождения +2.93% / −13.65% / −20.60%. Причина не доказана.
- Источник: `docs/STAGE13_ADC6_REPEAT_RECORDING_20261027_RU.md` (раздел повторной проверки). Не дублировать ранее выполненное; далее сравнивать синхронные окна и АЧХ фильтров без подгонки.
- **Правило синхронизации:** после каждого исследовательского шага обновлять одновременно `START_NEW_CHAT_RU.md`, профильный отчёт, `docs/PROJECT_STATUS_RU.md` и `docs/TEST_RUNS_RU.md`. Перед передачей в новый чат проверять отсутствие противоречий и несоответствий числу файлов/таблиц. Ни один тест не объявлять пройденным без доказательства.

- Дополнительные 2-секундные окна 38–61 с дают 10–3000 Гц от 2.7501 до 2.9388 м/с², ниже всех девяти TABLE CSV (минимум 3.458), поэтому простое изменение окна не объяснило расхождение. Детали в отчёте Stage13.

## Проверка на дублирование исследований (27.10.2026)
- Перед новой FFT-работой обязательно сверять `docs/STAGE13_ADC6_SPECTRAL_EDGE_20261027.md`, `docs/STAGE13_ADC4_ADC6_HIGH_BAND_AUDIT_20261027.md` и `docs/STAGE13_ADC6_REPEAT_RECORDING_20261027_RU.md`.
- **Уже сделано на первой записи АЦП6**: Welch Hann, 65536 отсчётов/1 Гц, пики 2481/2779/2886/2993 Гц и дополнительные 1002/1886 Гц; PSD RMS при верхних отсечках 2500, 3000, 3100, 3200, 3300, 3320, 3500 Гц. Изменение верхней границы до ~3.3 кГц близко к показанию MVKView, но это НЕ доказательство реальной полосы прибора.
- **Уже сделано на первой записи**: 11 окон по 2 с, стабильное расхождение ~20% для АЦП6 в 10–3000 Гц; отдельно на повторной записи — 10 двухсекундных окон (38–61 с), не объясняющих разницу простым выбором окна.
- **Нерешённое**: строгая синхронизация времени BIN и CSV MVKView; реальная передаточная функция и типы фильтров/определения расчётных величин. Следующий тест должен добавлять новое доказательство, а не повторять cutoff sweep или Welch peak list.
- Приоритет: установить происхождение timestamps TABLE и окон вычисления, затем проверить документированную фильтрацию (если есть), без подгонки полосы под ответ. Любые новые результаты записывать в профильный отчёт и отражать здесь; не выдавать прежние опыты за новые.

## Новое исследование временного ряда VALUES (27.10.2026)
- Найден полноценный `VALUES-2026-10-27--10-34-13(1).csv`: 124 записи показаний MVKView с интервалом примерно 0.5 с (10:34:13.911–10:35:15.410), три поля ускорения 10–1000/2000/3000 Гц. **Это новый независимый источник временной информации**, отличать от девяти TABLE CSV.
- Выполнено предварительное сопоставление с 61.039-с BIN на окнах 1/2/4 с при *гипотетическом* начале BIN в 10:34:14.000. Для окон 2 с: 118 пар, медианы BIN/MVKView в 10–3000: 2.87182/3.5385 м/с², медиана отношения по строкам 0.80539; разрыв сохраняется при смене окна. Синхронизация часов не доказана.
- Полный отчёт `docs/STAGE13_ADC6_VALUES_TIME_ALIGNMENT_20261027_RU.md`, воспроизводимый **offline-only** инструмент `tools/adc6_values_alignment/compare.py`; он не работает с сетью. Не повторять разбор CSV и уже выполненные оконные измерения. Следующее: исследовать лаг/фильтрацию по временным рядам без подгонки.
- Последние изменения находятся в ветке `docs/reconcile-stage13-20261027` (PR #11), а не обязательно в `main`; до следующего переноса проверить PR и, после согласованного объединения, сверить `main`. Обновлять этот файл одновременно с профильными результатами.

- Дополнительно выполнен лаг-скан ±6 с с шагом 0.5 с: лучший r для 10–3000 = 0.4145 при лаге 0.0 с, для 10–2000 = 0.3653 при −1.0 с, для 10–1000 = 0.5885 при −0.5 с. Это не подтверждает единый точный лаг. См. отчёт VALUES.


## Проверка качества BIN АЦП6 (27.10.2026)
Автономно проверены 4 000 256 отсчётов: все конечные; mean 1.77948, std 13.92232, min -76.58183, max +77.96915 м/с². По Welch Hann (1 Гц) RMS в полосах 3000–3500: 2.78719; 3500–5000: 4.05440; 5000–10000: 11.13344 м/с². Энергия выше 3000 Гц значительная, но конкретные фильтры MVKView неизвестны. Явного жёсткого ограничения амплитуды не видно, неисправность АЦП6 не доказана. В текущем сеансе исходный BIN АЦП4 недоступен, только прежний отчёт. Не повторять эти проверки без новых оснований.


## Проверка нового BIN АЦП4 от 27.10.2026
- Получены BIN 33.75390625 с (2212096 float32, 65536 Гц), TSXML, VALUES и 10 TABLE CSV.
- Независимый RMS ускорения для полос 10-1000 / 10-2000 / 10-3000 Гц: 4.009376 / 4.314487 / 4.366532 м/с².
- Медианы VALUES: 3.947 / 4.300 / 4.376 м/с²; медианы TABLE: 3.9055 / 4.2695 / 4.3460 м/с².
- Разница в полосе 10-3000 Гц между BIN и медианой VALUES составляет около -0.22%, для АЦП6 в другом захвате около -20%. Записи НЕ синхронные. Это не доказывает неисправность АЦП6.
- Выше 3000 Гц в АЦП6 значительно больше энергии, чем в АЦП4. Проверить фильтрацию MVKView и индивидуальные настройки каналов; не повторять уже сделанный cutoff sweep.

## Новое исследование хвоста фильтра 27.10.2026
- Реально выполнен офлайн-пересчёт исходных BIN АЦП4 и АЦП6: periodogram PSD, частотная весовая АЧХ Butterworth bandpass 10–3000 Гц (1,2,3,4,5,6,8 порядки). АЦП4 ideal 4.366532, 3-й порядок 4.365510; АЦП6 ideal 2.860116, 3-й порядок 3.538408 м/с². Медианы VALUES соответственно 4.376 и 3.5385 м/с².
- **Важно:** почти идеальное совпадение 3-го порядка является постфактум подобранной гипотезой, НЕ доказательством алгоритма MVKView. Различие в частотной энергии выше 3 кГц объясняет чувствительность АЦП6, а неисправность датчика не доказана. Далее требуется независимая проверка фильтра по документации/реализации или на других данных без выбора параметров по целевому числу.
- Воспроизводимость: `docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md` и `tools/adc_filter_edge_audit/check.py`. Все изменения пока в PR #11, до объединения обязательно смотреть рабочую ветку.


## Stage13 fixed-order cross-band validation (2026-10-27)
Order-3 digital Butterworth single-pass PSD-weighted bandpass model applied unchanged to 10-1000/2000/3000 Hz on ADC4 and ADC6. Across all six comparisons against VALUES medians absolute relative error <0.35%. ADC4 model/reference: 3.94265/3.947, 4.28796/4.300, 4.36551/4.376; ADC6: 1.63067/1.6265, 2.20639/2.199, 3.53841/3.537 (m/s2). This is cross-band support, NOT blind validation: order-3 was chosen post-hoc on ADC6 10-3000. Real vendor filter unknown. Do not repeat the same bands; next: verify vendor filter definition or prospective independent measurement, without tuning. Detailed report docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md; tool tools/adc_filter_edge_audit/check.py. No production code change.


## Паспорт МВК01: алгоритм полос (27.10.2026)
- Прочитано руководство ВАРБ.411711.112 РЭ, Приложение 1, стр. 41–44. Подтверждено: FIR-децимация, Hann FFT, третьоктавные весовые функции, трёхзонное суммирование квадратов для фиксированных полос, включая весовую область верхних срезов 1000/2000/3000 Гц.
- Производитель НЕ подтверждает в прочитанном разделе фильтр Баттерворта 3-го порядка. Ранее полученное совпадение шести полос — эмпирическая аппроксимация, не реконструкция реального DSP. Не внедрять Баттерворт как доказанный фильтр.
- Далее реконструировать штатную схему весовых окон и требуемые коэффициенты. Источник: `docs/MVK01_HANDBOOK_FILTER_ALGORITHM_20261027_RU.md`; PDF в `docs/vendor/`. Сохранение/запуск исходной v0.3.40 не затрагивать.


## Stage13: построен офлайн-каркас фиксированных полос (27.10.2026)
Реализован `tools/mvk_fixed_band_lab/mvk_stage13_fixed_band.py`: Hann PSD, три зоны энергетического суммирования, явные краевые весовые функции, диагностический третьоктавный базис. Добавлены 3 синтетических unit-теста и README. **Не является готовой копией DSP МВК01:** точные веса краевых окон, фирменная FIR-децимация и третьоктавная обработка не восстановлены. Автотесты опубликованы, но их фактический запуск в чистом checkout не подтверждён. Не считать реальную валидацию пройденной. См. `docs/STAGE13_FIXED_BAND_RECONSTRUCTION_20261027_RU.md`. Запрет на live и изменения v0.3.40 сохраняется.


## Таблица 4 руководства МВК01 (27.10.2026)
Проверено ВАРБ.411711.112 РЭ, стр. 7–8: виброускорение 0.5–20000 Гц, скорость 0.5–7000, перемещение 0.5–2000. Полосовые фильтры 0.8–150, 0.8–300, 2–1000; по ГОСТ ИСО 10816-3/4 дополнительно 2–1000, 10–1000, 10–2000 Гц. **Класс третьоктавных фильтров — 2 по ГОСТ Р 8.714-2010**; в центре третьоктав есть 2500, 3150, 4000 Гц. В перечне полос таблицы 4 **нет 10–3000**; её нельзя объявлять паспортной полосой по этой строке. Класс 2 НЕ подтверждает порядок Баттерворта. Подробно: docs/MVK01_TABLE4_BANDS_CLASS2_20261027_RU.md. Следующий шаг: нормативная маска класса 2 и фирменные краевые веса для 10–3000.


## Нормативная проверка класса 2 (27.10.2026)
- По ГОСТ Р 8.714-2010 подтверждены нормативные пределы относительного затухания третьоктавного фильтра класса 2. Полоса с номинальным центром 3150 Гц имеет приблизительные границы 2806–3536 Гц: пики АЦП6 3105 и 3313 Гц лежат внутри неё.
- **Важно:** это НЕ доказывает, что пики входят в фиксированный показатель 10–3000 Гц, поскольку производитель применяет отдельные весовые окна на верхней границе. Класс 2 не задаёт эти веса, не определяет фильтр Баттерворта и не подтверждает срез около 3.3 кГц.
- Источник `docs/STAGE13_THIRD_OCTAVE_CLASS2_EDGE_20261027_RU.md`. Дальше: независимо восстановить краевые веса; не подбирать их под MVKView. Никаких сетевых испытаний.



## Исправление П1.4 от 27.10.2026
Ранее созданный single-PSD трёхзонный каркас НЕ соответствует П1.4 в части источников данных для верхней зоны и середины. Добавлен `tools/mvk_fixed_band_lab/p14_two_spectrum.py`: нижняя зона из high-res acceleration PSD; верхняя и внутренняя из третьоктавных мощностей; контроль перекрытия. Тесты созданы, но НЕ запускались. Точные весовые окна/FIR неизвестны, код не является законченным DSP. См. `docs/STAGE13_P14_TWO_SPECTRUM_CORRECTION_20261027_RU.md`. В дальнейшем сначала проверять первичную документацию, затем гипотезы. 


## P1.4 implemented + tested offline, 27.10.2026
Primary reference remains VАRB.411711.112 RE Appendix 1 (P1.2-P1.4, pp.42-44). P1.4 split-path module and 3 unit tests exist. Executed equivalent local numerical code: 3/3 PASS. New `tools/mvk_fixed_band_lab/bin_hann_preflight.py` reproduces Welch Hann diagnostic of ADC4 and ADC6 BIN: RMS 10-3000 4.366450 / 2.860347; 3000-3536 0.328961 / 2.865118 m/s2. These are PSD diagnostic baselines, NOT P1.4 vendor results. Unknown proprietary 1/3-octave edge windows and FIR remain blocking. Full report `docs/STAGE13_P14_EXECUTION_20261027_RU.md`. Must not call P1.4 metrologically verified or alter frozen v0.3.40. First examine vendor manual before proposing additional filtering models.


## ОБЯЗАТЕЛЬНЫЙ ПЕРВОИСТОЧНИК: полный аудит РЭ 2019 (27.10.2026)
Прочтено/проиндексировано руководство ВАРБ.411711.112 РЭ (55 стр.), зарегистрированы разделы 1–12 и приложения 1–2: `docs/MVK01_MANUAL_FULL_ANNOTATED_AUDIT_20261027_RU.md`. **Читать этот реестр перед любым новым анализом DSP или Modbus и сверяться с оригинальным PDF** `docs/vendor/ВАРБ.411711.112 РЭ МВК.pdf`. Главные находки: приложение 1 п.1.3 указывает ГОСТ ISO 2954-2014 как АЧХ для фиксированных 2–1000, 10–1000, 10–2000, 10–3000; приложение 2 в п.3.4 содержит RMS acceleration 10–3000 по A+0x60 (A=0x2000+N*0x200). Текст П1.3 упоминает 42 третьоктавных полосы, тогда как Modbus регистр хранит 43 float и п.3.5.5 перечисляет 43 центра: до разрешения не удалять 43-й элемент. Биты статуса 4,5,6 указывают неполные буферы и отключённые диапазоны, необходимо учитывать их при сравнении. Класс 2 ГОСТ Р 8.714-2010 относится к третьоктавным фильтрам, а для фиксированных полос ключевой стандарт другой. Точные веса DSP по РЭ не доказаны. Никакого запуска прибора/записи FC16, v0.3.40 заморожена.


## КЛЮЧЕВОЕ НОВОЕ НАХОЖДЕНИЕ 27.10.2026 — ГОСТ ISO 2954-2014
Паспорт Приложение 1 п.1.3 для фиксированных полос 2-1000 / 10-1000 / 10-2000 / 10-3000 ссылается на ГОСТ ISO 2954-2014, а его п.5.3 прямо устанавливает комбинацию ФВЧ и ФНЧ **Баттерворта третьего порядка** для нормативной АЧХ. Это независимое объяснение раннего совпадения модели третьего порядка на 6 измерениях. Однако НЕ подтверждает конкретную цифровую реализацию DSP, оконные таблицы П1.4, FIR и временные окна. Смотреть `docs/STAGE13_GOST_ISO2954_BUTTERWORTH3_20261027_RU.md` и `docs/MVK01_MANUAL_FULL_ANNOTATED_AUDIT_20261027_RU.md` ПЕРЕД новыми экспериментами. Ветка PR #11, v0.3.40 не менять.


## CORRECTION 27.10.2026 — TCP/10230 calculated data already proven
Previously 26.10 reverse engineered 4700-byte calculated frame on TCP/10230: 28-byte header, eight 584-byte per-ADC records; 43 third-octave values, 24 RMS, 24 equivalent peaks, 24 spans. Verified on 48 frames/384 channel records; see docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md and docs/FRAME_4700_REAL_RAW_REGRESSION_20261026_RU.md. TCP/10230 carries waveform AND calculated data. Port 502 is an ALTERNATIVE Modbus calculated/config reader, not the exclusive computed-data path. In the v0.3.40 UI calculated=502 reflects current implementation, not the packet format. P1.3 says 42 but Appendix 2 and real 4700 frame contain 43 slots (0.63-10000 Hz); whether first 0.63-Hz slot is reserved/unused remains unproven. Do not erase the 43rd slot. Detailed docs/STAGE13_TCP10230_CALCULATED_43_VS_42_RECONCILIATION_20261027_RU.md. Respect source priority and do not repeat settled work.


## Stage13 4700 calculated frame — next step 27.10.2026
Не повторять ранее подтвержденную карту 4700 байт. Добавлены `tools/raw_offline_audit/test_4700_calculated.py` (синтетические проверки структуры/43 полей/статусов) и `tools/raw_offline_audit/audit_4700_first_octave.py` (проверка реальных первых 0.63 Hz полей на существующих RAW) с отчётом `docs/STAGE13_4700_DECODER_NEXT_STEP_20261027_RU.md`. Исходные реальные RAW в GitHub не публиковать. На этом шаге запуск новых тестов/сканирование RAW НЕ подтверждены. Валидация 42 против 43 остаётся ОТКРЫТОЙ; не объявлять первую полосу исключённой без проверки. Сначала читать руководство и прежние подтвержденные исследования. v0.3.40 не изменять, без новых live соединений.



## 27.10.2026 — rechecked before next Stage13 gate
42/43 practically settled: five handbook sections and existing 4700 frame support 43, P1.3 mentions 42 probably editorial error; see docs/STAGE13_TCP10230_CALCULATED_43_VS_42_RECONCILIATION_20261027_RU.md. Next-step comparison partly ALREADY DONE: docs/MVKVIEW_ADC4_SCREEN_COMPARISON_20261026_RU.md compares 4700 ADC4 with MVKView but screenshot timing unknown. Do not redo this or promise exact matching from it. Follow docs/STAGE13_MEASUREMENT_VALIDATION_LAB_MASTER_PLAN_20261026_RU.md and docs/STAGE13_FIELD_EVIDENCE_BUNDLE_SPEC_20261026_RU.md: compare same channel, quantity, band, unit, interval; otherwise NOT_COMPARABLE. Primary unresolved gate is paired/time-proven comparison of 24 calculated fields and end-to-end evidence.


## Stage13 27.10 — нормативная модель выполнена и проверена
Добавлен `tools/mvk_fixed_band_lab/fixed_band_normative.py`: отдельные цифровые ФВЧ3 и ФНЧ3 (ГОСТ ISO 2954-2014 §5.3, на который ссылается РЭ Прил.1 §1.3), PSD интеграл с |H|². **Это эквивалентная частотная характеристика, не доказанный исходный DSP**. На загруженных BIN ADC4/ADC6 полосы 10-3000: 4.365258579 и 3.542213511 м/с²; прежний MVKView ADC6 ~3.537, несинхронно. 4 синтетических теста PASS в локальной среде, GitHub checkout не тестировался. Полный отчет `docs/STAGE13_NORMATIVE_FIXED_BAND_EXECUTION_20261027_RU.md`. Следующий шаг — все 8 АЦП с сохранёнными gain и сравнением одновременных окон кадра 4700. Не повторять поиск причины ADC6 и 42/43. v0.3.40 без изменений.


## 27.10 — интеграция П1.2→П1.3→П1.4 без повторного изобретения алгоритмов
Первичный источник ВАРБ.411711.112 РЭ, приложение 1, стр.38–44. Переиспользованы `p14_two_spectrum.py` и `fixed_band_normative.py`, добавлен только связующий экспериментальный `tools/mvk_fixed_band_lab/p12_p14_pipeline.py` и 5 синтетических тестов. Локально 5/5 PASS на эквивалентной копии зависимостей; чистый checkout не тестировался. Точные производственные FIR/третьоктавные и краевые веса по-прежнему НЕ установлены, диагностические rectangular windows не соответствуют заявленному классу 2. Отчёт `docs/STAGE13_P12_P14_PIPELINE_IMPLEMENTATION_20261027_RU.md`. ADC6 discrepancy уже объяснён нормативной АЧХ; 43 третьоктавные поля и 4700 уже рассмотрены. Следующий реальный этап: все 8 АЦП на архивном PCAPNG, проверка времени/калибровки, сравнение с 4700. Основную v0.3.40 не изменять.



## 2026-10-27: ALL 8 ADCs tested on 4 offline PCAPNG
Read docs/STAGE13_ALL8_FOUR_PCAP_NORMATIVE_20261027_RU.md. The normative HP3*LP3 model was applied using gain from VAST_MVK for all 8 ADCs in all four captures 83/84. Read matching 4700 calculated RMS from the same TCP sessions. The 32 comparisons generally align within a few percent; 83 ADC4 rec -0.06%, ADC6 rec -0.13%, 84 ADC6 rec +0.54%. Exception 83 ADC5 live +5.71%; one 847-byte TCP reconstruction gap in 83 recording makes ADC1 result invalid. Full-record RMS vs frame medians is NOT synchronized window acceptance, so no PASS verdict. Next audit stream coverage and frame-level timing then cross-check all 24 metrics. Do not regress to earlier settled 42/43 and ADC6 theories. Frozen v0.3.40 unchanged.



## 27.10.2026 — приоритет MVK-LAB-06
Получен и локально проверен полный исследовательский пакет MVK-LAB-06 (скрипт, отчёт, JSON). 12/12 selftest PASS, статические результаты сверены. Это теперь **основная экспериментальная реконструкция П1.4**; прежние fixed_band_normative.py, p14_two_spectrum.py и p12_p14_pipeline.py сохраняются как контрольные/вспомогательные. Коэффициенты 3000 Гц: энергии полос 3150/4000 с весами 0.40530224/0.10487199; это эмпирическая подгонка на приборе 83, а не доказанные заводские коэффициенты. НЕ утверждать метрологической аттестации, особенно ВС/ВП на 0.8/2 Гц. Обязательно независимое frozen-weights испытание на приборе №84 без повторной подгонки. Реестр и SHA256 исходников: docs/STAGE13_MVK_LAB06_PRIMARY_RECONSTRUCTION_REVIEW_20261027_RU.md. Три полных пользовательских артефакта остаются вложениями проекта, только реестр занесён в GitHub; не утверждать что полный код залит. Продакшн v0.3.40 не менять.



## 27.10 — MVK-LAB06 frozen v3 executed on BIN and PCAP
Experimentally frozen inference module `tools/mvk_fixed_band_lab/instrument_reconstructed_v3.py`, test `test_instrument_reconstructed_v3.py`; coefficient fitting and channel target-derived gamma removed from inference. Two BIN tests (83 ADC4/6) and 4 PCAPNG x 8 ADC x 6 bands = **192** offline same-session comparisons against 4700 median, not synchronized windows. Device 84 ADC6 10-3000 is -10.09% recording / -11.62% realtime, notably WORSE than earlier HP3×LP3 normative; cannot claim passed independent validation or replace normative baseline. Recording83 has known missing TCP segment; exclude affected claims. Detailed report `docs/STAGE13_FROZEN_MVK_LAB06_BIN_PCAP_VALIDATION_20261027_RU.md`. Local synthetic sine/invalid input/frozen coefficient checks passed; clean GitHub checkout not independently run. NEXT: time-aligned comparison, no refit. Main v0.3.40 unchanged.

## Промпт продолжения для нового чата
«Продолжи проект MVK Reader Web из приватного GitHub-репозитория `shonentez-afk/MVK-Reader-Web`. Сначала прочитай `START_NEW_CHAT_RU.md`, `docs/PROJECT_STATUS_RU.md`, `docs/DECISIONS_RU.md`, `docs/TEST_ASSETS_INDEX_RU.md`, затем проверь актуальную ветку и код. Не начинай проект заново, не упрощай интерфейс, не запускай новую версию или соединение с МВК01 без отдельного разрешения пользователя; пассивные тесты 26.10 уже выполнены, однако запуск основной программы не разрешён. Отделяй подтверждённые факты от гипотез, сохраняй каждый новый тестовый скрипт и обновляй журнал изменений и статус». 
