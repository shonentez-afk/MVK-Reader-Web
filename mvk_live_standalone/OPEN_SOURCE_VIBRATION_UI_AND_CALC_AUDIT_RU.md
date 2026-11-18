# MVK Live — аудит интерфейсов и расчётов OpenTest / c-spectrum / других проектов

**Исследование:** 18.11.2026. **Тип изменения:** только аналитическая документация; рабочие Python/Qt, Go, протокол и DSP не изменены. Дополнение к [WORKSPACE_V2_OPTIMAL_MAIN_AND_ANALYSIS_RU.md](WORKSPACE_V2_OPTIMAL_MAIN_AND_ANALYSIS_RU.md).

**Граница задачи:** не реализовывать карточки агрегатов, подшипников и редукторов, дерево оборудования, маршруты, мастер создания машин и связанные модели БД. Расчёт BPFO/BPFI/BSF/FTF или GMF может требовать ввод 1× и геометрии *на странице конкретного анализа* без карточки.

## I. Исходники OpenTest (проверены вручную)

Репозитории:
- https://github.com/crysound/OpenTest — GUI, хранение конфигураций и платформенные интерфейсы.
- https://github.com/crysound/OpenTest-Plugins — отдельный *публичный исходный код* FFT-плагина с UI и Java-конвейером. Нельзя ошибочно считать весь набор коммерческих/официальных модулей OpenTest доступным в исходниках: Octave, Vibration Analysis и пр. представлены в README как official package; наличие их скриншотов не равно наличию полного исходного DSP.

**Реализация рабочих графиков:**
- `apps/frontend/src/modules/monitor/components/monitor-graphic-grid-viewer.vue`: динамическая сетка карточек, интерактивное выделение графика, добавление панели и расчёт размера сетки.
- `apps/frontend/src/modules/monitor/components/monitor-graphic-view-panel.vue`: единый компонент рендеринга, устойчивые идентификаторы кривых, события выбора/настроек/экспорта.
- `apps/frontend/src/modules/monitor/hooks/use-monitor-dashboard-config.ts`: конфигурация панели отдельно от потока данных; чтение/нормализация/сохранение и слежение за изменениями.
- `apps/frontend/src/modules/monitor/hooks/use-monitor-graphics.ts`: управление runtime-графиками, целевые обновления, идентификаторы каналов и обработка смены настроек.
- `apps/frontend/src/modules/shared/data-graph/components/views/waterfall-view.vue`: отдельные ветви realtime `appendRealtimeFrame` и исторической загрузки `setHistoryFrames`, вычисление шага кадра по Fs/FFT/overlap; это полезнее, чем рисовать заново при каждом repaint.
- `apps/frontend/src/modules/shared/data-graph/components/chart-tools/cursor-view/index.vue`, `cursor-settings-dialog.vue`: курсоры с X/Y, A/B, delta в полосе, несколько каналов, маркеры, гармоники/боковые полосы; раздельные настройки инструментов графика.

**Настройка измерений и фильтров:**
- `apps/frontend/src/modules/test/index.vue`: раздел `Setup / Measure / Monitor` с вложенными `Splitter`; модульные настройки и просмотр данных — разные панели.
- `apps/frontend/src/modules/test/components/channel-level-filtering.vue`: опциональная фильтрация по каналам, отдельный таб каждого канала, окно FFT по каналу, проектные настройки можно разнести по АЦП.
- `apps/frontend/src/modules/shared/dashboard/digital-filter-config/index.vue` + `model.ts`: только доступные поля в зависимости от типа фильтра. Семейства NONE, HP, LP, BP, BS; допустимые типы/порядки по режиму, отдельные частоты/порядок/ripple/взвешивание, валидация и нормализация.
- `apps/frontend/src/modules/shared/data-graph/components/views/graph-config-dialog.vue`: настраиваются тип графика/источники, оси, единицы, сетка/отображение, ограничения; отдельно решается, требует ли изменение перезапуска расчёта.
- `plugins/fft-tools/frontend/src/contributions/measure/fft-measure/setting.vue`: collapsible группы Acquisition / Measurement Control / Signal Analysis / Averaging / Advanced; выбор каналов, окон FFT, анализ BASEBAND/ZOOM, разрешение как N линий / df / длительность блока, реальная Fs→df/длительность на экране, overlap, POWER/RMS/EXP averaging, тайм-константа, amplitude PEAK/RMS, cross spectrum/ref channel.
- `plugins/fft-tools/frontend/src/contributions/measure/fft-measure/fft-options.ts`, `resolution-metrics.ts`, `model.ts`: обоснованные предустановки и вычисляемые зависимости параметров без ручного угадывания N и df. Например `df=Fs/N`, `T=N/Fs`; недоступные режимы скрыты/не выбираются.
- `plugins/fft-tools/frontend/src/shared/config.ts`: валидация конфигурации и типизированные значения — полезный контракт перед расчётом.

