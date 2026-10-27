# Состояние проекта на 2026-10-26

## Основная база
Версия **v0.3.40 CALCULATED MODES OFFLINE**, построенная поверх v0.3.32 NETWORK GUARD LAB. Сохранять существующий интерфейс и функции: FastAPI, Collector Server, SQLite, Plotly, BIN/TSXML, PCAPNG, FFT, архив, экспорт.

На дату этой записи полная кодовая база **не перенесена** в GitHub. Не принимать README за программный релиз и не ставить git-тег v0.3.40, пока полные файлы и тесты не размещены.

## Подтверждённое
- В PCAPNG TCP/10230 передаются блоки всех 8 АЦП, маркер 0xFF800ADC; fs=65536 Гц, 256 float32 little-endian отсчётов в блоке; заголовок 28 байт, полная длина блока 1052 байта.
- Для двух проверенных пар PCAPNG/BIN, АЦП 4, согласована формула ускорения м/с²: raw float32 TCP/10230 умножить на индивидуальный коэффициент Modbus.
- Float32 по FC03 использует порядок слов CDAB.
- 10.13.42.83 АЦП4: gain=509.90582275390625; 10.13.42.84 АЦП4: gain=510.2197570800781.
- Коэффициент датчика всех проверенных каналов: приблизительно 0.010194 В/(м/с²).
- Во время сеансов с MVKView измерительный поток начинался до получения полной клиентской посылки 36 байт. Это **не** является доказательством работы без каких-либо прикладных команд.

## Новые подтверждённые результаты (26–27.10.2026)
- В двух отдельных пассивных испытаниях 26.10 TCP/10230 начал отдавать поток после connect без send(); основную программу не запускали. Более ранняя формулировка «не доказано» ниже относится к сеансам MVKView до этих испытаний.
- Stage13 офлайн-прототип: 59/59 unittest на Linux и SQLite integrity OK по двум RAW; Windows и полный регресс ещё не проверены.
- По АЦП4 для 10–3000 Гц независимая интеграция PSD отличается от MVKView на +0.81%; по АЦП6 −20.06% и на независимой повторной записи −19.46%. Причина расхождения не доказана; сравнение пока не синхронизировано по времени.
- До разрешения пользователя не запускать новую версию, не подключаться к промышленным приборам.

## Следующая работа
1. Зафиксировать результаты уже выполненного пассивного теста; дополнительные подключения — только после отдельного разрешения.
2. Интеграция калибровки PCAPNG, привязанной к прибору, каналу, времени и происхождению параметров.
3. Stage13 P0: временное совмещение BIN и TABLE CSV АЦП6; независимое исследование FFT/окон/фильтров 1–3 кГц без подгонки параметров; затем количественная регрессия спектров ускорения, виброскорости и перемещения.
4. Один TCP/10230 collector на прибор; браузеры должны использовать уже собранный сервером поток.
5. Импорт полного v0.3.40 кода и формирование проверенного git-тега с Windows-релизом.

## Примечание
Наблюдение пользователя: при одном клиенте TCP/10230 второй не подключается, при этом SCADA читает TCP/502. Формальное определение лимита соединений требует отдельного безопасного теста.


## Дополнение 27.10 — повторно загруженный BIN АЦП6
Новая загрузка содержит тот же 61.039-секундный BIN (SHA256 совпадает с отчётом Stage13), и **9** TABLE CSV (отличать от 11 в прежнем отчёте). Медианы девяти таблиц по 10–1000/2000/3000 Гц: 1.626/2.221/3.602 м/с². Полный PSD BIN: 1.673664/1.917813/2.860116 м/с². Устойчивое верхнечастотное расхождение остаётся; причина и синхронизация не установлены. Подробности в `docs/STAGE13_ADC6_REPEAT_RECORDING_20261027_RU.md`.


