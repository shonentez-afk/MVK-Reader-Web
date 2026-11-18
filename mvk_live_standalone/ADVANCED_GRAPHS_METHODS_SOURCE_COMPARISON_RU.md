# MVK Live — другие графики, методы и исходники настроек (аудит)

**18 ноября 2026.** Аудит исходников независимых проектов. Не меняет оригинальный MVK01 Native Go, FRange или AUX4700. Карточки агрегатов, подшипников и редукторов **не делать**.

## 1. Что уже есть в ветке MVK Live

Проверено по реальным `app.py`, `advanced.py`, `pipeline.py`, `kurtogram.py`, `measurement_history.py`, а не по макетам:

| График | Текущий статус | Главное ограничение |
|---|---|---|
| Временной сигнал ВУ | Есть: независимый фильтр, длительность, ±Y | Временной отрезок и курсоры A/B ещё улучшить |
| FFT ВУ/ВС/ВП, Welch PSD/ASD | Есть | Δf/N, window/averaging/peak table требуют более ясного инспектора |
| Оригинальные AUX4700 43 третьоктавы, 24×RMS/peak/span | Есть | Не смешивать c локальным спектром |
| Спектр огибающей Hilbert | Есть | Не путать с экстракцией комплексной огибающей PySDKit |
| **Fast Kurtogram** | **Добавлена** карта по точному бинарно-троичному численному алгоритму PySDKit (MIT), выбор центра/полосы; интеграция с Hilbert-огибающей | Нужна приёмка GUI/Windows, промышленная корректность по реальному MVK01 ещё не подтверждена |
| Водопад (реальные RxPos) | Есть | Пока строки по номерам, а не по реальному времени, нет полного архивного replay |
| STFT/CWT/кепстр | Есть отдельными страницами | STFT не имеет связанного спектра в точке и тренда частоты |
| Тренд RMS, архивные тренды, наложение сохранённых дат | Есть | Удобное масштабирование, курсоры, единая модель выбранной записи |
| Подшипниковые частоты BPFO/BPFI/BSF/FTF, GMF | Есть локальная начальная проверка/метки | Совпадение одной гармоники не является диагнозом |

## 2. Профессионально полезные новые графики — проверенные открытые исходники