**Backend FFT-плагина — что реально видно в исходниках:**
- `plugins/fft-tools/backend/src/main/java/com/opentest/plugins/fft/measurement/FftParameters.java`: типизированный DTO алгоритма, окна, overlap, усреднения, каналов, настроек фильтра.
- `.../FftFilterValidation.java`, `.../FftStartupValidation.java`: канальные частоты/Nyquist, валидация выбранного режима и достаточного N до старта.
- `plugins/fft-tools/backend/src/main/java/com/opentest/plugins/fft/spectrum/FftSelfSpectrumPipeline.java`: разветвление `acquired waveform -> channel filter -> filtered waveform + FFT -> display/persistence`. Оригинальный сигнал и обработанные результаты имеют разные типы выходов.
- `.../FftSpectrumProcessor.java`: FFT, ASD, PSD и спектрограмма/неусреднённый кадр. Фактические FFT-функции вызывают `AlgorithmService` платформы; не весь низкоуровневый код алгоритмов находится в плагине.
- `.../FftSpectrumAccumulator.java`: политики averaging, включая exponential.
- `.../measurement/FftVibrationIntegration.java`: отдельный расчёт ВС/ВП интегрированием с переносом состояния между фрагментами и удалением DC. Это **другой подход**, чем частотная интеграция MVK Live: нельзя переносить коэффициенты или трактовать физические результаты как идентичные без проверки дрейфа/полосы/фазы.
- `.../transfer/FftTransferProcessor.java`: auto/cross spectra, H1/H2 FRF/phase для двух каналов. Данный класс **не означает**, что МВК01 предоставляет синхронную фазу, необходимые возбуждение, когерентность и тахометр; НЕ включать такую функцию в наш план без подтверждения исходных данных.
- `apps/frontend/src/modules/result-limit/panel.vue`: редактор порогов и правил с валидацией. Для MVK Live сначала нужен обоснованный источник порога; цветовая тревога по произвольному лимиту недопустима.

**Главный UX-вывод:** из OpenTest брать не всю сложную плагинную платформу, а **сетки 1/2/4, настройку выбранного графика, независимые конфиги по каналам, явные `Apply`/валидацию и живые зависимые подсказки N/df/T/Fs**. Историю и результаты нашего SQLite/NPZ сохранять как есть.

