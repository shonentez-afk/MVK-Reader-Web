# Stage 13 — протокол доказательной отчётности каждого сеанса (2026-10-26)

**Статус:** утверждаемый проект отчётности; код генератора ещё не реализован. Связано с issue #6 и master plan `docs/STAGE13_MEASUREMENT_VALIDATION_LAB_MASTER_PLAN_20261026_RU.md`. Production v0.3.40 не трогать.

## Принцип
Два продукта **одного** прогона: (а) данные измерений для пользователя в processed.sqlite и графики; (б) **evidence bundle для разработчика**, проверяемый без прибора, со всеми расчётными кадрами, промежуточными цифрами и происхождением. Каждое заключение имеет статус VERIFIED / UNVERIFIED / NOT_COMPARABLE / FAIL. Не путать «приняли поток» с «измерение метрологически достоверно».

## Прототипы для архитектуры
- QCoDeS: experiment/run/GUID, dataset в SQLite, metadata + timestamps: https://github.com/microsoft/Qcodes/blob/main/docs/dataset/introduction.rst
- ObsPy: Trace.stats {starttime, npts, sampling_rate, calib}; явный анализ gaps/overlaps: https://github.com/obspy/obspy/blob/master/obspy/core/stream.py
- Frictionless: декларативная схема, validation report с кодом ошибки и row/field: https://github.com/frictionlessdata/frictionless-py

## Рекомендуемая структура
```text
REPORTS_FOR_ANALYSIS/
  ALL_TESTS.csv
  20261026T101307Z_MVK83_RECORD_<run_uuid>/
    manifest.json
    summary_ru.md
    run_events.jsonl
    connection.json
    calibration.json
    stream_audit.json
    persistence_audit.json
    anomalies.jsonl
    processed.sqlite
    instrument/
      aux4700_full.csv.gz
      aux160_full.csv.gz
    dsp/
      fft_method.json
      fft_lines.npz
      dsp_windows.csv.gz
      comparison.csv.gz
    evidence/
      spectrum_preview.html
      user_notes.json
    checksums.sha256
```

## Временные поля
Иметь **три отдельные шкалы**: `t_receive_utc_ns` (часам компьютера нельзя автоматически приписывать метрологическую точность), `t_monotonic_ns` (порядок/прошедшее время во время процесса) и `t_adc_relative_s` (счётчик/65536 с учётом wrap). `sample_counter` хранить как uint32 без округления. Указывать неопределённость сопоставления кадра AUX4700 с ADC, поскольку прибор не обязан давать точный общий timestamp.

## Идентификаторы / трассировка
run_id UUID; frame_seq и stream_byte_offset; adc 1..8; frame_marker+payload_length; origin `instrument` vs `computed`; calibration_hash; window_id; sample_counter_begin/end; algorithm_version; dataset_id. Для каждого FFT-bin: window_id, bin_index, frequency_hz, unit, amplitude_rms, window/scaling/filter, floating-point method. Не подменять массивы спектра скриншотом.

## Что пишем непрерывно
- START: фактические IP+port локального/удалённого сокета, Ethernet, профиль, SHA версии кода/requirements, версия ОС; Windows permissions, disk free; device_id.
- CONNECT: DNS не нужен для IP, start/success/fail, errno, timeout, first byte, received VAST_MVK, каждый ADC gain+sensitivity и исходные LE биты.
- RECIEVE: frame counters by type; ADC counter continuity and per channel 8-alignment; AUX4700 all values+status; AUX160 all words; malformed/unknown; processing queue levels, latencies and processing lag; rolling source SHA256. Высокочастотные счётчики копить в памяти/periodic checkpoints, не синхронный fsync на каждый ADC кадр.
- COMPUTE: each DSP window used sample counter range, gain, DC/detrend, filter, Hann normalization/ENBW, Welch options, FFT bins, RMS acceleration/velocity/displacement with exact unit, quality flags.
- COMMIT: per-table expected/committed rows; transaction boundaries; SQLite journal mode/integrity; disk usage, provenance.
- STOP: trigger manual/timed/error/eof, how socket closed FIN/RST if verified against PCAPNG, final bytes/frames, unfinished window and why discarded/retained.
- EXPORT: manifest and hashes only after files closed; zip digest; completeness test.

## Параметры проверки
Comparison engine сопоставляет только одинаковые АЦП, величину, физические единицы, частотную полосу, RMS-vs-Peak, метод фильтра и совместимый временной интервал. Если MVKView совпадение не доказано, заполнять reason `NOT_COMPARABLE`, а не нулевое отклонение. Разные AUX160/AUX4700 трактовать отдельно; известный №84 AUX160 нулевой не является нулевым сигналом АЦП.

## Автоматические вердикты
- PASS — контролируемый критерий и допуск выполнены.
- WARN — измерение возможно полезно, но есть диагностическая проблема/отклонение.
- FAIL — данные потеряны, повреждены или не записаны; результаты недостоверны по данному критерию.
- NOT_CHECKED — критерий не исполнялся.
- NOT_COMPARABLE — внешние величины неэквивалентны или не было эталона.
Каждое заключение: `rule_id`, `severity`, `expected`, `actual`, `tolerance`, `evidence_ids`, `source`.

## Особые испытания
- Разрыв TCP и повторное подключение, ручная остановка в середине TCP-пакета, Windows WinError32, заполнение диска, browser close while Collector runs, interrupted app crash, device #84 ADC7/8 0x400, #83 AUX160 transitions, wrap ADC counter, clock skew, corrupted/truncated capture, single dropped frame.
- Перечень проверок и дефектов связывать с issue #1-#6.

## Правила объёма и приватности
Нет постоянного RAW; все расчётные AUX и линии FFT сохраняются. При подозрении на DSP-ошибку без RAW восстановить полный сигнал нельзя. Для **разового полевого опыта** отдельная опция `DEBUG_CAPTURE` (явное разрешение, малый TTL/квота, короткая запись, без автоматического удаления пользовательских PCAPNG). По умолчанию OFF. Данные приборов и пользовательские PCAPNG не заливать в GitHub. В GitHub только спецификации, тесты на синтетике и обезличенные краткие отчёты.

## Приёмка
Инструмент `verify_bundle.py`: validate schema, SHA256 всех файлов, SQLite PRAGMA integrity_check, counters, 8×144 AUX4700, 4×16B AUX160, missing spectrum bins, calibration metadata, debug storage OFF, summary vs data. Все пять категорий выдержаны на офлайн RAW/PCAPNG и Windows-полевых сеансах до переноса в production.
