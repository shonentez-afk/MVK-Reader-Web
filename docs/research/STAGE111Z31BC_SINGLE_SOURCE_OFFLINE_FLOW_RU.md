# Stage111Z31BC — одна проверяемая цепочка File → ADC → Spectrum → Status

Дата: 11.11.2026. Рабочая ветка research/stage111-mvkview-desktop-20261029.
База: Stage111Z31BB, последний подтверждённый source fe5707972f872f47eb21b453d245585a2e04ae7a, CI #42964108279 SUCCESS.

## 1. Что было разорвано в Desktop

После Stage111Z31BA/BB главные Delphi формы, семь страниц и безопасные UI-состояния были идентифицированы и отображались. Но четыре фактических экрана файлов/сигнала/спектра/состояния продолжали напрямую обращаться к OfflineSession/DirectBinSession **параллельно**:

- PageFile выбирала session/channel и описывала AUX/VALUES декларативно.
- PageAdc отдельно вызывала session.waveform() / envelope().
- PageSpectrum отдельно вызывала session.samples(), spectrum() или spectrum_envelope().
- PageStatus отдельно вызывала session.calculations(tick), а затем разделяла результат между двумя Qt таблицами.

Проблема: отсутствие единого клиент-независимого контракта «один источник / один выбранный канал / один тик» позволяло экранным модулям разойтись, а исключение повторной проверки VALUES/AUX оставляло на экране показатели предыдущего тика. Неправильно было также говорить, будто отдельно загруженная BIN/TSXML даёт оригинальные DSP/VALUES/AUX.

## 2. Реализовано целым пакетом, не новый DSP

В новом чистом Core mvk_compatible/core/offline_measurement_flow.py:

1. Immutable OfflineMeasurementFlow.bind(session) принимает только реально проверенные OfflineSession (Native R6.1 ZIP) или DirectBinSession (оригинальный локальный BIN/TSXML Single). Доступные каналы, тип источника, число обновлений, выбранный ADC и selected DSP tick строго валидируются.
2. select(channel, tick_index) возвращает новое состояние, а require_session(session) запрещает перенос чужой session, даже при одинаковом серийном номере и файле.
3. samples() применяет существующий строгий ZIP SHA/TSXML или Direct BIN SHA-validator, не изменяя Float32, FRange, усиление или FFT.
4. source_record() выдаёт **только source-derived метаданные**: тип, канал, тик, число реальных Single, Fs, контрольную SHA256 и флаги доступности; никогда абсолютный путь, сырой BIN, IDP/PAS, оригинальный screenshot или приватный исходный массив.
5. status_snapshot() возвращает только валидированную Native R6.1 VALUES/AUX/TIMELINE для данного тика; проверяет serial, tick и восемь исходных ADC. Для DirectBin возвращает None, не вызывает отсутствующие calculations() и не придумывает DSP/TACH/контрольные зоны. status_table(index) делегирует существующий source_pagestatus_table() с тем же снимком.
6. waveform(), envelope(), spectrum() и spectrum_envelope() — без перерасчёта или изменения входов делегируют **существующий** собственно вычислительный Core. Они выбирают канал из того же immutable source-контекста. Уже принятые Native R6.1, Window/FIR/FFT/LOG и оригинальный Code20/LOG0 0 ULP не тронуты.

Это не выполняет новый приборный протокол, не создаёт конвертер оригинального BIN, не утверждает наличие калибровки DirectBin и не имитирует недостающие AUX.

## 3. Подключение во ВСЕ четыре экрана

- desktop/main_window.py при открытии локального ZIP/BIN создаёт OfflineMeasurementFlow **до записи нового активного сеанса**. При переключении АЦП и тика _current_offline_flow проверяет тождественность исходной session и синхронно обновляет selection.
- PageAdc использует flow.waveform()/envelope(); PageSpectrum — flow.samples()/spectrum()/spectrum_envelope(); PageStatus — flow.status_snapshot(), точно с тем же тиком и 8 ADC. Исходные расчётные методы ядра не переписаны и их Float32 результаты не масштабируются повторно.
- desktop/original_shell.py PageFile получает **тот же flow**, запрещает несовпадение каналов, а sourceFileEvidence показывает выбранный ADC, число реальных отсчётов, Fs, проверенный SHA256 prefix и тип достоверных данных. Для Direct BIN прямо пишет, что DSP нет, калибровка не подтверждена. Native VALUES только там, где Native exporter их проверил; AUX/peak только при подлинной дополнительной проверке.
- При входе в Live preview предыдущая архивная модель File автоматически очищается. При закрытии/открытии другого измерения Core context сбрасывается или создаётся заново.
- **Fail-closed:** если пересчёт текущего VALUES/AUX тика завершился ошибкой (изменившийся/испорченный источник), старые _pagestatus_snapshot, старые 24/43 табличные показатели, системный статус и TACH более НЕ остаются отображёнными как новый тик. Выводится явная ошибка и placeholder.

## 4. Тесты без оригинальных приватных данных

- test_stage111z31bc_offline_measurement_flow.py — синтетический Native ZIP (8 ADC, 2 ticks, полный AUX) и Direct BIN/TSXML (только ADC4), несмешиваемая session identity, канал/тик, File record digest, PageStatus 43-band status only when actually backed, bitwise equivalence GetSignal/GetSpectrum to existing methods, no DSP for direct, file mutation catches SHA failure, rejects unknown channels/invalid ticks.
- test_stage111z31bc_qt_crossscreen_flow.py — настоящее Qt MainWindow.open_archive() / PageFile / ADC / Spectrum / Status, channel/tick changes, source provenance label, ZIP→BIN source replacement, no stale DSP, session close, synthetic rejection of current VALUES clears prior DSP. Включено в Windows Qt 150% CI.
- Существующие тесты Stage111Z31BB UI, Stage111Z31AM original numerical, Stage111Z31AZ TQGrapher/bitmap и Native standalone build остаются обязательными.

## 5. Ограничения приёмки

Stage111Z31BC закрывает **межэкранный offline источник и защиту происхождения**, а НЕ полное восстановление всех функций MVKView. Возможности оригинальных трёх форм, 62 DFM/dynamic callbacks, runtime TLanguage, полноценные архивные форматы, приборные Config/Calib, реальный GDI-рисунок и численная приёмка всех Tag/Envelope остаются открыты. Основной исходный native computation по-прежнему аттестован побитово **только на одном физическом Code20/LOG0 capture**. До real Win32 original-vs-compatible operator acceptance не утверждать 1:1.

Аппаратные Upload/Reset/Calib, original x32dbg/F9 и любые действия в оригинальном процессе без нового согласия запрещены. Приватные IDP/DFM/PAS/BIN/screenshots не публикуются в GitHub.

## 6. Результат CI

Статус нового Stage111Z31BC: **PENDING** до подтверждения Linux Core, Windows Core, Qt DPI150 и verified autonomous EXE с Native R6.1. Предыдущая проверенная база: Stage111Z31BB, source fe5707972f872f47eb21b453d245585a2e04ae7a, GitHub Actions #42964108279 SUCCESS, artifact #13830154606.

Следующий большой пакет после BC: восстановление оригинального read-only Config/Channels/Alarms по IDR и Tmvkeditform с сохранением отдельной границы «обнаружен оригинальный обработчик» против «подтверждена семантика»; TLanguage; полноценный сценарный Win32 parity harness поверх двух уже запущенных программ. Точно не прыгать обратно к ручным пиксельным подгонкам, пока не закрыты семантические функции всей программы.
