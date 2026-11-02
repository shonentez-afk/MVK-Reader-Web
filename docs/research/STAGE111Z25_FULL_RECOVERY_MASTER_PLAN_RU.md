> **STAGE111Z.26A UPDATE (02.11.2026): LIVE STATUS/QC ADDED, NOT ORIGINAL LIVE GRAPHS.** Source commit `f8ef5692a1f4b90a5a642b37427ded11b114b884`. Existing Native R6.1 remains sole TCP client; opt-in local JSON status with 8 ADC+2 TACH counters, actual AUX DSP status, freshness, Qt progress+quality table, fail-closed parser/tests. [Detailed Z26A](STAGE111Z26A_NATIVE_LIVE_QT_PROGRESS_AND_QUALITY_RU.md). [Actions #41384453175](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41384453175): Linux Core 964 PASS, Windows Core 965 PASS, Windows Qt 39 PASS, Go test/vet/build PASS; **Final EXE PASS:** GitHub Artifact [13114542769](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41384453175/artifacts/13114542769), 68 477 949 байт, tested EXE SHA256 `853f8fcd530d2070724aeb26bcff8add206e487f87db36f2d9aceeab70cc8b03`, 3/3 jobs SUCCESS; NEW GUI/Go physical device acceptance remains OPEN. **Next Z26B**: verified local live sample read windows, original GetSignal/GetSpectrum candidate only with provenance and constraints, one session/one socket; no premature real-time original parity. All Z27–32 gates below remain open. Do not repeat Stage52/108/109.

> **ATTESTED Z.25 BUILD (02.11.2026):** [GitHub Actions #41383158906](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41383158906) completed ALL 3 JOBS SUCCESS, tested source SHA `5e299ea9b77c568b9a6431462a5fdbe525da98ca`, artifact id `13113903664`, Windows EXE SHA256 `e1f27e5e2a78257942899c3b9d1c758cf05adcb1d112ae3fa0db46c4a8727e76`. Linux 948 passed, Windows Core 949 passed, Windows Qt 38 passed, Go Native test/vet/build PASS. **Z.25 offline CI/onefile gate CLOSED; физическая новая GUI/Go сессия и live plot/parity остаются OPEN.** Detailed [QA report](STAGE111Z25_NATIVE_R6_QT_ONEFILE_WINDOWS_QA_RU.md). Do NOT conflate new docs-only commits with tested code SHA.

# MVKView Compatible — единый план ПОЛНОГО восстановления (Stage111Z.25)

**Дата ревизии:** 02.11.2026. **Исследовательская ветка:** `research/stage111-mvkview-desktop-20261029`. **Главное решение:** только автономное Windows Qt/PySide6 приложение + существующий проверенный Go Native R6.1 (внутренний компонент), БЕЗ возврата к Web v0.3.40. Не начинать функции заново, в первую очередь использовать ранее восстановленное.

## 0. Статусы и правила достоверности

- **SOURCE-VERIFIED** — оригинальные DFM/IDR фрагменты, адреса и структура проверены; это ещё не runtime parity.
- **DATA-VERIFIED** — независимая проверка реальных RAW, PCAP, BIN, чисел/хешей.
- **CODE-IMPLEMENTED** — функция есть в нашей ветке, но не обязательно проверена на Windows/оригинале.
- **CI-VERIFIED** — workflow конкретного кода завершился SUCCESS; EXE объявлять готовым **только после** SUCCESS Windows artifact.
- **OPEN** — нет численного/побайтового/визуального доказательства, хотя алгоритм-кандидат реализован.

**Инварианты:** stable `main` и прежняя Web v0.3.40 не изменять; не менять подтверждённые FFT golden Stage111Z.8/Z.10; на прибор никаких прикладных команд, Modbus, конфигурации, прошивок; никаких приватных PAS/DFM/IDP/EXE/PCAP/RAW/BIN/TSXML/PNG в GitHub/Actions; отсутствие доказательства не маскировать «успехом».

## 1. Что уже сделано — НЕ повторять

| Подсистема | Проверенное основание | Состояние |
|---|---|---|
| TCP/10230 8 АЦП/2 тахоканала, 256 float32/кадр ADC, AUX4700, регистры, качество | Stage106–109; R6.1 аппаратный тест №84 30.0128155с, 84855 кадров, 0 client→device app bytes | **DATA-VERIFIED**, не универсальная long-run приёмка |
| Native Go R6.1, Windows EXE, Ethernet IP_UNICAST_IF, RAW, live 8 BIN spool, TSXML, VALUES/TABLE, атомарная проверка | `tools/research/native_tcp10230_stage108_live_recording_r6_1/source/`, Stage108, **Stage109 PASS** | **CODE+HARDWARE VERIFIED**; использовать, а не переписывать |
| Live FRange writer `_Unit125:00808653`, getter `00806964` из offset `0x0E`; tach fallback 1.0 | Stage52, проверено повторно Stage111Z.24 | **SOURCE-VERIFIED**, не повторять «найти FRange» |
| Archive FRange `_Unit128:0084655E` из TSXML/fallback; no double gain | Stage61/62/Z21/Z23, Stage51 shared TmpStream/Storage | **SOURCE-VERIFIED**, per-run byte parity всё ещё OPEN |
| DSP: штатные 43 третьоктавы, 24 RMS/P/PP на ADC, статусы/датчики | Stage55–80/106–110, исходные AUX4700 | **DATA-VERIFIED** для набора реальных тестов, часть UI ещё OPEN |
| Исходный периодический RMS Hann, original local FFT, 4 режима, GetSignal, x87/Delphi кандидаты | Stage81–96, Stage111B–Z.10, Z.22 memory capture | **SOURCE+PARTIAL NUMERIC**, не объявлять total bitwise parity |
| Три видимые вкладки оригинала, скрытые исходные PageStart/PageConfig/PageStatus/PageAdc/PageSpectrum/PageFile/PageCalib | Original `mvkform.dfm`, Stage110/Stage111Z17–20 | **CODE-IMPLEMENTED** Qt старт/сигнал/спектр; UI пиксельный parity OPEN |
| ZIP R6.1, прямые BIN/TSXML и проверки SHA/source provenance | Stage111Z16/Z21 и `mvk_compatible/core` | **CODE-IMPLEMENTED**, оригинальный same-run BIN parity OPEN |
| Windows Qt EXE/CI | GitHub Actions Stage111Z15–23 (последняя ранее принятая сборка в START_NEW_CHAT) | Прежний release verified, **новые коды НЕ заявлять собранными без нового CI** |

## 2. Stage111Z.25 — подключение ГОТОВОГО Native R6.1 в единый Windows EXE

**В этом проходе добавлено (CODE-IMPLEMENTED; текущий CI/Windows artifact отдельно проверять):**
1. `mvk_compatible/desktop/native_capture_dialog.py` — локальный Qt controller: список интерфейсов, выбор Ethernet IPv4, IP МВК, длительность и лимит RAW, папка, явное подтверждение допусков, локальный журнал, Start / graceful Stop / открыть итог; никаких Qt-сокетов.
2. `mvk_compatible/core/native_r6_bridge.py` — проверка SHA встроенного Go EXE, validation IPv4/выбранных каталогов, безопасные аргументы, отдельная папка сессии, проверка `STAGE108_EXPORT_STATUS.json`, RAW SHA, всех 19 output SHA, AUX provenance, атомарная ZIP-упаковка и повторная проверка через существующий `OfflineSession`. Исходные RAW/BIN НЕ изменяются.
3. Native Go получил **необязательный** `-stop-file` и локальный watcher, отменяющий `context.Context` с последующей обычной `Finalize`; без флага прежний проверенный Live тракт неизменён. **НЕ** применять `QProcess.kill()` / `terminate()` как штатную остановку; при отсутствии файла прежний режим R6.1 сохраняется.
4. `mvk_compatible/desktop/main_window.py` — вход «Запись с прибора» с главного экрана «Задачи» и из меню «Файл»; полученный ZIP автоматически открывается в существующих трёх вкладках.
5. `.github/workflows/stage111-desktop-offline.yml` — при Windows EXE сначала Go tests/vet/compile из принятого source, затем PyInstaller `--onefile` с вложенным Go EXE + SHA. Новые pure-core и Qt smoke тесты. **Новая сборка требует фактической проверки CI и Artifact**.

**Оговорка**: это мост от законченного измерения до всех трёх вкладок, а **не** ещё live streaming charts во время приёма. Временные метки VALUES — часы ПК, и оригинальный BIN той же сессии не сравнен.

## 3. Оставшаяся дорожная карта — в правильном порядке

| Приоритет | Этап | Что сделать, не повторяя готовое | Условия закрытия |
|---|---|---|---|
| P0 | **Z.25 CI / интеграционный QA** | Проверить Go/Windows Core/Qt/one-file build, реальное нахождение вложенного Native EXE, корректное завершение stop-file, invalid NIC, отказ без approval, source audit; проверить UX без прибора | Все jobs SUCCESS, checksum Artifact, Windows offline GUI проверена |
| P0 | **Z.26 Live UX 1 программа** | Состояния recording / validating / completed / refused, индикатор качества, журнал и прогресс, выбор сессий, безопасное закрытие; затем по отдельной приёмке потоковое обновление текущих вкладок из одного Native без новых сетевых соединений | Никаких двух socket-клиентов, единая временная база и 8ADC/2TACH, fail-closed |
| P0 | **Z.27 Original BIN/TSXML ↔ same-run TCP parity** | На частной паре одного сеанса проверить original writer FRange, режим/ADC/sample index, TSV/TSXML, BIN против Native byte-by-byte; контракты Single и Byte/Count раздельно, не умножать K повторно | Числа/хеши и причина каждого расхождения документированы. Нет пары → OPEN, не подставлять synthetic |
| P0 | **Z.28 Расчётные данные / статусы** | Полная исходная PageStatus: оригинальные 43 полосы, 24 RMS/ПИК/ПИК-ПИК и режимы, TACH и системные поля, контрольные зоны, тревоги и правильные источники без повторных DSP вычислений | Совпадение по одному AUX/каналу/тику, status 0x400 не объявлять OK |
| P1 | **Z.29 Временной сигнал** | Original GetSignal AC/AC+DC, границы интервалов, ring buffer/rewind, временные оси и каналы, огибающая (только при доказанной FIR/IDP), zoom/cursor/clipboard/CSV | Численный паритет по идентичному BIN/window и screenshot-пара |
| P1 | **Z.30 Спектр** | Закрыть original Float32/x87 radix-2 parity по оригинальным real golden, все четыре режима (лог., ВУ, ВС, ВП), интегрирование, Y/X шкалы, фильтры/огибающая, Cursor Copy/Save; не менять доказанные Z8/Z10 | Сверка полного массива bins/cursor и числа пиков со старым MVKView на той же записи |
| P1 | **Z.31 UI/UX 1:1** | Stage111Z17 backlog 18 (9 code, 5 partial, 4 open на дату отчёта), все основные/внутренние оригинальные страницы, меню, статусы, клавиши, 100/125/150% DPI, 1024x704, original XOR, pixel-compare | Заполненный backlog + парные screenshot оригинал/Qt для одного окна/данных, без ложно закрытых P2 |
| P1 | **Z.32 Длительная Live/архив/отказы** | Обрыв, неполный кадр, смена gain/rate, сетевые переподключения только по разрешению, 30с→длительные сессии, нагрузка/запись/архив (SQLite опционально, **ещё НЕ реализован**) | Протокол и QA сценарии, запись не теряется, повторная проверка пакета, полный audit |
| P2 | **Release acceptance** | Собрать автономный Windows EXE/установщик, проверять update/распаковку, recovery и общую регрессию старых модулей, документировать known gaps | Не выпускать 1:1 compat, пока источники/числа/UI по критериям выше OPEN |

## 4. Полный продуктовый acceptance gate

**Одна программа, один приборный сеанс, три оригинальные вкладки:** проверенные 8 ADC, 2 TACH, метрики и статус DSP, временной график, локальный GetSpectrum, BIN/TSXML, текущая запись и архив, правильная калибровка, UX. Отличать «работает как исследовательский кандидат» от «подтверждено как точный оригинал».

**Чего пока нет:** Live-визуализации каждого приходящего кадра; оригинального same-run BIN/TCP parity; полной оригинальной обработки Byte/Count, guard/reconnect-long tests, пиксельного UI и bitwise FFT parity. Не терять исходные Stage111Z8/Z10 reference.

## 5. Порядок повторного подключения нового чата

1. Прочитать **`START_NEW_CHAT_RU.md`** и этот план, затем Stage111Z.24 correction.
2. Проверить последний GitHub HEAD + **реальный Actions run** и его source SHA, а не только «рабочий» код.
3. Основные исходники: `mvk_compatible/`, `tools/research/native_tcp10230_stage108_live_recording_r6_1/source/`, `docs/research/STAGE109_R6_1_FIRST_REAL_LIVE_DEV84_ACCEPTANCE_RU.md`, `docs/research/STAGE111Z17_UI_UX_AUDIT_BACKLOG.json`.
4. Не проводить повторно Stage52/Stage51/Stage108–109, не возвращать Web, не публиковать частные данные.
5. Первое действие следующего этапа — закрыть **Z.25 CI + реальный Windows offline QA** и только потом обсуждать аппаратный тест расширенной GUI-сборки.
