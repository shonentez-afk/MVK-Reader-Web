# START NEW CHAT — MVK Live Standalone: диагностика, архив, качество, паспорт

> **ПРИНЦИП ВЕТКИ: СОБСТВЕННОЕ ПРИЛОЖЕНИЕ, А НЕ КОПИЯ MVKView.** MVK Live Standalone — независимый современный анализатор по **реальному потоку данных МВК01**. Исходный MVKView используется только для проверки протокола/трактовки приборных данных там, где это необходимо, **не как шаблон интерфейса и не как предел функций**. Интерфейс, обработка APP_DERIVED, диагностика, сохранение и сравнение измерений проектируются самостоятельно. Открытые и закрытые сторонние программы — сравнительные референсы UX/алгоритмов; перенос стороннего исходного кода допускается исключительно после проверки лицензии. Оригинальный приём RX, FRange, каналы и AUX4700 не изменять без доказательной причины.


**Дата:** 18 ноября 2026. **Рабочая ветка:** `feature/mvk-live-standalone-20261117` репозитория [MVK-Reader-Web](https://github.com/shonentez-afk/MVK-Reader-Web). **Этот документ — handoff к новому чату**, а не отчёт о том, что новые функции написаны.

**Обновление 18.11.2026:** добавлена общая матрица реализации **82 пунктов** с проверкой первоисточников, реальными скриншотами, исходным кодом/лицензиями, статусами и приоритетами: [UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.md](UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.md); [Excel-compatible CSV](UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.csv). Сверены совместно три приватных источника MVKView, включая DFM controls `PageAdc`/`PageSpectrum` и `TDSXFastFourier`/`GetSpectrum`, но приватные данные не опубликованы. Не путать каталог реализации с готовым кодом.

## Сначала прочитать

1. [Главная спецификация пяти пробелов и четырёх направлений исследования](FIVE_GAPS_AND_DIAGNOSTIC_RESEARCH_PLAN_RU.md) — ключевой документ, проверка code facts, план пакетов D1–D4 и приёмка.
2. [Полный каталог методов, режимов LIVE/ОКНО/АРХИВ и форм настроек](FULL_VIBRATION_METHODS_REALTIME_RECORDINGS_SETTINGS_SCREENS_RU.md) — сейчас **82 позиции**: 19 LIVE, 43 ОКНО, 20 АРХИВ/условно. Это **не 82 внедрённых метода**.
3. [Подшипники и спектр огибающей](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md), [гармоники/коллизии/маркеры](HARMONIC_OVERLAYS_AND_DIAGNOSTIC_METHODS_CATALOG_RU.md), [сравнение Fast Kurtogram/Protrugram/Infogram/Gini + качество и стандарты](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md).
4. [История, архив и overlay](HISTORY_TRENDS_OVERLAY_DESIGN_RU.md), [W32/A20 поиск признаков и IP-профили](CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md), [README](README_RU.md).
5. В новом чате снова проверить **HEAD ветки и GitHub Actions**. Не считать прошлый PASS достаточным для нового коммита, реальный МВК01 или поверки.

## Пользовательский запрос и обязательный порядок

**Сначала закрыть пять существенных пробелов; затем исследовать четыре направления.** Планы, примеры из сторонних приложений и академические пороги не выдавать за готовые алгоритмы.

| Пробел | Фактическое состояние | Следующее действие |
| --- | --- | --- |
| **G1 — реальные пики vs расчётные частоты** | `advanced.py::envelope_fault_lines` ищет максимум ВНУТРИ ожидаемой полосы; без отдельного `find_peaks`, prominence/width, `peak_id`; `noteworthy` от **одной** линии при SNR >=6 dB | Сначала независимые измеренные пики всего FFT, затем гипотезы, допуски и collision-safe matching; таблица Hn, amplitude, local SNR, source |
| **G2 — боковые и коллизии** | В `vibration.py::bearing_frequency_markers` есть BPFO/BPFI/BSF/FTF, но нет отдельной BDF; экран `app.py` не рисует полноценные sidebands/реальные пики | **BDF=2BSF** отдельная метка; `n BPFI ± k fr`, `n BDF ± k FTF`; BSF ≠ BDF; 1 реальный пик не подтверждает два семейства |
| **G3 — сравнимость архива** | `history_widgets.py` накладывает до 8 кривых по ADC; разные Fs видны с общей Nyquist-границей, но RPM/load/точка не проверены | Классы comparable / conditional / incompatible / unknown, point, source, kind/unit, band/method/NFFT, RPM/source/load, UTC quality; missing ≠ zero |
| **G4 — Quality Gate** | Нет общего отчёта качества измерения до диагностики | Проверить SHA/N/Fs/расширение/пропуски если доказаны, Nyquist, окно T/df, возможный clipping только как подозрение, шум/фильтры, RPM readiness; подробные PASS/WARN/BLOCK/UNKNOWN |
| **G5 — паспорт измерения** | `recordings.py` NPZ V1: Float32 acceleration, ADC, Fs, source_session, capture_end, saved_utc, SHA; `saved_utc` **не acquisition time** | Не меняя NPZ V1, внешний MeasurementContextV1 по SHA: свободный point label, направление/монтаж/датчик/калибровка, RPM и источник, load/mode, timestamp quality; null если неизвестно; **без карточек оборудования** |

**Исследовательские направления после этих оснований:**
- **R1 подшипники:** BPFI/BPFO/BSF/BDF/FTF Hn, отдельные измеренные пики, ±sidebands, collisions, реальные графические overlays и таблица, повторяемость в независимых окнах.
- **R2 выбор полосы:** действующий Fast Kurtogram PySDKit + W41 Protrugram, W42 Infogram SE/SES, W43 Spectral Gini (три последних — только R&D/ПЛАН). На одном и том же неизменном реальном ADC window; сравнивать downstream Hn/sidebands и CPU/RAM, не складывать чужие score.
- **R3 архивные тренды:** конкретные Hn/SNR/prominence/energy/kurtosis и 2–8 сохранённых envelope FFT, истинные источники SHA/время, режим RPM/load и compatibility; EWMA только с валидным baseline.
- **R4 единый экран признаков:** W32 одно окно, A20 архив; подшипники, вал/1×/2×, ослабление, редуктор GMF, вентилятор BPF; без автоматических диагнозов по одной линии или искусственного процента уверенности.

## Реальные файлы кода, которые уже есть

- `mvk_live_standalone/advanced.py` — `envelope_fault_lines`, time features, STFT, CWT, cepstrum, gear markers.
- `mvk_live_standalone/vibration.py` — физические FFT/PSD/ASD, band-pass+Hilbert envelope, кинематические формулы.
- `mvk_live_standalone/kurtogram.py` и `_pysdkit_kurtogram.py` — Fast Kurtogram (лицензия MIT, notice включён).
- `mvk_live_standalone/app.py` — Qt, `bearing_plot`, `_show_bearing_diagnostics`, `_run_bearing_page`, Live/Freeze/NPZ.
- `mvk_live_standalone/recordings.py` — проверяемый immutable NPZ V1; `load_snapshot` **требует ровно два члена архива**; нельзя вставлять третий JSON без нового формата.
- `mvk_live_standalone/measurement_history.py` — отдельный SQLite индекс ORIGINAL AUX4700 и NPZ; `history_widgets.py` — тренды/overlay.
- `mvk_live_standalone/live_ipc.py`, `live_ring.py`, `pipeline.py` и Native Go под `tools/research/native_tcp10230_stage108_live_recording_r6_1/source/` — не вмешиваться в физический приём и single-socket логику.

**Физические ограничения:** один Native TCP/10230; оригинальный FRange применяется один раз; 43 third octave + 24×3 AUX4700 — настоящие приборные скаляры, не waveform; только реальная NPZ даёт FFT/Kurtogram/STFT/огибающую offline. No fake samples, no new TCP, no automatic local-IP scan. RPM MANUAL или принятая оценка из ВС **не** TACH. Отсутствие оборудования/датчика — неизвестно, не ноль и не «исправно».

## Как оформить один большой следующий этап D1

1. Выделить immutable `AnalysisInput` из существующих ring/NPZ без меняющих приём вызовов.
2. Добавить `quality_gate.py` с проверками и кодируемыми reason flags.
3. Добавить `bearing_evidence.py`: независимый `find_peaks` по спектру; набор `PeakCandidate`, `PredictedLine`, `PeakMatch`, `CollisionGroup`, `FamilyEvidence`; физические BPFO/BPFI/BSF/BDF/FTF.
4. Добавить боковые `BPFI±fr`, `BDF±FTF` и Hn, обязательный контроль независимости/разрешимости, таблицу candidate vs found.
5. Qt: реальные маркеры поверх `bearing_plot`, настройки Hn/sidebands/tolerance/SNR, таблица доказательств, клик по peak и явно указанные ограничения, **без карточек оборудования**.
6. Unit/Qt-тесты: 1/2/3 Hn, ложный одиночный удар, 50/60 Hz, BPFO×3≈BPFI×2, shaft collision, невидимые FTF при коротком T, RPM/геометрия null, смена ADC/сессии во время worker, corrupt NPZ/no signal; CI + Windows smoke.
7. После D1 перейти крупными пакетами D2 archive/context, D3 selector comparative R&D, D4 unified evidence. В отчёте каждый статус «реализовано/план/не проверено прибором» отдельно.

## Совместно проверять три приватных источника оригинального MVKView

Они предоставлены проекту в `/mnt/data` и **не входят в GitHub**:
- `/mnt/data/mvkview.idp` — IDR project, символы/типы;
- `/mnt/data/Projects.7z` — исходные Pascal/DFM-реконструкции;
- `/mnt/data/mvk_idr(1).sqlite` — SQLite индекс функций/calls/forms/events.

Все три доступны и локально обследованы в текущем исследовании, включая `TMvkChannelStorage.GetSpectrum`, `pbSpectrum` и обработчики оригинального GUI. Эти приватные материалы не доказывают наличие новых методов огибающей в оригинальном MVKView; новое APP_DERIVED не называть OEM. Если уточняем оригинальное измерение/фильтры/приём — **обязательно сверять все три вместе**, ничего из приватного не коммитить.

## Честные границы работ на момент handoff

**Сделано:** глубокий аудит фактического кода, проверка трёх приватных источников на уровне индексов/выбранных оригинальных функций, новые проектные документы с воспроизводимыми требованиями, проверкой обратной совместимости и ссылками на научные/официальные источники. **Не сделано:** изменение production-алгоритма `envelope_fault_lines`, независимый matcher, боковые, единый Quality Gate, паспорт NPZ и автоматический поиск дефектов; физический МВК01 не тестировался. **Нельзя обещать готовность по одному GitHub CI.**

Дополнительные ресурсы: [SciPy find_peaks](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html), [MathWorks bearingFaultBands](https://www.mathworks.com/help/predmaint/ref/bearingfaultbands.html), [ISO 13373-1](https://www.iso.org/standard/21831.html), [ISO 20816-3:2026](https://www.iso.org/standard/89922.html) (**не стандарт автоматического диагноза подшипника**), [CWRU](https://engineering.case.edu/bearingdatacenter/download-data-file), [Paderborn KAt](https://mb.uni-paderborn.de/kat/forschung/bearing-datacenter/data-sets-and-download), [Infogram](https://doi.org/10.1016/j.ymssp.2015.04.034), [Gini filtration](https://www.sciencedirect.com/science/article/pii/S0019057820300197).

**Стартовая команда для нового чата:** «Продолжай ветку MVK Live; прочитай эту передачу и `FIVE_GAPS_AND_DIAGNOSTIC_RESEARCH_PLAN_RU.md`, проверь актуальный код/Actions и реализуй пакет D1 целиком с тестами и без изменений оригинального RX/FRange/AUX4700; используй три приватных источника совместно, когда затрагивается оригинальная логика».