## Stage13 — анализ VALUES, 27.10.2026
Разобран VALUES CSV с 124 временными измерениями каждые ~0.5 с. Пробное выравнивание 61.039-с BIN по предполагаемому времени старта 10:34:14 и PSD по 1/2/4-секундным окнам не устраняет ~20% дефицит независимого RMS в 10–3000 Гц. Например, для 2 с 118 пар: медианы BIN 2.87182 против MVKView 3.5385 м/с², медианное отношение 0.80539. Точный лаг и фильтрация неизвестны; приёмка не пройдена. См. `docs/STAGE13_ADC6_VALUES_TIME_ALIGNMENT_20261027_RU.md` и `tools/adc6_values_alignment/`.


## ADC4 independent record check (2026-10-27 11:18)
BIN 33.75390625 s, 2212096 float32 LE, fs=65536 Hz. PSD RMS for bands 10-1000/2000/3000 Hz: 4.009376 / 4.314487 / 4.366532 m/s2. VALUES medians 3.947 / 4.300 / 4.376; ten TABLE medians 3.9055 / 4.2695 / 4.3460. Relative difference at 10-3000 Hz vs VALUES median -0.22% (ADC6 ~-20% in a separate recording). Non-simultaneous recordings; do not conclude ADC6 hardware failure. See START_NEW_CHAT_RU.md.


## Stage13 — проверка хвоста фильтра (27.10)
Проверены исходные BIN АЦП4/6 частотным взвешиванием PSD через Butterworth 10–3000 Гц. Для 3-го порядка RMS 4.365510 (АЦП4) и 3.538408 (АЦП6) м/с² против медиан VALUES 4.376 и 3.5385. Это совпадение после выбора порядка из испытанных моделей, а не доказанный фильтр МВК01/MVKView. Полный отчёт: `docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md`.


## Stage13 cross-band fixed model 2026-10-27
Same order-3 Butterworth response, no order tuning between bands, reproduces six ADC4/ADC6 VALUES medians over 10-1000/2000/3000 Hz within 0.35%. Not a blind test since order 3 originally chosen on ADC6 10-3000. Vendor filter not established; v0.3.40 unchanged. Details docs/STAGE13_BUTTERWORTH_EDGE_CHECK_20261027_RU.md.


## Прямое документальное подтверждение алгоритма МВК01
ВАРБ.411711.112 РЭ, Приложение 1, стр.41–44: FIR-децимация, FFT с окном Ханна, третьоктавное спектральное взвешивание и трёхчастная схема расчёта фиксированных полос с краевыми весовыми функциями. Модель Баттерворта 3-го порядка остаётся эмпирическим заменителем, не установленным фильтром производителя. См. `docs/MVK01_HANDBOOK_FILTER_ALGORITHM_20261027_RU.md`.


## Stage13 offline fixed-band scaffold 2026-10-27
Добавлен `tools/mvk_fixed_band_lab/` с реализацией Hann PSD / 3 энергетических зон, явных весов и тестами. Точные FIR и краевые весовые функции МВК01 пока не идентифицированы. Тесты в GitHub, выполнение не подтверждено. Не выдавать за готовую реконструкцию DSP. См. `docs/STAGE13_FIXED_BAND_RECONSTRUCTION_20261027_RU.md`.


## 2026-10-27 — таблица 4 паспорта МВК01
Уточнены рабочие частоты, паспортные полосовые фильтры и **класс 2 третьоктавных фильтров по ГОСТ Р 8.714-2010**. Полоса 10–3000 Гц не входит в перечисление полосовых фильтров таблицы 4; наличие показателя в MVKView не заменяет доказательства нормативной полосы. См. docs/MVK01_TABLE4_BANDS_CLASS2_20261027_RU.md.


Stage13 27.10: Class-2 3150 Hz third-octave filter nominal band approximately 2806-3536 Hz includes ADC6 peaks 3105 and 3313 Hz. Unknown weights into fixed 10-3000 indicator; see docs/STAGE13_THIRD_OCTAVE_CLASS2_EDGE_20261027_RU.md.


