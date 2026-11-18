# MVK Live — актуальная проверка кода, реального UI и новые решения по FFT/огибающей

Дата исследования: 18.11.2026. Ветка: feature/mvk-live-standalone-20261117. Проверенный HEAD до фиксации этого документа: 58ce1907571e4c65a4ea23ea0c3e7dca2099c8cc.

**Статус:** аудит реально присутствующего кода + дополнение инженерного каталога первоисточниками. Никаких изменений Native Go, TCP/10230, FRange, AUX4700, обработки RAW, Qt-кода, NPZ или SQLite в этом исследовательском пакете нет. Сохранённые три приватных источника оригинального MVKView не публикуются.

## 1. Сверка документации с последним кодом — важно для нового чата

Ранее опубликованный START_NEW_CHAT_MVK_LIVE_DIAGNOSTICS_20261118_RU.md описывает интерфейс до реализации modern_shell.py. Следующие записи в старом handoff — **исторические**, а не актуальная картина: «нет QMenuBar», «в главном окне ещё шесть вкладок», «один видимый ADC только планируется», «нет отдельных окон методов». README_RU.md также содержит старое описание шести верхних вкладок. Проверять именно HEAD.

| Задача | Фактическая реализация HEAD | Ограничение |
|---|---|---|
| Главное окно | modern_shell.py::install_modern_shell вызывает компоновку из app.py, вкладки Обзор / Спектр / Временной сигнал / Расчётные данные | Проверка экрана с прибором не проведена |
| Верхнее меню | modern_shell.py::_build_menu: 8 разделов (Файл, Измерение, Анализ, Диагностика, Архив, Вид, Настройки, Справка), работающие команды/shortcuts | 163 команды в проектном CSV — не количество реализованных команд |
| Один видимый ADC | Основной win.adc; совместимые extra_adc и dsp_adc скрыты и синхронизированы | Отдельный выбор источников в архивном сравнении остаётся |
| IP | Профили Qt QSettings и отдельный диалог подключений, без постоянного IP на главной панели | Никаких новых сетевых команд/сканирования |
| Графики | Два крупных графика Обзора, независимые страницы Spectrum/Time, правая контекстная QDockWidget и dark/light/system | Цветовой контраст и DPI требуют реального Windows QA |
| Окна методов | modern_shell.py::open_advanced_window: waterfall, kurtogram, short_trend, STFT, CWT, cepstrum, bearing, gears; отдельно archive trends/comparison | Не путать эти окна с запланированными W01–W43 |
| Зафиксированный источник | _pin_method_source для STFT, CWT, кепстра и Fast Kurtogram; app.py:: _calculate_extra / _calculate_kurtogram уже потребляют pin | Bearing, gears, waterfall, оперативный тренд пока не обладают таким общим immutable AnalysisInput |
| История | recordings.py NPZ V1 + measurement_history.py SQLite + history_widgets.py trends/overlay | Нет полного MeasurementContext и Quality/Comparability Gate |
| Подшипники | Hilbert/FFT и теоретические BPFO/BPFI/BSF/FTF, частичный local SNR | Нет отдельной BDF, полного evidence peak catalogue, collision-safe matcher, итогового диагностического движка |
| Лог X и ручные оси | graph_policies.py::spectrum_x_limits вычисляет нижнюю физическую положительную частоту; preserve_manual_axis и тесты есть | Не считать прежнее замечание handoff о безусловном X=0/log-X и сбросе zoom актуальным без новой регрессии |

**Доказательство сборок и изображений:**
- GitHub Actions Linux/Qt/Go + screenshot: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44337271877 — PASS на HEAD 58ce190, артефакт MVK_Live_Modern_Main_UI_Review_NO_DEVICE, два изображения Dark/Light, 1600×900, NO DEVICE.
- GitHub Actions Windows Native IPC + EXE: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44337272001 — PASS на том же SHA, артефакт MVK_Live_Standalone_Windows_Experimental.
- Проверены test_qt_modern_graphs.py и test_qt_workspace_tabs.py: четыре вкладки, один видимый ADC, общее происхождение графиков, ручной zoom, логарифмическая физическая X, разделённые фильтры, отсутствие фактического TCP в smoke.
- PASS = статические/автоматические проверки, **не** подтверждение корректной диагностики реального MVK01, непрерывной записи или ISO-аттестации.

