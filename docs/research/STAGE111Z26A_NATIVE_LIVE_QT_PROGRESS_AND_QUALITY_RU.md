# MVKView Compatible Stage111Z.26A — текущая запись: Live Progress + Quality, БЕЗ второго TCP

**Дата:** 02.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. Статус: **CODE IMPLEMENTED + OFFLINE CORE/Qt VERIFIED**. Финальная сборка единого EXE проверяется отдельным job. **НЕ** заявлять новой аппаратной приёмки.

## 1. Исходная база, которую нельзя потерять

- **Native R6.1** (`tools/research/native_tcp10230_stage108_live_recording_r6_1/source/`) — аппаратно проверенный Stage109 на МВК №84; единственный TCP/10230 клиент. Его существующий `Read→RAW→8 ADC live BIN spool→SHA/replay→8 BIN+8 TSXML+VALUES/TABLE` путь сохранён.
- **FRange** live writer уже найден Stage52 (`_Unit125:00808653` после `GetFloatByAddr(0x0E)`); archive source Stage61/62; общий буфер BIN Stage51/Z23. Вторично коэффициент к BIN НЕ применяется.
- Существующий `mvk_compatible/desktop/main_window.py` содержит исходные 3 пользовательские вкладки и версионированные численные кандидатные алгоритмы original GetSignal/GetSpectrum. **Не переписывать FFT goldens Stage111Z8/Z10.**
- Предшествующий Stage111Z25 one-file Windows acceptance: source `5e299ea9b77c568b9a6431462a5fdbe525da98ca`, [Actions #41383158906](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41383158906), 3 jobs PASS.

## 2. Реализовано Stage111Z.26A

**Go (opt-in только для Qt):**
- `source/live_progress.go` — файл `MVK_NATIVE_LIVE_STATUS.json` в **закрытой локальной папке единственного сеанса** `TEST_<timestamp>`. JSON строится из `Monitor.Snapshot` на той же приёмной горутине, не читает повторно сеть, не трогает исходные RAW/BIN, пишет полностью во временный файл и заменяет целевой после закрытия. Стандартный Native без `-live-status=true` не публикует эту телеметрию.
- `source/main.go` вызывает publisher при CONNECTING/RECORDING, затем VERIFYING и COMPLETED/REFUSED; частота записи ограничена (~750 мс). При ошибке вспомогательного файла предупреждает и **не прерывает существующий RAW**.
- `source/monitor.go` собирает для UI фактические frames/samples/rates, gaps/NaN/Inf для **8 ADC + 2 TACH**, приборный DSP status только из настоящего подтверждённого AUX4700 (только последний тик), момент последнего пакета и AUX. **Нулевой DSP status не придумывается до AUX.**
- `source/live_progress_test.go` — offline проверяет штатный режим без sidecar, последовательную запись, 8+2, 0x400, отказ sidecar.

**Python Core (без Qt и сети):**
- `mvk_compatible/core/native_r6_live_status.py`: ограничение длины локального JSON; контроль схемы, единственного каталога сеанса, ожидаемого IP МВК и выбранного IPv4 Ethernet, десяти уникальных каналов, явного read-only flag, UTC меток, отрицательных/повреждённых значений. Не следует символическим ссылкам; при несовпадении — fail closed.
- `mvk_compatible/core/native_r6_bridge.py`: добавлен только аргумент `-live-status=true` при явном запуске из Qt. SHA built-in Go, одноклиентный TCP, завершение/аудит ZIP не менялись.

**Qt Live Dialog:**
- `mvk_compatible/desktop/native_capture_dialog.py`: индикатор прогресса по длительности, RAW МиБ, кадров и AUX обновлений; таблица **10 каналов**, статус DSP 0x00000400 красной логической меткой `DSP: ПРЕДУПРЕЖДЕНИЕ` (без фиктивного «здоров»), контроль пропусков/NaN/rate, индикация отсутствия AUX и «устаревший статус» при потере обновлений; раздельные вкладки «Каналы · live» и «Журнал». `QTimer` только читает локальный JSON, не создаёт второе сетевое подключение.
- Когда Native завершает запись, действует прежний строгий offline postprocessing `RAW SHA + 19 SHA output + AUX provenance → ZIP → OfflineSession.open`, после чего открываются существующие три вкладки.

## 3. Достоверность / граница StageZ26A

| Что | Уровень |
|---|---|
| Реальный транспорт, формат, потоковый BIN, 8 ADC +2TACH, калибровка | **Stage109 REAL DEVICE VERIFIED**, старый Go R6.1 |
| Новая sidecar-схема, Qt-панель, статусы, fail-closed, отсутствие нового TCP | **CODE-IMPLEMENTED и offline CI** |
| Последнее 0x400 и Status DSP — из приборного AUX | SOURCE/DATA model verified; не диагностика здоровья датчика |
| Новая Windows GUI+Go на физическом МВК | **НЕ ПРОВЕРЕНО**, нужен отдельный допуск |
| Онлайн обновление ГРАФИКОВ трёх исходных вкладок из кольцевого буфера | **НЕ РЕАЛИЗОВАНО Z26A**; это Z26B после безопасной приёмки local live boundaries |
| Оригинальный same-run BIN, полный FFT bitwise, UI pixel parity, контрольные зоны и архив долгих сессий | **ОТКРЫТО**, согласно Master Plan |

**Запрет:** не показывать предварительные локальные статусные снимки как финально проверенный оригинальный MVKView DSP/FFT/BIN. Нельзя считать 0 статусом датчика, пока AUX не получен; нельзя выдавать `TACH samples` за доказанный RPM, `RAW bytes` за физическую вибрацию.

## 4. Независимые тесты и дальнейшие этапы

- `mvk_compatible/tests/test_stage111z26_native_live_status.py` — чистые синтетические status snapshots; повреждение, stale, mismatch, 0x400, неизвестный DSP, symlink, отсутствие сети.
- `mvk_compatible/tests/test_stage111z25_native_recorder_qt.py` — новая Qt проверка реальных отображаемых счётчиков/10 строк при fake status; не подключается к прибору.
- Linux Core: **964 passed, 3 skipped, 30 subtests**. Windows Core: **965 passed, 2 skipped, 30 subtests**. Windows Qt: **39 passed**. Эти результаты относятся к GitHub Actions [run #41384453175](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41384453175); полную приемку считать только после финального Windows EXE job.
- Следующий **Z26B**: verified-read-only live BIN ring + переключение настоящих 3 вкладок без второго TCP, архив/история сеансов, качество и отказоустойчивость. Перед загрузкой к прибору нужен офлайн real-RAW replay новой GUI-оболочки и отдельный field-acceptance. Затем Z27 (same-run original-vs-native BIN), Z28 (полный DSP/TACH), Z29 GetSignal, Z30 GetSpectrum, Z31 UI 1:1, Z32 long session согласно [Full Master Plan](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).

**Важно:** архивы `Projects.7z`, IDP, DFM/PAS/EXE/PCAPNG/RAW/BIN реальные в GitHub и CI не помещать.