## Исправление П1.4 от 27.10.2026
Ранее созданный single-PSD трёхзонный каркас НЕ соответствует П1.4 в части источников данных для верхней зоны и середины. Добавлен `tools/mvk_fixed_band_lab/p14_two_spectrum.py`: нижняя зона из high-res acceleration PSD; верхняя и внутренняя из третьоктавных мощностей; контроль перекрытия. Тесты созданы, но НЕ запускались. Точные весовые окна/FIR неизвестны, код не является законченным DSP. См. `docs/STAGE13_P14_TWO_SPECTRUM_CORRECTION_20261027_RU.md`. В дальнейшем сначала проверять первичную документацию, затем гипотезы. 


Stage13 P1.4 (27 Oct): executed 3/3 synthetic unit tests on equivalent local copied code and independently computed Hann Welch BIN diagnostic for both ADC4/6. Upper 3000-3536 Hz RMS 0.328961 (ADC4), 2.865118 (ADC6) m/s2; exact vendor weight windows remain unknown. Report docs/STAGE13_P14_EXECUTION_20261027_RU.md. No production changes.


## 2026-10-27: 55-page handbook inventory
Full indexed source notes: `docs/MVK01_MANUAL_FULL_ANNOTATED_AUDIT_20261027_RU.md`. New crucial evidence: GOST ISO 2954-2014 fixed-band transfer function including 10-3000 (Appendix 1 sec.1.3); explicit Modbus RMS acceleration 10-3000 at A+0x60 (A=0x2000+N*0x200); unresolved discrepancy of 42 vs 43 one-third-octave values; buffer-not-ready status bits 4-6. Vendor coefficients still unknown, no device access.

## КЛЮЧЕВОЕ НОВОЕ НАХОЖДЕНИЕ 27.10.2026 — ГОСТ ISO 2954-2014
Паспорт Приложение 1 п.1.3 для фиксированных полос 2-1000 / 10-1000 / 10-2000 / 10-3000 ссылается на ГОСТ ISO 2954-2014, а его п.5.3 прямо устанавливает комбинацию ФВЧ и ФНЧ **Баттерворта третьего порядка** для нормативной АЧХ. Это независимое объяснение раннего совпадения модели третьего порядка на 6 измерениях. Однако НЕ подтверждает конкретную цифровую реализацию DSP, оконные таблицы П1.4, FIR и временные окна. Смотреть `docs/STAGE13_GOST_ISO2954_BUTTERWORTH3_20261027_RU.md` и `docs/MVK01_MANUAL_FULL_ANNOTATED_AUDIT_20261027_RU.md` ПЕРЕД новыми экспериментами. Ветка PR #11, v0.3.40 не менять.

## CORRECTION 27.10.2026 — TCP/10230 calculated data already proven
Previously 26.10 reverse engineered 4700-byte calculated frame on TCP/10230: 28-byte header, eight 584-byte per-ADC records; 43 third-octave values, 24 RMS, 24 equivalent peaks, 24 spans. Verified on 48 frames/384 channel records; see docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md and docs/FRAME_4700_REAL_RAW_REGRESSION_20261026_RU.md. TCP/10230 carries waveform AND calculated data. Port 502 is an ALTERNATIVE Modbus calculated/config reader, not the exclusive computed-data path. In the v0.3.40 UI calculated=502 reflects current implementation, not the packet format. P1.3 says 42 but Appendix 2 and real 4700 frame contain 43 slots (0.63-10000 Hz); whether first 0.63-Hz slot is reserved/unused remains unproven. Do not erase the 43rd slot. Detailed docs/STAGE13_TCP10230_CALCULATED_43_VS_42_RECONCILIATION_20261027_RU.md. Respect source priority and do not repeat settled work.


Stage13 4700 frame 27.10: existing decoder reused; new synthetic tests and per-channel 0.63 Hz first-slot audit added. Not run yet on actual RAW. Full next-step report docs/STAGE13_4700_DECODER_NEXT_STEP_20261027_RU.md. No production changes.


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
