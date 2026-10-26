# Stage 13 — приём 16 бинарных каналов, аудит качества, отбор эталонов (2026-10-26)

## Решения
- Завтра ожидаются **бинарные файлы всех восьми каналов каждого из двух МВК01**: №83 и №84; дополнительно может быть экспорт таблицы измерений MVKView (отдельной от спектра), а также экспорт спектра/скриншоты.
- Измерения могут быть сделаны **в другое время, чем наши прежние TCP/PCAPNG испытания**. Поэтому допустимы: исследование формата, собственных коэффициентов, поиск дефектов качества по каждой записи, независимая обработка сигнала этого файла, сопоставление данных одной и той же записи. Недопустимы прямые выводы «ошибка алгоритма» из несовпадения двух несинхронных спектров/СКЗ на изменяющейся машине.
- **Цель:** сначала отобрать пригодные эталонные каналы (все 16 проверить один раз), а далее делать дорогостоящие регрессионные/полевые измерения на 2–4 опорных АЦП; дефектные каналы оставить для отдельной регрессии диагностики, не исключать из проверки декодирования.
- Stage13 — независимая measurement validation laboratory. Основную MVK Reader Web v0.3.40 до acceptance не изменять. Не требуется новая поездка до просмотра файлов.

## Важнейшие внешние источники
- SKF Accelerometer Troubleshooting: bias voltage, floating contacts, overload/clipping, FFT ski slope, cable noise: https://skftechnicalsupport.zendesk.com/hc/en-us/articles/1500001563501-Accelerometer-Troubleshooting
- Endevco: высокий DC bias может соответствовать обрыву, низкий — КЗ; интерпретация зависит от типа IEPE и схемы питания: https://www.endevco.com/our-resources/ask-the-experts/determining-accelerometer-and-input-signal-condition
- NI: пределы акселерометра и крепление могут порождать искажения: https://www.ni.com/en/shop/data-acquisition/sensor-fundamentals/measuring-vibration-with-accelerometers.html
- SciPy Welch, coherence и спектральные расчёты: https://github.com/scipy/scipy/blob/main/scipy/signal/_spectral_py.py
- tsfresh feature calculators (статистические признаки): https://github.com/blue-yonder/tsfresh/blob/main/tsfresh/feature_extraction/feature_calculators.py
- Scientific investigation of sensor saturation / mounting integrity: https://link.springer.com/article/10.1007/s42417-024-01435-8

## Входные данные и интерпретация
Каждый файл инвентаризовать SHA256, size, format, channel, instrument, acquisition_timestamp (если есть), ADC fs, sensor gain, unit, mode; **проверять**, действительно ли содержит временной сигнал. Не полагаться на расширение файла. Определить границы внутренних записей, общий формат/связь со старым TCP VAST_MVK, наличие AUX4700/AUX160/таблиц и калибровки. При необходимости искать в архиве калибровку/время. Если time series отсутствует, ряд проверок помечать NOT_TESTED, не делать вывод о качестве осциллограммы из одного спектра.

## Трёхступенчатая оценка
### A. Непригодность по аппаратному/потоковому признаку
- Актуальные AUX4700 status: bit10=0x400 sensor DC above maximum; bit11=0x800 at/below minimum; bit0 overload; bit4–6 buffering not ready; любые неизвестные биты сохранять.
- DC bias / датчик/кабель: сравнивать только с характеристиками датчика и его питания; нельзя глобально использовать один фиксированный предел.
- Отсутствующая или неправильная калибровка, NaN/Inf, malformed block, sample-counter gaps/dup, канал перепутан.
- Near-zero/stuck signal вместе с аппаратной диагностикой; нулевой RMS сам по себе не доказывает обрыв.

### B. Возможные искажения
- Clipping: длительные plateaus/повторение идентичных экстремальных величин, асимметрия лимитов, базовый сдвиг после overload; обязательно учитывать реальные характеристики АЦП.
- Impulses/contact noise: робастное отклонение MAD, high crest factor, kurtosis, число spikes и clusters, выбросы в отдельных окнах; **не считать все импульсы ложными** — реальные дефекты подшипников тоже импульсные.
- DC drift/baseline changes; stationarity RMS/PSD across windows; abrupt gain/calibration shifts.
- 50/60 Hz interference (+100/120 и гармоники), фон и относительный тональный уровень, частоты оборотов (если известны). Электрическую наводку нельзя устанавливать по одному пику 50 Гц; требуется контекст вращения, оборудование и спектральное сравнение.
- Broad noise floor, SNR в валидной полосе, Welch PSD, harmonic stability; optional coherence с соответствующим физически связанным каналом.