**Визуальный разбор настоящего NO DEVICE screenshot:**
- 4 KPI (ВУ СКЗ, ВС СКЗ, пиковая ВУ, crest), большой FFT и временной график, справа свойства FFT; один ADC; сверху «Измерить / Стоп / Freeze / Сохранить окно».
- Нет синтетической кривой: заголовки «ожидание реального АЦП», «нет отсчётов», статус «НЕТ ПРИЁМА».
- Потребуются изображения/скриншотные тесты 1280×720 и 1920×1080 при DPI 100%/150%, раскрытый inspector, длинные названия полей, floating windows, светлая тема и контраст.

## 2. Новые уточнения из первоисточников: как профессиональные FFT действительно настраиваются

### 2.1. DewesoftX: раздельные категории вместо одного «типа графика»

Официальная форма FFT разделяет спектральную величину, формат амплитуды, оконную функцию, разрешение, перекрытие, тип усреднения и интегрирование/дифференцирование. Варианты: Linear/Power/PSD/ASD/ESD; Peak/RMS/Peak-Peak; окна Rectangular/Hann/Hamming/Flat Top/Blackman и др.; усреднение без, блоковое и накопительное, тип Linear/Energy/Energy exponential/Maximum. **Это наличие опций Dewesoft, не наличие их у MVK.**

- https://manual.dewesoft.com/x/setupmodule/device-modules/math_OnDevice/frequency-domain-analysis/fft
- https://manual.dewesoft.com/x/setupmodule/modules/freqdomain/fftapplication

**Вывод для MVK:** не добавлять один комбинированный список вместо независимых параметров. На главной странице нужны только Kind (ВУ/ВС/ВП), Estimator (FFT/PSD/ASD), Y representation (linear/dB), X scale (linear/log), Fmax/Auto, local filter; в расширенном блоке N, T=N/Fs, Δf=Fs/N, окно, усреднение, сегменты и provenance. Пока доступны только реально реализованные режимы (FFT/Hann, Welch/Hann 50% overlap, ASD=sqrt PSD). Кнопки Flat-top/Max Hold должны быть помечены «план» и не создавать фиктивный результат.

### 2.2. OROS NVGate: явно отличать усреднение, overlap, спектральные линии и FFT zoom

В NVGate показаны отдельные вкладки Channel / Trigger / Average / FFT analysis / FFT zoom и отдельно заданные frequency span, number of lines, overlap, time/spectral/synchronous averaging, linear/exponential/peak-hold. Их «zoom FFT» — самостоятельный вид анализа, а не простое обрезание отображаемого X.

- https://wiki.oros.com/index.php?title=NVGate_FFT
- https://wiki.oros.com/index.php?title=FFT_Spectrum_Analyzer_Multipurpose

**Вывод:** у MVK изменение X max — только viewport, не изменение Fs или N и не «увеличение разрешения». Записывать actual Fs, real N, time duration, df отдельно; при отсутствии тахометра не открывать режимы synchronous/order как готовые.

### 2.3. SciPy Welch и принцип спектральных единиц

SciPy различает scaling=density (физическая величина в квадрате / Гц) и scaling=spectrum (в квадрате без /Гц); коэффициент связи включает эквивалентную шумовую полосу окна, и это не просто смена подписи. При Hann 50% overlap — обычный оправданный старт, но не универсальный запрет на другое overlap. MVK FFT line RMS и Welch PSD не совпадают по смыслу и не должны суммироваться одинаково.

- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html