**Лицензия:** [OpenTest Community License 1.0](https://github.com/crysound/OpenTest/blob/main/LICENSE.md) применяется и к [OpenTest-Plugins](https://github.com/crysound/OpenTest-Plugins/blob/main/LICENSE.md); это **не MIT/GPL**. Исходники используются в исследовании как документированные примеры; не копировать код/UI-ассеты в MVK без отдельного анализа условий.

## II. Исходники c-spectrum (проверены вручную)

Репозиторий: https://github.com/arkid-lutaj/c-spectrum

**Облик:** `src/cs_gui.c` рисует верхние пять видов (spectrum, waveform, waterfall, envelope, chart), постоянную левую панель с состоянием/показателями/причиной события и компактные клавиши. Один активный большой график + всегда видимые значения. Логарифмический спектр и линейный спектр огибающей используют разную ось X. Временной сигнал использует **min/max на пиксель**, чтобы не терять короткие импульсы. Водопад показывает историю по времени; EWMA-chart — реальное состояние каждого из шести индикаторов и диапазон допустимого изменения. Сохранённые эталонные screenshot-файлы: `docs/assets/1-spectrum.png`, `2-waveform.png`, `3-waterfall.png`, `4-envelope.png`, `5-chart.png`.

**Критически важно:** c-spectrum *не* содержит полноценной пользовательской панели настройки FFT/фильтра/threshold в GUI. Клавиши `1..5/TAB` переключают виды, `F` переключает HP, `R` запускает повторное обучение baseline, `Space` включает паузу. Детальные параметры задаются **CLI** в `src/main.c`: `--fft`, `--hop`, `--window`, `--hp`, `--env-band`, `--baseline`, `--sigma`, `--lambda`, `--consecutive`, `--adapt`, `--rpm`. В MVK Live GUI-настройки следует взять из OpenTest, а не копировать этот недостаток.

**Алгоритмы:**
- `src/cs_analysis.c`: скользящее FFT-окно, сдвиг `hop`, Hann/Hamming/Blackman-Harris/FlatTop, нормировка спектра по coherent gain, фильтрация **до** FFT. Сигнал обрабатывается один раз общим ядром, GUI не делает второе FFT при отрисовке.
- `src/cs_features.c`: RMS в дБ (после удаления среднего), crest, Pearson kurtosis, spectral centroid, spectral flatness, high frequency energy ratio. Только последние три стоит предварительно предложить в MVK Live как *новые APP_DERIVED* показатели. Все зависят от полосы, Fs, окна и базовой шкалы; нужно хранить метаданные.
- **Численная находка:** комментарий в `cs_features.c` называет `ari` арифметическим средним спектральной амплитуды, но реализация `sqrt(total/log_n)` — это **квадратическое** среднее амплитуды. Поэтому метрика `flatness` отличается от общепринятого `geometric_mean(PSD)/arithmetic_mean(PSD)`. **Не копировать формулу как стандарт без проверки.** В MVK потребуется собственная корректная реализация, документация определения и тесты.
- `src/cs_features.c` `cs_band_edges`: отображаемые полосы называются `octave-ish`, логарифмически делятся от 20 Гц до Nyquist. Они **не IEC 61260 1/3-октавный OEM фильтробанк** и не должны заменять МВК01 AUX4700 43 полосы.
- `src/cs_monitor.c`: исходное `LEARNING` + Welford mean/variance → z-score → ограничение одиночных выбросов → EWMA → меняющиеся по времени границы `L*sqrt(lambda/(2-lambda)*(1-(1-lambda)^(2*i)))` → consecutive/hysteresis/dwell → `WARNING/ALARM`. Подстройка baseline запрещена во время предупреждений/тревоги. Порог без устойчивого baseline не информативен.
- `src/cs_envelope.c`: резонансная BP, rectification + LPF/decimation → FFT огибающей → prominence vs median background, несколько гармоник в окрестности BPFO/BPFI/BSF/FTF/1×; без исходных RPM/геометрии — нет локализации дефекта. **Это не Hilbert-огибающая**, используемая в некоторых режимах MVK Live: методы могут давать разные нормировки и амплитуды. Показывать `method` и частотную полосу.
- `src/cs_config.c`: настройки/валидация Nyquist, Fs, FFT N, hop, envelope band; исходный пример имеет `highpass=20 Hz`, `envelope=2–6 kHz`, `baseline=10 s`, `lambda=0.2`, `sigma=4`, `consecutive=3`. Это **демонстрационные начальные значения микрофонного анализатора**, а не нормы/пороги для МВК01.
- `src/cs_engine.c`: ядро/история не зависят от вкладки. `src/cs_report.c`: JSON/CSV с параметрами, baseline, событиями и спектром. `src/cs_synth.c` и `tests/test_*.c` дают повторяемые синтетические сценарии для регрессии, но не физическую валидацию на реальном оборудовании.

**Не переносить:** автоматическую подстановку симулятора вместо отсутствующего физического микрофона (`cs_gui.c`); МВК должен честно показывать `NO_DEVICE / CONNECTING / NO_DATA`, а не синтетическое состояние. Не переносить готовые пороги/диагнозы с акустического микрофона на акселерометр. Не смешивать сигнал разных АЦП или разные Fs/фильтры в одном baseline.

**Лицензия:** MIT, https://github.com/arkid-lutaj/c-spectrum/blob/main/LICENSE — идеи/реализации допустимо заимствовать с сохранением уведомлений при фактическом копировании кода; здесь исходники не копировались.

## III. Ещё четыре исходника — по узким полезным возможностям

1. **[pySPWB](https://github.com/Charette-AI-Group/pySPWB), MIT, PySide6.** `src/spwb/gui/fft_analysis.py`: слева список каналов, справа FFT и вкладки `Spectral Analysis / Energy Band`, отдельные `df`, overlap, window, weighting, таблица RMS/мощности в выделенной полосе. `src/spwb/gui/tfa_analysis.py`: STFT с двумя связанными срезами `Time Section (spectrum at cursor)` и `Frequency Section (level over time)`. `src/spwb/processing/dsp/timefreq.py`: чистые методы `time_section`, `frequency_section`; `src/spwb/gui/settings.py`: `QSettings` для геометрии окна, ширины таблиц, `QSplitter.saveState()`. Это ближайший к MVK Qt-образец, **но** разные определения спектральной мощности/окна нельзя переносить без тестов.
2. **[AccelSpectra](https://github.com/electromake/AccelSpectra), GPLv3.** `src/ui/MainWindow.cpp`: четко разделены аппаратные группы и FFT-настройки; три включаемых канала X/Y/Z, N, окно, hop; один QChart. `src/dsp/FFTPipeline.cpp`: FFTW r2c ядро. Для MVK полезны небольшие единообразные панели, не копирование GPL кода.
3. **[REI SignalLab](https://github.com/rootcastleco/rei-signallab), MIT.** `frontend/src/components/ControlPanel.jsx`: простые `Signal/Filter` переключатели, фильтр LP/HP/BP/BS, Butterworth/Chebyshev/FIR. `VibrationWorkbench.jsx`: FFT, огибающая, bearing 1×, order/balance, но компонент очень крупный, смешивает симуляторы с анализом. Не использовать как промышленную верификацию и не переносить карточки машин.
4. **[JYD-iBearing](https://github.com/kipp7/JYD-iBearing), MIT.** `Web/app/spectrum-analysis/SpectrumUpload.tsx`: отдельные FFT/envelope/STFT/VMD/CWT после загрузки; `Web/app/wave-analysis/TimeDomainUpload.tsx`: waveform/RMS/moving mean/moving std с выбором окна; `backend/preprocessing.py` — скользящий RMS и статистика. Важное: видны вкладки анализа, но лабораторное моделирование и ML не следует выдавать за аппаратно доказанную диагностику.

## IV. Выбранная архитектура MVK Live v2

**Основной экран = OpenTest + постоянная диагностическая панель c-spectrum.**

```
┌ MVK Live | IP МВК01 | Ethernet/TCP статус | [ИЗМЕРИТЬ] [СТОП] [FREEZE] ┐
├ Измерение: Обзор / Спектр / Время / Расчёты | История | Доп. анализ ┤
│ АЦП: [1][2][3][4][5][6][7][8]  {серые пока нет свежих отсчётов}       │
├ Диагностика ┬────────── РАБОЧАЯ СЕТКА 1/2/4 ───────────┬ Настройки ────┤
│ ВУ RMS      │ FFT ВУ/ВС/ВП с курсорами                  │ Метод         │
│ ВС RMS*     ├───────────────────────────────────────────┤ FFT N / df     │
│ Crest       │ Временной сигнал (личный фильтр)          │ Усреднение    │
│ Kurtosis    │                                           │ Фильтр/полоса │
│ Centroid*   │ {по выбору: waterfall/STFT/огибающая}     │ Ось/единица   │
│ Flatness*   │                                           │ [Подробнее ▸] │
│ HF ratio*   │                                           │               │
├─────────────┴───────────────────────────────────────────┴───────────────┤
│ Сеанс · АЦП · Fs · N · FRange применён Native · RxPos · архив · ошибка │
└────────────────────────────────────────────────────────────────────────┘
* Только при достаточных данных/действительном диапазоне. Не рисовать нуль.
```

Постоянные компактные индикаторы показывают **только фактически измеренные** или явно помеченные локальные величины; `STATUS` не превращать в диагноз без пригодного baseline. Страница «Обзор» по умолчанию даёт спектр+waveform; по клику график разворачивается. Раскладки 1/2/4 на базе `QSplitter` с сохранением `QSettings`. Запомненный UI — не подтверждение подключения.

**Графики и необходимые настройки** (каждый имеет собственную видимую панель + «Дополнительно»):

| Вид | Основные настройки | Главное графическое представление |
| --- | --- | --- |
| FFT спектр | ВУ/ВС/ВП, лин./дБ, FFT N/df, окно, усреднение, фильтр + готовая полоса, X/Y | Крупный спектр с A/B и Δf, таблицей пиков и гармоник |
| Осциллограмма | X-время, ±Y, отдельный фильтр, курсор/выделенный участок, Freeze | Кривая с min/max decimation только для экрана; статистика — из полного окна |
| Прибор AUX4700 43 | ORIGINAL 1/3, выбранный АЦП, позиция/частота | 43 полосы + таблица и переход в историю; APP_DERIVED RSS 1/1 отдельно |
| Прибор AUX4700 24×3 | Номер регистра, RMS/Peak/Span (исходные единицы пока не подтверждены) | Столбцы/таблица **по номеру позиции**, не по придуманной частоте |
| Локальные расчёты | Группа (ВУ/ВС/ВП, импульсность, спектральные), окно, физическая полоса | Таблица `показатель/значение/единица/параметры/источник/время/тренд` |
| Водопад | Реальные кадры, частотный диапазон, динамический диапазон цвета | Частота×время + легенда в правильной шкале |
| STFT | FFT block, overlap, окно, шкала, цветовой диапазон | Спектрограмма + спектр в выбранный момент + тренд выбранной частоты (pySPWB) |
| CWT | Масштабы, min/max частота, окно, цвет | Время–псевдочастота, не эталонный FFT |
| Кепстр | Окно, предел кэфренции | Кэфренция–амплитуда с физическими курсорами |
| Огибающая/подшипники | Фильтр/полоса, метод демодуляции, FFT N, 1×/геометрия вручную | Спектр + предполагаемые BPFO/BPFI/BSF/FTF + табличная оценка гармоник; не диагноз |
| Редукторы | 1×/зубья вручную, гармоники | FFT + ожидаемые GMF/sidebands, не выдуманные пики |
| Тренд истории | АЦП, исходный показатель, UTC/местное время, период | Дата–значение, выбрать точку → источник, затем сравнение |
| Сравнение | Однородный источник/физическая величина, даты до 8, N/ось | Overlay 2–8 или связанные отдельные панели, цвета дат и реальные Fs/Nyquist |
| Контроль изменений (ПОЗЖЕ, факультативно) | stable baseline того же АЦП/Fs/фильтра/показателя, sigma/λ/consecutive | EWMA линия и пределы, «обнаружено изменение признака», не диагноз |

**Контекстные настройки (из OpenTest):** частоты и N выбираются через готовые списки с подсказкой `Fs`, `Nyquist`, `df`, длительностью и реальной полосой. При «Без фильтра» не показывать пустые пороги. Октавные OEM-имена МВК01 (32 пункта) отдельно от локального альтернативного DSP и стандартизованных CPB. Изменения только вида/оси не пересчитывают сигнал; изменение фильтра/окна/N вызывает новый **локальный** расчёт, не повторный приборный сбор. При отсутствии данных — объяснение причины.

**Обязательная связанная модель:** `session_id, adc, source (original_aux/local_npz), UTC, Fs, FRange_state, quantity, units, filter_method, filter_band, nfft, window, averaging, valid_sample_count, provenance`. Дополнительные методы принимают калиброванные *один раз* Native Go отсчёты, не вмешиваются в TCP/10230 и не делят неподходящие временные/частотные оси.

## V. Приоритеты и критерии приёмки

1. **P0 UX:** двухграфический Live-обзор + постоянные 4–6 показателей слева + контекстная панель настроек; статусы реального устройства без синтетической подмены. Под Windows 1280×720, 1920×1080, 100%/150%.
2. **P1 настройка:** разделить device/acquisition, calculation/DSP, display, history; FFT/окно/overlap/усреднение с `df/T/Nyquist`, фильтры по выбранному АЦП, локальная/приборная provenance. Тесты отказов при недостаточном N/Fs/режиме.
3. **P2 диагностика:** новые centroid, spectral flatness (математически исправить в сравнении с c-spectrum), HF ratio + тренды и физические единицы; график огибающей с гармониками/локальным уровнем шума. Никаких автоматических диагнозов.
4. **P3 анализ:** A/B, энергия выбранной полосы, связанные STFT срезы и сохранение layout/параметров через `QSettings`.
5. **P4 статистический контроль (пока проектный):** только после тестов на реальных данных МВК01 и подтверждённой стабильной измерительной полосе — факультативный baseline/EWMA. Не показывать предупреждения/автоматику без исследования ложных срабатываний.

Критерии: отсутствие изменения собственного аппаратного RX/FRange; отсутствие мнимых данных при disconnect, Freeze, смене АЦП; графики без смешения других единиц/каналов; сравнения только совместимых исходных величин; отдельные контрольные тесты для 43+24×3 ORIGINAL; тесты корректной математической flatness на тоне, широкополосном шуме и тишине; unit-тесты DSP на реальных Fs; ручная проверка интерфейса и устройства МВК01.

## VI. Указатели на реальные демонстрационные экраны

- OpenTest общий экран: https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/opentest-main-window.webp
- OpenTest FFT: https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/module-fft.png
- OpenTest 1/n octave: https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/module-octave.png
- c-spectrum (5 настоящих screenshot-кадров): https://github.com/arkid-lutaj/c-spectrum/tree/main/docs/assets
- pySPWB FFT: https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/fft_harmonics.png
- pySPWB TFA: https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/tfa_log_sweep.png

## Итог

У OpenTest заимствовать идеи **организации рабочего пространства и контекстных настроек расчёта**, у c-spectrum — **связанную панель признаков + наглядную огибающую + статистическую оценку изменения**, у pySPWB — **интерактивные срезы STFT и энергию полосы**, у AccelSpectra — **простую компактную настройку FFT**. Код чужих проектов не копировался. Действующую ветку этой документационной задачей не менять функционально.