### C. Репрезентативность эталона
- Достаточная длительность и стабильность режима машины; диагностический статус OK; signal > noise floor и < overload.
- Повторяемость доминирующих частот/амплитуд в последовательных окнах; достаточно информативный спектр 0–100 Гц и более широкой полосы; сравнимые настройки.
- Нужны минимум один чистый канал с устойчивыми низкочастотными гармониками и один с информативным высокочастотным спектром. По возможности выбрать по одному или два с обоих приборов. Внутренние «нулевые AUX160» №84 не равны отсутствию сигнала.
- Для каналов с диагностической ошибкой статус исключения **в качестве эталона**, но использовать для тестирования правильной диагностики. Не путать failure «сигнал неисправен» и failure «измерение неудобно для сравнения».

## Матрица приёмки (после поступления файлов, без предрешения)
| Прибор | АЦП | Предварительный флаг из старых испытаний | Что перепроверить |
|---|---|---|---|
| 83 | 1 | bit 0x800 | DC/качество/counter |
| 83 | 2 | локальные помехи и переходы AUX160 | spikes, PSD, repeatability |
| 83 | 3 | показатель AUX4700 index46 повышался без дескрипторных переходов | корректность raw и нестандартных метрик |
| 83 | 4 | нет ранее подтверждённой неисправности | кандидат |
| 83 | 5 | bit 0x400 | DC/качество/counter |
| 83 | 6 | нет ранее подтверждённой неисправности | кандидат |
| 83 | 7 | нет ранее подтверждённой неисправности | кандидат |
| 83 | 8 | нет ранее подтверждённой неисправности | кандидат |
| 84 | 1–6 | AUX160 zero в прежних сеансах | waveform+calibration, это не повод исключать |
| 84 | 7–8 | bit 0x400, MVKView показал обрыв кабеля | проверить статус на новых данных |

Это **гипотезы для очередности просмотра, не вердикты по ещё не полученным файлам**.

## Порядок испытаний и пороги
1. Inventory, header/calibration, shape, records; preserve as-is.
2. Compute window quality metrics 0.5–2 s and whole-file stats; record thresholds + rationale, not hard-code universal pass/fail.
3. Plot waveform excerpts, envelope, amplitude distributions, PSD Welch, short-time spectra with axes and units; annotate gaps, clipping candidates.
4. Check inter-window drift, cross-channel coherence **only where physically applicable**.
5. Rank channels `REJECT` (evidence of sensor/ADC integrity problem), `INVESTIGATE` (quality uncertain), `CANDIDATE` (usable), `REFERENCE` (manually accepted after comparison). Distinguish diagnosis tests.
6. Validate after user/operator context (sensor type, mounted locations, rotation/load if available), but base initial ranking on existing files.
7. Use selected subset for expensive FFT/integration/MVKView validation, then field tests if required.

## Отчёты
`REPORTS_FOR_ANALYSIS/INPUT_BINARY_REVIEW_<date>/` with `input_manifest.json` (all SHA), `CHANNEL_QUALITY_MATRIX.csv` (16 rows), `CHANNEL_METRICS.jsonl` (window-level), `FLAGS_AND_EVIDENCE.jsonl` (cause, threshold, source, time), `QUALITY_RANKING.json` (verdict/confidence/test availability), plots PDF/HTML optionally, `REFERENCE_SELECTION_RU.md`, `COMPARABILITY.json` (what is/isn't compared), `manifest.sha256`. Stable channel identity, units and gain.

## No premature assumptions
- No universal high/low DC bias voltage threshold; know sensor specs.
- FFT of independently captured signal vs non-synchronous MVKView = illustration, not numerical proof.
- High crest/kurtosis may be real machine impacts, not electromagnetic interference.
- Missing raw sample trace in proprietary binaries limits confidence.
- Do not store industrial raw captures or binaries in public GitHub, only design/test vectors/anonymized metrics and results with operator permission.

## GitHub tasks
Issues #1–#6 original Stage13 validation; new #7 quality of 16 ADC, #8 proprietary binary & asynchronous reference import, #9 reference channel shortlist.