**Нужный контракт:** в подсказке вида графика показывать:
- FFT: RMS амплитуда отдельной линии [м/с², мм/с, мкм]; coherent-gain calibration для чистой гармоники, не выдавать сумму квадратов Hann line RMS за общий broadband RMS.
- Welch PSD: [ед²/Гц], RMS полосы = sqrt(интеграл PSD df с учётом допустимых bins).
- ASD: [ед/√Гц]; для RMS полосы сначала интегрировать ASD².
- log dB: FFT и ASD — 20 log10(A/Aref), PSD — 10 log10(P/Pref), опору явно рядом с Y. Не применять повторно log Y к уже рассчитанным dB.

### 2.4. Обработка фильтра и графика

Реальный MVK использует SciPy zero-phase forward-backward filtering (sosfiltfilt) в локальных окнах. Отображаемая АЧХ должна описывать **двухпроходную** амплитудную характеристику |H|²; single-pass характеристику нельзя выдавать за итоговую. Нельзя считать данный некаузальный window-analysis фильтр неизменной промышленной потоковой causal DSP-цепью. Текущий graph_policies.py уже различает именно этот случай.

- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html

При log X нулевая и отрицательная частота недопустимы. У PyQtGraph setLogMode выполняется log10 по данным, x≤0 становятся NaN. Текущий positive first FFT bin вместо 0 соответствует правильному подходу; проверить ручные оси/курсор после смены линейная↔лог X.

- https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html

## 3. Уточнение подшипников — физические частоты не равны найденным дефектам

MathWorks bearingFaultBands имеет управляемые Harmonics, Sidebands, Width и Domain=frequency/order. Показанные допуски и боковые — инструмент выделения частотных областей; выбранный по умолчанию Width **не** является диагностической нормой для любого станка. Частоты подшипника рассчитываются из RPM и геометрии, а спектральное доказательство ищется отдельно.

- https://www.mathworks.com/help/predmaint/ref/bearingfaultbands.html
- https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html

SciPy find_peaks выдаёт локальные максимумы и опциональные prominence, width, plateau; NaN ухудшают результат. Поэтому independent peak catalogue обязан работать сначала по подтверждённому спектру, не от гипотезы BPFO/BPFI; затем делать matching и обозначать коллизии.

- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.peak_prominences.html

Нужно зафиксировать будущую модель D1:
1. Immutable AnalysisInput (ADC, Fs, реальные отсчёты, session, capture_end, provenance).
2. QualityGate без самовольной подмены NaN/нулей и без догадок о saturation из калиброванного float.
3. Измеренные пики (peak_id, f_measured, amplitude/unit, prominence, width, local noise).
4. Рассчитанные семейства BPFO/BPFI/BSF/BDF=2BSF/FTF; H1..H10; BPFI ± k·fr; BDF ± k·FTF; shaft harmonics / GMF по условиям.
5. Допуск как явная функция df, 1/T и неопределённостей RPM/геометрии, не копировать порог чужого проекта.
6. Один measured peak_id — одно доказательство: коллизии не удваиваются. Результат: NOT_EVALUATED / INSUFFICIENT / CANDIDATES / AMBIGUOUS, не «исправен» и не вероятность в процентах.
7. Hn / sidebands / local SNR / measured-vs-predicted в общей таблице и на том же графике; сохранение версии аналитического пресета.

Текущий advanced.py::envelope_fault_lines обходит ожидаемые полосы и находит максимум внутри них; noteworthy=True при хотя бы одном попадании >=6 dB. Это **не** independent peak detection, не многогармоническая доказательная диагностика.

## 4. Два дополнительных QA-пункта, обнаруженных при проверке кода

1. **Счётчик Welch-сегментов:** vibration.py::_welch_acceleration возвращает max(1, 2*floor(L/N)-1), хотя при 50% overlap SciPy может поместить ещё одну половинную позицию; например при L=1.5N реальное число Welch-блоков = 2, текущий счётчик = 1. Проверить и исправить только metadata count; PSD-вычисление SciPy само по себе не опровергнуто. Тест L = N, 1.5N, 2N, 2.5N, 3N и соответствие реально использованным окнам.
2. **Незавершённая source pin-политика:** immutable snapshot уже есть для Kurtogram/STFT/CWT/Cepstrum, но не унифицирован для подшипников/редукторов/архивных методов и W01–W43. До изменения набора окон нужно внедрить единый AnalysisInput/MeasurementContext, а не независимые копии source-полей с возможной потерей ADC/Fs/времени.