| График / метод | В каком проекте / файл | Фактические настройки | Для MVK Live |
| --- | --- | --- | --- |
| **FFT + энергия выделенной полосы** | [pySPWB](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/fft_analysis.py), [DSP](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/spectral.py) | FFT N/Δf, оконная функция, перекрытие, усреднение, курсоры полосы, таблица уровня/энергии | **P1**: нужно; с явной единицей RMS и без суммирования амплитуд как мощностей |
| **Спектрограмма + спектр по курсору времени + тренд частоты** | [pySPWB GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tfa_analysis.py), [timefreq.py](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/timefreq.py) | block N, overlap 0–95%, window, выбор канала, color dB, время и частота курсора | **P1**: 3 связанных вида из одного АЦП, можно использовать существующий STFT |
| **A/B курсоры, Δf, гармоники и боковые полосы** | [OpenTest](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/chart-tools/cursor-view/cursor-settings-dialog.vue) | курсоры, количество гармоник, выбор линий/канала, X/Y, подсказки | **P1**: улучшить основной FFT, без нового DSP |
| **Два связанных вида водопада** | [OpenTest waterfall-view.vue](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/views/waterfall-view.vue), [c-spectrum GUI](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_gui.c) | Fs/N, новый RxPos, overlap, history, color scale, real vs historical | **P1**: физическое время и spectrum-at-time; no arbitrary timestamp |
| **Кюртограмма / эксцесс SK по центру и ширине** | [PySDKit Fast Kurtogram](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py), [тесты](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/tests/test_kurtogram.py) | 1 ADC, Fs, 2..6 уровней, 4096..32768 отсчётов, выбор клетки и границ по Nyquist | **УЖЕ ДОБАВЛЕНО** ядро + карта; адаптер требует точные физические Fs и калиброванные Native отсчёты |
| **Спектр квадрата огибающей (SES) и packet envelope PySDKit** | [find_wav_kurt](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py) | выбранная клетка PySDKit, разложение, правильная эффективная Fs после децимации, локальный фон, дБ | **P2**: перспективен как дополнительный выбор против Hilbert, нельзя молча считать его одинаково нормированным в м/с² |
| **Сдвиг частоты/центроид/спектральная плоскостность/HF ratio** | [c-spectrum features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c) | Fs, FFT, полоса; определение мощности, окно, valid samples; отдельные тренды | **P2**: диагностика изменений с `APP_DERIVED`, *исправить формулу spectral flatness* до стандартного `geometric mean(PSD)/arithmetic mean(PSD)` |
| **Контрольные карты EWMA** | [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c) | обучающая история, lambda, sigma, порог подряд срабатываний, dwell, состояние baseline | **P2/P3**: только для устойчивой сопоставимой истории, НЕ автоматический диагноз |
| **Огибающая с гармониками BPFO/BPFI/FTF/BSF** | [c-spectrum](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c), [CWRU пример](https://github.com/akshatverma1602/Signal-Processing-on-CWRU-Bearing-Dataset/blob/main/envelope.py) | полоса демодуляции, RPM, геометрия вручную, число гармоник, tolerance, local SNR | **P2**: несколько независимых подтверждений на графике и таблица доказательств |
| **Частотная карта Кэмпбелла / карта порядков / slice 1×,2×** | [rota-order maps](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/maps.py), [slices](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/slices.py), [plot/_maps.py](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/plot/_maps.py) | физическая серия RPM(t), окно/шаг, режим RPM или time, binning по rpm, порядок, df, гармоники | **P3, условно**: только когда появится надёжная серия RPM(t) за набор окон; нет TACH и доказанной межкадровой угловой привязки. Не копировать GPL-3 код в текущий MIT-пакет |
| **Циклическая спектральная когерентность (cyclic spectral coherence)** | [cyclo](https://github.com/TreyShenk/cyclo/blob/main/src/cyclo/analysis.py) | диапазон циклических частот α, FFT Ndft, блоки усреднения, общий Fs, mode; карта `α × f` | **P3/R&D**: может видеть модуляцию подшипников, но вычислительно дорого и требует долгой достоверной записи и валидации. Лицензия отдельно проверяется |
| **Synchrosqueezing SST (концентрированная T–F карта)** | [PySDKit sst.py](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/_tfa/sst.py) | Morlet/bump, число голосов, диапазон, threshold; мгновенная частота/режимы | **P3/R&D**: исследовательская альтернатива STFT при переходных режимах, без автоматической замены проверенного STFT |
| **IMCKD (максимизация коррелированного куртозиса)** | [PySDKit _imckd.py](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/deconvolution/_imckd.py) | период повторения дефекта, длина FIR, число итераций, shift order, контроль `ck_iter`/устойчивости | **P4/R&D**: перспективно для слабых импульсов, но на неверном периоде создаёт ложные признаки |
| **Частотный отклик FRF H1/H2, фаза/когерентность** | [pySPWB transfer.py](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/transfer.py), [tf_analysis.py](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tf_analysis.py) | reference/response канал, N/overlap/window, average *complex spectra before division*, H1/H2, phase unwrap, coherence | **ОТЛОЖИТЬ**: нужны подтвердённая синхронность/фазовая цепочка нескольких АЦП и опорное возбуждение; не следует придумывать эти данные |
| **Адаптивная LMS-фильтрация и график сходимости** | [pySPWB adaptive.py](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/adaptive.py), [lms_analysis.py](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/lms_analysis.py) | reference/noisy, filter length/taps, step-size, leakage, correlation/cleaned output | **ОТЛОЖИТЬ**: нужен доказанный коррелированный reference; фильтр может удалить сам дефект |
| **Орбита X–Y / Bode / Nyquist** | аналоги в промышленном rotor-dynamics софте, открытого подтверждённого кода для нашей цепочки нет | два одновременно измеренных ортогональных датчика с физическим пространственным смыслом, фаза, RPM | **ОТЛОЖИТЬ** до проверки hardware и монтажа датчиков |

## 3. UI-компоновка по OpenTest + c-spectrum + pySPWB

**Рабочее пространство:**
- вверху IP/единственная сессия Go/кнопка «Измерить»;
- слева 8 АЦП и компактная диагностическая панель (не оценка «зелёный = исправен»);
- в центре раскладка графиков 1/2/4 с независимыми инспекторами (FFT/waveform/kurtogram/waterfall/STFT);
- справа **только параметры активного метода**, по форме из [OpenTest FFT setting.vue](https://github.com/crysound/OpenTest-Plugins/blob/main/plugins/fft-tools/frontend/src/contributions/measure/fft-measure/setting.vue);
- архив и live различаются по time provenance, данные NPZ/AUX4700 не «синтетизируются» из соседних значений;
- детальный анализ открывает выбранное окно/частоту без потери контекста.

**Рекомендуемые настройки каждой вкладки:**
- FFT: quantity, RMS/peak convention, window, FFT N, `Fs/N`, averaging method/count, overlap, filter/preset, dB reference, X/Y, A/B;
- STFT: frame N, overlap, time window and color limits + два связанных среза;
- Waterfall: live/archive, 20–240 кадров/период UTC, unit/method (no mixed PSD vs FFT), frequency range, amplitude color scale, row/time selection;
- Kurtogram: nlevel 2–6 within `nlevel <= log2(N)-7`; window N real, output (frequency, level, excess SK) + grid cell → valid band → Hilbert; no «применить FRange повторно»;
- Envelope: выбранный resonance band, method (Hilbert / future PySDKit packet), peak harmonic tolerance, RPM source, evidence table;
- Diagnostics: source data, numeric measured peaks, counts, baseline evidence, limitations, an `Open graph` action. No arbitrary probability and no automatic «исправен».

## 4. Приоритет без раздувания проекта

**Уже реализовано в коде на этой ветке:** полноразмерная PySDKit Fast Kurtogram карта с интерактивным выбором и передачей полосы, численные проверки и лицензия. CI Windows/Qt проверять по GitHub Actions; до завершения тестирования не объявлять физическую приёмку.

**Следующий пакет, максимально полезный:** связанный STFT → spectrum-at-time/level-at-frequency, A/B курсоры и band RMS на FFT, улучшение настоящего времени и шкалы цвета водопада, квадрат огибающей PySDKit как *отдельный* метод.

**После него:** centroid/flatness/HF ratio и контрольный анализ трендов. Campbell и cyclic coherence — отдельно только после проверки входных данных и производительности.

**Не включать сейчас:** карты машин и редукторов, вывод «вероятность 88% дефект» из жёстких порогов, нейросети, FRF/орбиты на неподтверждённой синхронизации, автоматическую отправку настроек измерений обратно на МВК01.

## 5. Условия честности результатов

- Исходные 8 АЦП × FRange масштабированы единожды в Native Go, новые DSP-методы используют подтверждённые real Float32.
- Заводской AUX4700: 43 третьоктавы и 24×3 позиции оригинала остаются **ORIGINAL**, все графики PySDKit `APP_DERIVED`.
- Заимствованные идеи проверяются по лицензиям; наш PySDKit пакет — MIT с сохранённым уведомлением; `rota-order` GPL-3, поэтому **не копировать** его исходники в проект без отдельного решения о лицензировании.
- Ни цветовая карта кюртограммы, ни повышенный kurtosis, ни одна гармоника не являются доказательством механического дефекта.
- Для всех динамических графиков обязательно показывать истинные Fs, physical units, FFT N, Nyquist, window, source, time/session и ограничения.
