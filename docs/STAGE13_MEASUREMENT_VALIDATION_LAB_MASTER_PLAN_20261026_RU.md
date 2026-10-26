# MVK01 Stage 13 — измерительная лаборатория и план доказательной проверки (редакция 2026-10-26)

## Назначение
Stage 13 — изолированный **reference/validation harness**, а не новая версия основной MVK Reader Web. Она принимает офлайн RAW/PCAPNG и отдельно санкционированный TCP, выполняет независимо проверяемые вычисления, сохраняет все входные расчётные кадры и промежуточные результаты, выпускает вердикт по каждому измерению. **Основная v0.3.40 не изменяется до gate принятия.**

## Факты на старте
- Уже проверены получение VAST_MVK и индивидуальных коэффициентов восьми каналов, ADC 65536 Гц, AUX160/AUX4700 и диагностика.
- Полевые измерения №83/84 доказали поступление данных и сохранение SQLite, но выявили RST вместо FIN и неверную относительную ось времени. У №84 часть полей приборных расчётов нулевая при ненулевой осциллограмме.
- Прототип Stage 13 P0 сохраняет все 144 float32 из восьми записей AUX4700 и все четыре 16-байтовых элемента AUX160; требуется приёмка на PCAPNG, перенос связи кадров и точных временных отметок. Предыдущие 59 unit-тестов не являются метрологической аттестацией.
- Неподтверждённые поля и диаграммы MVKView нельзя автоматически отождествлять с нашим FFT.

## Что перенять из открытых проектов GitHub
1. **SciPy signal**: явные настройки detrend, window, nperseg, noverlap, scaling=spectrum/density, независимо тестировать RMS/Peak/PSD и энергетическую нормировку. https://github.com/scipy/scipy/blob/main/scipy/signal/_spectral_py.py
2. **ObsPy PPSD**: хранить метаданные прибора, коэффициенты и версии вычислительного ядра; сегменты с пропусками отмечать отдельно, не заполнять нулями незаметно; сохранять пригодные для переоткрытия спектральные агрегаты. https://github.com/obspy/obspy/blob/master/obspy/signal/spectral_estimation.py
3. **QCoDeS**: один замер = один dataset с ID/GUID, параметрами, временными отметками, состоянием и результатами в SQLite; разделить каталог сеансов и детальные данные каждого замера. https://github.com/microsoft/Qcodes/blob/main/docs/dataset/introduction.rst
4. **Telegraf**: независимые input / processing / aggregation / output модули, сквозной контроль успешности доставки или отбрасывания метрик, раздельные counters по стадиям. https://github.com/influxdata/telegraf/blob/master/docs/INPUTS.md

Это примеры архитектурных приёмов, **не доказательство идентичности МВК и других приборов**.

## Целевой конвейер
SOURCE (RAW/PCAPNG/TCP) -> STREAM & PROTOCOL AUDIT -> CALIBRATED SAMPLE WINDOWS -> REFERENCE DSP (в RAM) -> FULL INSTRUMENT DATA STORE -> COMPARISON ENGINE -> SQLITE/REPORT ZIP -> ACCEPTANCE VERDICT.

Отдельные пользовательские режимы: RECORD processed-only (история) и LIVE only (без истории). Явный DEBUG CAPTURE с ограниченным объёмом исключительно по запросу, RAW не сохранять постоянно.

## Этапы реализации и acceptance
**P0-1 Полный архив протокола.** Дополнить AUX4700_FULL и AUX160_FULL: каждый кадр, channel, absolute stream offset, device sample counter/relative timestamp where valid, recv UTC with uncertainty, raw uint32 bits, original length, per-frame SHA256/CRC if computed. Контроль дубликатов/пропусков и чисел записей. Проверить реальным RAW/PCAPNG.
**P0-2 Независимое DSP-ядро.** Жёсткий контракт: калибровка -> убрать DC/пометить, anti-alias where needed -> FFT bins, velocity/displacement integration with explicit low-frequency filter, window and gain (coherent/noise power), amplitude Peak/RMS, PSD/ASD, Welch and configurable overlap. 0-100/200/1000/3000 Гц и произвольная полоса; 0.5/1 Гц при достаточном окне. Версионировать параметры каждого результата.
**P0-3 Ground truth.** Synthetic golden signals: синус целой/нецелой линии, две гармоники, DC, белый шум, импульс, затухание, zero/NaN, изменение gain, подменённый канал, пропуск кадров. Проверки peak, RMS, Parseval/интеграл PSD, частоты, скорости и перемещения с заранее определёнными допусками по классам сигналов.
**P0-4 Два представления спектра.** Независимый FFT c корректными осями/единицами; AUX4700 все 144 по каналам как приборный output, сопоставление только документально подтверждённых metric/band и если сравниваемый channel, window, величина, фильтр и timing совпадают. Overlay с прозрачными допусками: absolute error, relative error, peak frequency Δ, spectral distance.
**P0-5 Traceability & completeness.** received -> parsed -> calibrated -> computed -> committed -> exported, per ADC/frame IDs и coverage, SQLite integrity, byte/bit comparison, SHA256 source+exports, Windows sqlite close and graceful socket close. No silent data loss.
**P1-6 Веб-лаборатория.** Выбор №83/84, АЦП, type, f-range, resolution, unit, reference source; live vs recording; tab «Качество потока», «Калибровка», «Спектры», «Показатели прибора», «Сравнение», «Протокол теста»; удобный экспорт ZIP.
**P1-7 Полевые acceptance.** Windows test suite; offline replay в произвольных chunks; 30 с №83/84, repeated connect, Live, manual stop, separate Wireshark, cross-check MVKView (same ADC/type/band/window). Без одновременных конкурирующих TCP подключений.

## Структура отчёта каждого запуска
`REPORTS_FOR_ANALYSIS/<timestamp>_<device>_<mode>_<guid>/`:
- `manifest.json` (schema/code versions, checksums, settings, result, errors)
- `connection.json` (Ethernet local/bind, endpoints, connect/first/last/close timestamps)
- `calibration.json` (eight channel gains/sensitivities from VAST_MVK, field provenance)
- `stream_audit.json` (frame count, counters, gaps, full coverage)
- `aux4700_full.csv.gz` and `aux160_full.csv.gz` (all float bits/status/offsets)
- `fft_lines.npz` or `fft_lines.parquet` and `fft_method.json` (all saved f bins and numeric values + windows/filter/version)
- `comparison.csv` / `comparison.json` (apples-to-apples comparisons only)
- `persistence_audit.json` (expected vs actual row/binary counts, SQLite integrity)
- `processed.sqlite`, optional PNG/HTML graphs, event log.
**Не удалять исходные пользовательские RAW/PCAPNG**. No background auto-upload, don't put proprietary captures in GitHub.

## Release gates
A: корректное сохранение всех приборных расчётных данных с 100% идентичностью битов в контролируемых RAW/PCAPNG;
B: эталонные синтетические DSP-тесты в пределах заранее прописанных допусков;
C: сравнение одного и того же канал/величина/полоса/момент с MVKView или корректно помечено «нет ground truth»;
D: стабильность на Windows при старте, стопе, отказе/потере TCP, закрытии SQLite и экспорте;
E: файловая спецификация и integration API с backward compatibility;
F: независимое явное согласование интеграции после acceptance. Пока gate A-E не закрыты, не изменять v0.3.40.

## Реестр
GitHub Issues #1, #2, #3, #4, #5; этот документ — актуальный верхнеуровневый план. Результаты разделять на VERIFIED, HYPOTHESIS, TODO.