## 5. Куда продолжать собирать факты до следующего крупного этапа кода

| Приоритет | Недостающие данные/решение | Как подтвердить | Где показывать |
|---|---|---|---|
| P0 | Согласованный спектральный паспорт: unit, FFT/PSD/ASD, dB ref, Fs/N/T/df, real window, filters | SciPy + положительный тест 1 синус/белый шум/две гармоники | Inspector + заголовок и CSV |
| P0 | Independent bearing peaks и collision ledger | SciPy find_peaks + MathWorks labels + реальные тестовые NPZ и отрицательные примеры | Отдельное окно «Подшипники» |
| P0 | Признаки пригодности выборки и причин отказа | SHA/finite Fs/N/Nyquist/df/RPM/status/unknown; не гадать о приборном full scale | Панель качества + каждое аналитическое окно |
| P0 | Сопоставимость двух сохранённых измерений | point label, ADC, Hz/units/alg version, RPM/load, approximate acquisition UTC, method/band | Архив · Сравнение, Тренды |
| P1 | FFT averaging и amplitude format | DewesoftX/OROS, отдельные тесты Hann/flat-top, RMS vs peak, PSD normalization | Расширенные настройки спектра |
| P1 | Band cursors и интеграл PSD | SciPy Welch vs known RMS time series | W01 FFT и архивное сравнение |
| P1 | Шаблоны графиков: ручной zoom + log X + theme/DPI | Qt скриншоты 1280/1920 100/150%; устройства с реальным потоком отдельно | Обзор/Спектр/Time |
| P1 | Долговременные RAW и временная метка | Отделить receiver/acquisition/saved times; native flow не менять по догадке | Архив/Паспорт/Запись |
| P2 | Сравнение селекторов полос (Fast Kurtogram, Protrugram, Infogram, Gini) | Одинаковый immutable ADC и CPU/RAM, downstream harmonics, реальные отрицательные кейсы | W41–W43 только после реализации |

**Граница данных:** ORIGINAL AUX4700 — 43+24×3 исходных скаляров; APP_DERIVED NPZ — реальные временные отсчёты одного ADC. Из AUX4700 нельзя восстановить FFT огибающей, STFT или Fast Kurtogram. saved_utc в NPZ — время сохранения файла, не доказанный acquisition UTC. Отсутствие RPM/TACH/фазы/нагрузки не подменять нулём. Никакой автоматической тяжёлой обработки каждого LIVE кадра.

**Следующий крупный программный этап:** один пакет D1 (QualityGate + immutable source + measured peaks + BDF/sidebands/collisions + real overlays/table + negative tests + Windows QA). Потом D2 (MeasurementContext/compare/history), D3 (research band selectors), D4 (unified evidence). Не дробить на пустые UI-заглушки и не менять сетевой приём ради DSP.

## 6. Сопутствующие файлы

- [Исходные два аудита пользователя](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md), [полный каталог методов](FULL_VIBRATION_METHODS_REALTIME_RECORDINGS_SETTINGS_SCREENS_RU.md).
- [Каталог D01–D44](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md), [пять пробелов и приёмка](FIVE_GAPS_AND_DIAGNOSTIC_RESEARCH_PLAN_RU.md).
- [Графики и пресеты](MAIN_SCREEN_MODERN_UI_AND_GRAPH_SETTINGS_20261118_RU.md), [контракт JSON](MAIN_SCREEN_GRAPH_PRESETS_AND_STYLE_CONTRACT_V1_20261118_RU.json).
- [Матрица 126 позиций](UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.md), [текущий handoff](START_NEW_CHAT_MVK_LIVE_DIAGNOSTICS_20261118_RU.md).

**Заключение:** базовый современный UI уже существует; следующие исследования и развитие должны углублять физическую корректность, проверяемость диагностических признаков и сопоставимость сохранённых измерений, не умножая количество заявленных «готовых» методов.
