# MVK Live — полный каталог методов, экранов и настроек: LIVE / окно / архив

**Версия каталога:** 18.11.2026. **Ветка:** feature/mvk-live-standalone-20261117.  
**Назначение:** единая техническая спецификация реализации, навигации, экранов и режимов расчёта для MVK Live. **Это каталог и проект UX, а не утверждение, что всё перечисленное уже реализовано.** В данном изменении программный код и приёмник не меняются.

**Зафиксированное исключение:** карточки агрегатов, подшипников и редукторов, дерево оборудования и связанные таблицы базы данных сейчас **не создавать**. Параметры RPM, числа зубьев, геометрии подшипника пользователь вводит прямо в соответствующем анализе, без создания карточки.

## 0. Четыре категории доступности, два разных формата архива

**LIVE** — непрерывный результат по новым физически подтверждённым блокам Go/IPC и оригинальным AUX4700. Приём не запускается повторно при открытии графика; GUI не применяет FRange повторно. Данные, не полученные с прибора, нельзя рисовать нулями.

**ОКНО** — дорогой или интерактивный расчёт по выбранному реальному участку АЦП при действующем соединении: снимок копируется из кольца или Freeze; расчёт в worker по нажатию «Рассчитать». Это **не** постоянный вывод на каждом кадре и **не обязательно сохранённый архив**.

**АРХИВ** — работа с одной или несколькими фактически сохранёнными записями, без подключения МВК01. Для повторной работы FFT, STFT, кюртограммы и огибающей **обязательна запись отсчётов временного сигнала** (NPZ с Fs, unit, ADC и source metadata). **AUX4700 JSONL/SQLite** уже содержит только готовые приборные числа: 43 третьоктавы и 24×3 позиции; из них нельзя реконструировать waveform, Fast Kurtogram, STFT или FFT.

**УСЛОВНО** — необходимы ещё не подтверждённые сведения: синхронная фаза АЦП, физические пары ортогональных датчиков, импульсы тахометра, валидированная RPM(t), входная сила или набор эталонных данных. В MVK Live пока не выставлять этот метод как готовый.

**Статусы кода:** **ЕСТЬ** — соответствующий расчёт/представление присутствует; **ЧАСТИЧНО** — базовая функция есть, но UX/обработка архива неполны; **ПЛАН** — только изученные исходники/спецификация; **ОТЛОЖЕН** — не предлагать к активации без исходных условий. Внешние примеры не равны готовой реализации в MVK.

## 1. Схема потоков и мест отображения

~~~text
     Оригинал МВК01 (TCP/10230) / один Go Native RX
                       |
             проверенные 8 АЦП + Fs, FRange один раз
                       |
              [ Ring / снимок NPZ ]
                 |             |
                 |             +--> окно анализа / сохранённая запись:
                 |                  Kurtogram, Hilbert/SES, STFT, CWT,
                 |                  Cepstrum, SRS, advanced diagnostics
                 |
                 +--> LIVE обзор: waveform, FFT, RMS/peak,
                      PSD/ASD, 1/3 из AUX4700, waterfall, short trend
     Оригинальный AUX4700 (43 + 24x3)
                 |
          [ JSONL / SQLite оригинала ]
                 +--> LIVE приборные полосы / значения
                 +--> АРХИВ тренды полос / позиций, сравнение дат

     Каждой кривой: source, ADC, session, timestamp, Fs, unit,
     filter, nfft, method, APP_DERIVED или ORIGINAL_AUX4700.
~~~

**Два независимых объекта истории:** (1) исходные аппаратные скалярные показатели AUX4700 и (2) сохранённые полноценные окна АЦП NPZ. Методы из группы «АРХИВ» могут требовать одного из них или оба, это указано отдельно.

## 2. Полная матрица: доступно при живом измерении

| № | Метод / экран, как выглядит | Реальная реализация/пример исходников | Настройки и управление | Данные / режим | MVK Live |
|---|---|---|---|---|---|
| L01 | **Осциллограмма** — крупная линия ±амплитуды, время по X, курсоры A/B | [OpenTest monitor](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/monitor/components/monitor-graphic-view-panel.vue), [c-spectrum GUI](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_gui.c), [MVK time_controls](time_controls.py) | ADC, развёртка 10–500 мс / 1–30 с, Y Auto/±, собственный фильтр, Freeze, область A–B, единицы | LIVE и ОКНО из реальных отсчётов; для длинного окна нужна реальная длина | ЕСТЬ; курсоры/выделение улучшить |
| L02 | **ВУ/ВС/ВП FFT** — спектр, пики, гармоники, курсоры | [OpenTest FFT settings](https://github.com/crysound/OpenTest-Plugins/blob/main/plugins/fft-tools/frontend/src/contributions/measure/fft-measure/setting.vue), [pySPWB FFT](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/fft_analysis.py), [MVK vibration](vibration.py) | quantity ВУ/ВС/ВП; scale лин./dB; N/Δf, window, усреднение, X/Y, peak hold, A/B, фильтр | LIVE по блокам и архив NPZ; оригинальный AUX не подменять | ЕСТЬ; инспектор и курсоры улучшить |
| L03 | **Welch PSD / ASD** — плотность мощности/амплитуды по Гц | [enDAQ PSD](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/psd.py), [MVK vibration](vibration.py) | FFT length, overlap, window, band, density vs amplitude density, интеграция энергии с df | LIVE/ОКНО; NPZ offline | ЕСТЬ |
| L04 | **Фильтрация сигнала** — один селектор типа и отдельный селектор готовой полосы | [OpenTest filter editor](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/dashboard/digital-filter-config/index.vue), [MVK octave_filters](octave_filters.py) | off, HP, LP, BP, band-stop/50/60; preset 1/1,1/3,2; в расширенном режиме порядок/частоты; показать Nyquist | Локальная обработка LIVE/ОКНО; **не** OEM-коэффициенты | ЕСТЬ; не смешивать с аппаратными 43 полосами |
| L05 | **Оригинальные 43 третьоктавные полосы** — столбики по центральным частотам + таблица RMS | [OpenTest octave screen](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/module-octave.png), [MVK original_dsp](original_dsp.py) | ADC, оригинальная 1/3, номинальная частота, подсветка полосы, показать/сохранить/тренд, без вмешательства в FIR | LIVE ORIGINAL_AUX4700 и архив исходных чисел | ЕСТЬ |
| L06 | **Сводные 1/1 полосы из 43** — столбики с другой шириной, пометка RSS | [MVK octave_filters](octave_filters.py), [enDAQ to_octave](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/psd.py) | ADC, третичные исходные диапазоны, группировка 1/1, подпись APP_DERIVED | LIVE/АРХИВ на основе 43; **не** оригинальный OEM 1/1 фильтр | ЕСТЬ |
| L07 | **24 × СКЗ/пик/размах AUX4700** — таблица и график номеров позиций | [MVK original_dsp](original_dsp.py) | ADC, № позиции 1–24, тип величины, дата, источник/валидность, переход в историю | LIVE ORIGINAL_AUX4700 + архив скаляров | ЕСТЬ; не выдумывать частотный центр/единицы |
| L08 | **Временные признаки** — компактные числовые плитки и таблица | [c-spectrum features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c), [viblearn features](https://github.com/Liang-Guo-SD/viblearn), [MVK advanced](advanced.py) | ADC, реальное окно, фильтр, RMS, peak, p-p, crest, kurtosis, skewness, impulse/shape/clearance; метод нормировки | LIVE поверх достоверных окон; сохранённый NPZ offline | ЕСТЬ, частично UI |
| L09 | **Спектр ВУ/ВС/ВП и интеграция** — те же виды с физическими единицами | [enDAQ integration](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/integrate.py), [MVK vibration](vibration.py) | Физическая полоса, защита от интеграционного DC/дрейфа, quantity, единицы | LIVE/ОКНО/NPZ; не повторять FRange | ЕСТЬ |
| L10 | **Оперативный водопад FFT** — тепловая карта X частота / Y последовательные кадры / цвет уровень | [OpenTest waterfall](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/views/waterfall-view.vue), [c-spectrum GUI](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_gui.c), [MVK app](app.py) | 20/50/120/240 реальных кадров, X, шкала цвета, единицы/тип спектра, выбранный ADC | LIVE, только новые RxPos | ЧАСТИЧНО: кадры есть, реальные timestamp/шкала/срез по курсору план |
| L11 | **Короткий Live-тренд RMS** — непрерывная линия по времени | [c-spectrum control chart](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_gui.c), [MVK app](app.py) | ADC, 20/50/120/240 последних проверенных точек, окно RMS, Y, точка | LIVE; **не** архивная история | ЕСТЬ |
| L12 | **Краткий уровень FFT-пика и позиция частоты** — числа, маркеры на FFT | [pySPWB FFT](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/fft_analysis.py), [MVK history](measurement_history.py) | quantity, диапазон пиков, marker threshold, единицы/Hz, окно и timestamp | LIVE; тренд только из сохранённого | ЕСТЬ частично |
| L13 | **Текущее состояние АЦП/связи** — 8 кнопок каналов, RX/время/ошибка, статус архивирования | [OpenTest Monitor](https://github.com/crysound/OpenTest), [MVK app](app.py) | IP, адаптер, ADC, Freeze/Stop, состояние RX, Fs read-only, исходный FRange | LIVE служебное, без DSP | ЕСТЬ; упрощение главного экрана план |
| L14 | **Метки 1×/гармоник по принятой скорости** — частотные вертикали на спектре | [viblearn fault markers](https://github.com/Liang-Guo-SD/viblearn), [MVK rotation](rotation.py) | RPM вручную/спектральная оценка с подтверждением; число гармоник; допуск | LIVE/ОКНО/NPZ при подтверждённой 1×; не тахометр | ЕСТЬ ограниченно |
| L15 | **Сохранение измерения** — действие «Сохранить окно»/«Сохранить исходный AUX» | [OpenTest test records](https://github.com/crysound/OpenTest), [MVK measurement_history](measurement_history.py) | ADC, текущая запись/UTC, N, Fs, source, SHA, reason, NPZ/JSONL | Во время LIVE; архивирование является действием, не аналитическим методом | ЕСТЬ |
| L16 | **Пользовательские семейства гармоник H1…Hn** — прогнозные пунктиры на FFT + измеренные пики отдельно | [OpenTest harmonics](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/dashboard/harmonic-order/harmonic-order-dialog.vue), [Dewesoft marker](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/harmonic-marker) | выбранная f0/принятая 1×, H1…H12, поиск пика, допуск, источник/единица, hide/show group | LIVE-наложение на FFT/огибающую или NPZ, без новых команд МВК01 | ПЛАН полноценного менеджера; базовые линии уже есть |
| L17 | **Боковые частоты** — пары слева/справа вокруг carrier и 2×/3×GMF | [OpenTest sideband form](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/chart-tools/cursor-view/cursor-settings-dialog.vue), [OROS markers](https://wiki.oros.com/index.php?title=NVGate_Marker) | f_center, f_mod, количество ±k, выбранные mesh harmonics, Peak/SNR, допуск | LIVE вычисления по новым FFT кадрам; postprocess NPZ | ПЛАН: существующие GMF± отмечаются без полноценной таблицы |
| L18 | **Текущая амплитуда выбранной гармоники** — число + небольшой Live-тренд и активная семья | [Dewesoft marker history](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/harmonic-marker), [MVK short trends](app.py) | источник f0, выбор Hn, локальное окно поиска и единицы, min/update interval | LIVE по новым RxPos, НЕ исторический тренд без сохранения | ПЛАН |
| L19 | **Частоты лопастей/лопаточных направляющих** — BPF и кратные на FFT | [phonometry diagnostics](https://github.com/jmrplens/phonometry/blob/main/src/phonometry/vibration/machinery/diagnostics.py), [vibration fan research](https://link.springer.com/article/10.1007/s43995-025-00107-2) | подтверждённые RPM, лопасти N, H1…Hn, направляющие — необязательный параметр, Nyquist | LIVE-пунктиры/ОКНО по проверенным данным, не диагноз вентилятора | ПЛАН, без карточек оборудования |

**LIVE не означает бесплатный пересчёт:** графики могут получать новые блоки асинхронно; интенсивный анализ запускается в отдельном worker с лимитом частоты обновления и отменой результатов старого ADC/сеанса.

## 3. Полная матрица: расчёт по одному выбранному окну АЦП

| № | Метод / форма графика | Где есть исходники и как работает | Экран НАСТРОЕК (всё применимо к одному ADC) | Режим / MVK |
|---|---|---|---|---|
| W01 | **FFT с A/B курсорами / энергия выбранной полосы** — FFT + подграфик выделенной полосы и таблица | [pySPWB FFT и Energy Band](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/fft_analysis.py), [enDAQ PSD integration](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/psd.py) | f_low/f_high от курсоров, N/df, нормировка, PSD/RMS, integral by df, единица, экспорт | ОКНО, NPZ; ПЛАН более удобного UI, частичный broadband RMS уже есть |
| W02 | **Hilbert-огибающая** — исходная АЧХ сверху, резонансный диапазон и спектр огибающей снизу | [c-spectrum envelope](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c), [viblearn](https://github.com/Liang-Guo-SD/viblearn), [MVK vibration](vibration.py) | выбранная BP, режим демодуляции, RMS/дБ, N, масштаб, local noise floor | ОКНО / NPZ; ЕСТЬ локально |
| W03 | **Fast Kurtogram (Антони)** — X центр полосы, Y уровень дерева, цвет excess SK; пик и выбранная клетка | [PySDKit код](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py), [тесты](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/tests/test_kurtogram.py), [MVK adapter](kurtogram.py) | ADC, реально доступное окно N=4096..32768, уровни 2..6 с ограничением log2(N)-7, курсор и валидные low/high < Nyquist, кнопка «Полоса → огибающая» | ОКНО; **ЕСТЬ** ядро и экран, для NPZ-архива прямой вход в этот экран ещё подключить |
| W04 | **Squared Envelope Spectrum, SES** — спектр квадрата огибающей (не обычной Hilbert-амплитуды) | [PySDKit find_wav_kurt](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py) извлекает комплексную packet-огибающую; дальнейшее squaring/FFT необходимо явно реализовать | клетка Kurtogram, effective Fs после decimation, remove DC, scaling, FFT, метки линий | ОКНО / NPZ; ПЛАН, не приписывать PySDKit готовый экран MVK |
| W05 | **STFT** — частота×время + спектр выбранного момента + тренд частоты | [pySPWB GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tfa_analysis.py), [DSP](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/timefreq.py), [MVK advanced](advanced.py) | окно исходного сигнала, nperseg 256–4096, перекрытие, функция окна, fmax, colormap/dynamic range, t/f cursor | ОКНО / NPZ; STFT **ЕСТЬ**, два связанных среза **ПЛАН** |
| W06 | **CWT Morlet / Scalogram** — X время, Y псевдочастота, цвет коэффициента | [PySDKit CWT/SST](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/_tfa/sst.py), [MVK advanced](advanced.py), [JYD-iBearing](https://github.com/kipp7/JYD-iBearing) | scales 16/24/40/64, wavelet, f_min/f_max, output normalization, colormap, window N | ОКНО / NPZ; CWT **ЕСТЬ**, улучшить настройки/лейблы |
| W07 | **Реальный кепстр** — X кэфренция, Y величина, курсор 1/q | [MVK advanced](advanced.py), [DewesoftX](https://dewesoft.com/products/dewesoftx/tech-specs) | N, оконная функция, max quefrency 0.001..1 с, лог-спектр, окно/источник, физическая интерпретация | ОКНО / NPZ; ЕСТЬ |
| W08 | **Спектр подшипника + линия предполагаемых дефектов** — Hilbert FFT с маркерами BPFO/BPFI/BSF/**BDF=2BSF**/FTF, их гармониками и боковыми, ожидаемые линии отдельно от реальных пиков | [c-spectrum envelope](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c), [viblearn faults](https://github.com/Liang-Guo-SD/viblearn), [MVK advanced](advanced.py) | RPM/1× и геометрия вручную, band, tolerance ±df, local SNR, минимум гармоник, repeat windows | ОКНО / NPZ; ЕСТЬ базовые линии; multi-harmonic evidence ПЛАН, **не диагноз** |
| W09 | **Частоты GMF и боковые полосы редуктора** — FFT + маркеры и таблица частот | [viblearn faults](https://github.com/Liang-Guo-SD/viblearn), [MVK advanced](advanced.py) | RPM/1× вручную, число зубьев, GMF гармоники/±1× sidebands, допуск по Hz, actual peak vs predicted | ОКНО/NPZ; ЕСТЬ прогноз, проверку обнаружения улучшить |
| W10 | **Spectral centroid** — скаляр/полоса с возможным trend | [c-spectrum cs_features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c) | PSD/energy definition, Fs, N, f_low/high, valid power, units Hz | ОКНО / NPZ и потом АРХИВ; ПЛАН |
| W11 | **Spectral flatness** — скаляр 0..1 и архивный trend | [c-spectrum cs_features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c) | PSD mean **geometric/arithmetic PSD**, band, eps, исключение тишины; **не копировать нестандартный denominator c-spectrum** | ОКНО / NPZ; ПЛАН |
| W12 | **HF energy ratio / энергия заданной полосы** — числовая доля и trend | [c-spectrum features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c), [enDAQ PSD](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/psd.py) | высокочастотная граница, опорная полоса, integrate PSD, сквозная единица и Fs | ОКНО / NPZ; ПЛАН |
| W13 | **Autocorrelation / повторяемость импульсов** — корреляция по задержке | [pySPWB adaptive processing](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/adaptive.py), [c-spectrum harmonic check](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c) | window/lag max, detrend, нормировка, порог качества; в огибающей отличать случайный удар от периода | ОКНО / NPZ; ПЛАН, без готовой подтверждённой диагностики |
| W14 | **SRS / PVSS** — максимум отклика SDOF-осцилляторов по натуральной частоте | [enDAQ shock.py](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/shock.py) (ISO 18431-4), [Dewesoft SRS](https://dewesoft.com/products/dewesoftx/tech-specs) | частоты от/до, 1/3 или 1/12 octave per bin, damping ζ/Q, mode SRS/PVSS, maximum time, positive/absolute | ОКНО / NPZ, **не** AUX; ПЛАН как отдельный ударный метод, не основной тренд смазки/подшипника |
| W15 | **Synchrosqueezing SST** — концентрированная временно-частотная карта | [PySDKit SST](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/_tfa/sst.py) | Morlet/bump, scales, adaptive bandwidth tiles, threshold, f_range, time range | ОКНО / NPZ; ПЛАН/R&D после STFT |
| W16 | **IMCKD** — очищенный импульсный сигнал + trace роста correlated kurtosis | [PySDKit IMCKD](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/deconvolution/_imckd.py) | период повтора, filter taps, iteration count, shift order, original-vs-filtered, iterations trace | ОКНО / NPZ; ПЛАН/R&D, ложные признаки при неверном периоде |
| W17 | **Циклическая спектральная когерентность** — теплокарта циклическая частота α × частота f | [cyclo analysis](https://github.com/TreyShenk/cyclo/blob/main/src/cyclo/analysis.py), method TSM | α_min/max, шаг α, Ndft, число блоков, overlap, normalization, max memory/time | ОКНО / длинная NPZ; ПЛАН/R&D; нужен тест вычислительной нагрузки и точности |
| W18 | **Оценка 1× из спектра скорости** — кандидат оборотов + спектральный маркер | [MVK rotation](rotation.py), [rota-order speed ridge](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/speed.py) | f_search_min/max, harmonic acceptance, quality, вручную «Принять RPM» | ОКНО / NPZ; базовая оценка ЕСТЬ, не приравнивать к тахометру |
| W19 | **Адаптивная фильтрация LMS** — сырой / очищенный сигнал + convergence | [pySPWB adaptive](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/adaptive.py) | reference and response, LMS/NLMS, taps, step, leakage, correlation | **УСЛОВНО**: нужна опорная помеха/доказанная синхронизация; ОТЛОЖЕНО |
| W20 | **FRF H1/H2, coherence, phase** — модуль/фаза/когерентность | [pySPWB transfer](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/processing/dsp/transfer.py), [GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tf_analysis.py) | force/ref channel, response, комплексное усреднение, N/window/overlap, H1/H2, phase unwrap | **УСЛОВНО**, нет подтверждённого sync-reference; ОТЛОЖЕНО |
| W21 | **Wavelet Packet Decomposition (WPD)** — энергия и куртозис по частотным полосам | [bearing WPD example](https://github.com/Dingding1996/bearing-fault-diagnosis), [wavelet repo](https://github.com/rajeevfee/Wavelet-Based-Bearing-Fault-Diagnosis) | wavelet db4/sym5/coif3, глубина, relative energy, выбранное исходное окно | ОКНО/NPZ, ПЛАН; гистограмма полос, не OEM 1/3 |
| W22 | **EMD / VMD разложение** — стек IMF/мод и огибающая выбранной | [CWRU decomposition.py](https://github.com/akshatverma1602/Signal-Processing-on-CWRU-Bearing-Dataset/blob/main/decomposition.py) | EMD max IMF, VMD K/alpha/tau/init/tolerance, критерий выбора моды | ОКНО/NPZ, ПЛАН/R&D; следить за mode mixing |
| W23 | **Cepstral pre-whitening** — спектр до/после удаления доминирующих периодичностей | [Borghesani et al. MSSP](https://www.sciencedirect.com/science/article/pii/S0888327012003950) | lifter/log-spectrum smoothing, window, band, output normalization | ОКНО/NPZ, ПЛАН/R&D, затем Hilbert/SES с отдельным методом |
| W24 | **Teager–Kaiser Energy Operator** — импульсная энергетическая осциллограмма | [ISA Transactions TKEO](https://www.sciencedirect.com/science/article/pii/S0019057812002005) | физическая полоса до преобразования, метод нормировки, контроль шума, N | ОКНО/NPZ, ПЛАН собственного DSP, не готовый перенос UI |
| W25 | **Spectral entropy** — скаляр Шеннона + энергетический спектр | [bearing features](https://github.com/Dingding1996/bearing-fault-diagnosis) | PSD window/N, f_low/f_high, нормировка 0..1, тишина/missing | ОКНО/NPZ, ПЛАН, локальное APP_DERIVED |
| W26 | **Проверка нескольких гармоник и коллизий** — таблица ожидаемых/измеренных частот и local SNR | [viblearn evidence](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py), [c-spectrum envelope](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c) | family, Hn, RPM, frequency tolerance, minimum supporting lines, peak interpolation, collision detection | ОКНО/NPZ, ПЛАН, не диагноз по одному пику |
| W27 | **Gear Sideband Energy Ratio / Index** — GMF±k и относительная энергия боковых | [NREL report](https://docs.nrel.gov/docs/fy12osti/54530.pdf), [JSV ISER](https://www.sciencedirect.com/science/article/pii/S0022460X20305423) | GMF, f_mod, k, local bandwidth, amplitude vs power ratio, режим RPM/load | ОКНО/NPZ, ПЛАН, нужен baseline для сравнения |
| W28 | **AM/FM демодуляция** — мгновенная амплитуда и частота узкополосного сигнала | [planetary gearbox study](https://onlinelibrary.wiley.com/doi/10.1155/2017/6565237) | resonant band, analytic Hilbert, phase unwrap, amplitude gate, FFT of modulation | ОКНО/NPZ, ПЛАН/R&D |
| W29 | **Ширина резонансного пика / damping marker** — частотные пороги, ширина, Q при валидной FRF | [Dewesoft damping](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/damping-marker) | selected peak, dB cutoff, interpolation; FRF presence required for физический Q/ζ | ОКНО/NPZ: ширина возможна; физическое демпфирование УСЛОВНО |
| W30 | **Поиск периодических ударов** — waveform с метками событий и гистограмма межударных периодов | [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c), [enDAQ shock](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/shock.py) | event threshold, noise floor, dead time, min repeats, envelope/filtered input | ОКНО/NPZ, ПЛАН; единичный удар не доказывает дефект |
| W31 | **Time-Synchronous Averaging (TSA)** — оборотное среднее и остаточная вибрация | [pyvib diagnosis](https://github.com/andrek10/bearing-vibration-diagnostics-toolbox/blob/master/examples/diagnosis.py), [MATLAB TSA reference](https://github.com/matlab/matlab-agentic-toolkit/blob/main/skills-catalog/control-systems/matlab-extract-rotating-machinery-features/references/tsa.md) | подтверждённая RPM(t)/shaft angle, resampling, cycles, rejection, residual FFT | **УСЛОВНО**, ОТЛОЖЕНО до проверенной фазы/тахометра |
| W32 | **Поиск признаков неисправностей** — отдельная вкладка с таблицей диагностических гипотез и фактических спектральных доказательств | [c-spectrum envelope](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c), [viblearn evidence](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py), [экран и алгоритм](CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md) | АЦП/реальная NPZ, подтверждённые RPM/1×, BPFO/BPFI/**BDF=2BSF**/FTF, BPFI±fr/BDF±FTF, геометрия по необходимости, полоса огибающей/Fast Kurtogram, FFT, Hn, tolerance, local SNR, коллизии, статус/ограничения | **ОКНО / NPZ, ПЛАН**; отдельная функция, НЕ автоматическая постановка диагноза |
| W33 | **Энергия гармонических полос подшипника** — вклад BPFO/BPFI/BSF/BDF/FTF в спектр огибающей | [bearing-fault-monitor frequency_domain.py](https://github.com/CaringNihilistic/bearing-fault-monitor/blob/master/src/bearing_pdm/features/frequency_domain.py), [аудит](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md) | по каждому физическому Hn: nominal f, band ±Hz/%, PSD integration и reference band, единицы, min valid N | ОКНО/NPZ → архивный тренд, **ПЛАН** |
| W34 | **Боковые полосы подшипника BPFI±fr и BDF±FTF** — measured peaks, paired sidebands, локальный фон | [riya features.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/features.py), [MathWorks bearingFaultBands](https://www.mathworks.com/help/predmaint/ref/bearingfaultbands.html) | RPM/FTF, carrier BPFI/BDF, n harmonics, ±m pairs, tol/df, local SNR, collision, no silent carrier normalization | ОКНО/NPZ, **ПЛАН**; расширение W08/W26 |
| W35 | **Autogram** — оптимальная полоса по автокорреляции квадрата огибающей | [MSSP Autogram](https://www.sciencedirect.com/science/article/pii/S0888327017306441), [аудит](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md) | bank/decomposition level, lag T, window N, correlation metric, comparison with SK band | ОКНО/NPZ, **R&D**, не реализован |
| W36 | **EES/IES из cyclic spectral coherence** — улучшенная огибающая на фоне VFD/EMI | [MSSP 2020](https://www.sciencedirect.com/science/article/pii/S0888327020300595) | α×f map, segment/window/overlap, integration over all or selected carrier band, f range | ОКНО/NPZ, **R&D**, нужен независимый DSP |
| W37 | **WCES weighted combined envelope spectrum** — многополосное объединение | [Measurement 2022](https://www.sciencedirect.com/science/article/pii/S026322412101335X) | band count, weights, normalization, SCoh mode, α/f limits, chosen bands | ОКНО/NPZ, **R&D**, не готовый код |
| W38 | **IESCFFOgram** — оптимизация резонансной полосы по кандидатным частотам дефектов | [Journal of Sound and Vibration 2022](https://www.sciencedirect.com/science/article/pii/S0022460X22000037) | RPM+geometry, candidate BPFO/BPFI/BDF, α tolerance, band-selection constraints | ОКНО/NPZ, **R&D**, может подтвердить неверную гипотезу |
| W39 | **Spectral Auto-Correlation Analysis (SACA)** — подчёркивание повторяющегося гребня линий | [MSSP 2013](https://www.sciencedirect.com/science/article/pii/S0888327013003798) | spectral resolution, correlation lag, iteration, calibration/normalization | ОКНО/NPZ, **R&D**, сравнение с Hilbert/SES |
| W40 | **Tacholess envelope order spectrum** — гармоники BPFO/BPFI в порядках при разгоне | [riya order_tracking.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/order_tracking.py), [Sensors 2013](https://www.mdpi.com/1424-8220/13/8/10856) | только подтверждённая RPM(t) и uncertainty, angular re-sampling, pts/rev, band-pass in Hz BEFORE angular mapping | **УСЛОВНО/ОТЛОЖЕНО**, недостаточно одной ручной 1× |

| W41 | **Protrugram** — карта резонансных полос по куртозису FFT огибающей | [оригинальная статья MSSP](https://www.sciencedirect.com/science/article/pii/S0888327010001895), [новый аудит](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md) | диапазон fc/bandwidth, N/Fs, демодуляция, window, score definition, top bands | ОКНО/NPZ, **R&D/ПЛАН**, не реализован |
| W42 | **Infogram (SE/SES)** — отдельные карты негэнтропии квадрата огибающей и его спектра | [Applied Sciences 2020](https://www.mdpi.com/2076-3417/10/8/2657), [настройки и ограничения](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md) | bank level, SE/SES/combined, DC, FFT scaling, normalization, top bands | ОКНО/NPZ, **R&D/ПЛАН**, не реализован |
| W43 | **Spectral Gini selector** — выбор полосы по sparsity индексу Джини | [Applied Sciences 2020](https://www.mdpi.com/2076-3417/10/8/2657), [новый аудит](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md) | filterbank, вход в индекс, Gini definition, N/Fs, normalization, карта | ОКНО/NPZ, **R&D/ПЛАН**, не реализован |

**Правило для тяжёлых методов:** пользователь должен видеть на экране «Источник: АЦП / сеанс / фрагмент / Fs / N», нажимать «Рассчитать», а при смене канала результат предыдущего сеанса должен быть отброшен или помечен как исторический. Вкладки не запускают дополнительный TCP.

## 4. Полная матрица: только серия сохранённых измерений / история

| № | Метод и экран | Реализация / пример | Экран настройки | Требуемый архив / статус MVK |
|---|---|---|---|---|
| A01 | **Долгосрочный тренд выбранного показателя** — дата × значение, A/B курсоры, выделение периода | [MVK history](measurement_history.py), [OpenTest saved records](https://github.com/crysound/OpenTest) | ADC, original/local source, величина, позиция/частота, период, UTC/local, вид пропусков | AUX или NPZ со скаляром; ЕСТЬ, нужны инструменты UX |
| A02 | **Наложение исторических спектров** — 2–8 кривых/легенда дат, выбор исходной записи | [MVK history widgets](history_widgets.py), [Adash DDS](https://adash.com/software-vibration-analysis/digital-diagnostics-system) | ADC, одинаковый quantity+unit+provenance, даты, RMS/dB, fmax, режим overlay/раздельные панели | NPZ или сохранённый спектр с совместимыми параметрами; ЕСТЬ частично |
| A03 | **Архивный водопад** — спектр × реальное время, кликом открыть кадр и частотный тренд | [OpenTest waterfall view](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/views/waterfall-view.vue), [OROS NVGate Waterfall](https://wiki.oros.com/index.php?title=NVGate_Waterfall) | ADC, даты, source/units, Hz interval, color scale, time or verified RPM, sample gaps | Серия NPZ или сохранённых совместимых спектров с timestamps; **ПЛАН**, нынешний waterfall только Live |
| A04 | **Спектр в выбранную дату** — точка тренда → выбранный FFT/временной сигнал | [OpenTest Analyze/Records](https://github.com/crysound/OpenTest), [MVK history widgets](history_widgets.py) | выбор точки/даты, тип source, открыть исходные NPZ, некорректные не интерполировать | NPZ для waveform/FFT; AUX скаляры доступны отдельно; ЧАСТИЧНО |
| A05 | **Тренды спектральных признаков** — RMS/crest/kurtosis/centroid/flatness/HF ratio vs UTC | [c-spectrum features](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c), [MVK measurement_history](measurement_history.py) | показатель, одинаковые Fs/band/window, шаг, агрегация, baseline (optional) | NPZ серия / уже индексированные local_values; первые значения ЕСТЬ, новые centroid/flatness/HF ПЛАН |
| A06 | **EWMA / статистический контроль** — признак + baseline/upper/lower bands и событие | [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c) | время обучения, λ, σ, consecutive, dwell, adapt allowed, gap handling, study window | ТОЛЬКО сопоставимая реальная серия измерений. ПЛАН, отсутствие baseline = «не оценено» |
| A07 | **Сравнение состояния до/после** — таблица прироста и 2 совместимых FFT | [OpenTest Test Records](https://github.com/crysound/OpenTest), [MVK history](history_widgets.py) | две или несколько сохранённых дат, интервал, quantity, freq-grid matching, статистика Δ/отношение | AUX same position/source или NPZ same calculation; ЧАСТИЧНО |
| A08 | **Оценка стойкости гармоник на нескольких записях** — строки найденных частот vs дата | [c-spectrum envelope](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c) как однокадровая основа | геометрия/RPM, band/method, tolerance, ≥2 harmonics, repeat windows, noise floor | NPZ серия; ПЛАН для подтверждения диагностических признаков |
| A09 | **Сравнение куртограмм и огибающих до/после** — пара карт/SES, одинаковая шкала | [PySDKit kurtogram](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py) | ADC, одинаковые N/Fs/level/method/band, две даты, peak values/locations | NPZ двух записей; ПЛАН, корректное сравнение без скрытых пересэмплирований |
| A10 | **Историческая диагностика изменений** — таблица «гипотеза / признаки / источники / ограничения / перейти на график» | [c-spectrum monitor+envelope](https://github.com/arkid-lutaj/c-spectrum), [viblearn faults](https://github.com/Liang-Guo-SD/viblearn) | доступные признаки, окна, выбранные частоты, приемлемая повторяемость, ручной RPM | серии совместимых NPZ/АUX, ПЛАН; **не** диагноз по одному пику |
| A11 | **Карта Кэмпбелла и карта порядков** — Hz/RPM или order/RPM с контурами и линиями | [rota-order maps](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/maps.py), [изображения](https://github.com/ZhenxianLi/rota-order/tree/main/docs/images), [Dewesoft](https://dewesoft.com/applications/order-analysis) | истинная RPM(t), fs, order/max frequency, samples/rev, FFT N, bin RPM, run-up/down, dynamic range | **УСЛОВНО**, нужна физически валидная скорость vs время; пока не добавлять как работающий метод |
| A12 | **Орбита X–Y, Bode/Nyquist и балансировка** — 2D XY, вектор фаза/скорость | [Dewesoft order/orbit](https://dewesoft.com/applications/order-analysis), [REI SignalLab simulator](https://github.com/rootcastleco/rei-signallab/blob/main/frontend/src/components/VibrationWorkbench.jsx) | одновременно измеренные X,Y в физических направлениях, угловая метка, фаза, speed/time, rpm | **УСЛОВНО** — неподтверждённая синхронизация и физическая привязка датчиков, ОТЛОЖЕНО |
| A13 | **ML-классификация по данным подшипников** — классы и неоткалиброванные softmax | [JYD-iBearing model_infer](https://github.com/kipp7/JYD-iBearing/blob/main/backend/model_infer.py) | модель/версия, dataset/regime, окно, предобработка, калибровка/uncertainty, OOD | **ПЛАН/R&D, НЕ внедрять** без обучения/валидации под МВК01 |
| A14 | **Отчёт анализа** — выбранные графики, таблицы, единицы/метаданные и метод | [OpenTest report](https://github.com/crysound/OpenTest), [c-spectrum CSV/JSON](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_report.c) | набор виджетов, дата, source, ADC, алгоритм, параметры, производные/оригинал, PNG+CSV+JSON | АРХИВ; часть экспорта ЕСТЬ, единый шаблон ПЛАН |
| A15 | **Долговременный тренд конкретной Hn/GMF/BPFO/BPF** — уровень и дата, маркеры событий | [Dewesoft marker full history](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/harmonic-marker) | ADC, saved NPZ/spectrum, Hn, method/units, исходная RPM на дату, UTC, data gaps | только сопоставимая СЕРИЯ архивов; ПЛАН |
| A16 | **Тренды боковой энергии и SNR семейств** — дата/отношение и отдельный baseline | [NREL gearbox study](https://docs.nrel.gov/docs/fy12osti/54530.pdf), [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c) | fixed method, physical band, RPM/load class, modulation, sidebands, baseline | архив NPZ/спектров, ПЛАН |
| A17 | **Наложение 2–8 спектров с отдельными семейными маркерами** — общий FFT и таблица коллизий по датам | [OROS marker](https://wiki.oros.com/index.php?title=NVGate_Marker), [MVK history widgets](history_widgets.py) | trace/source per date, 1× per date, compatibility, Hn and legend display | архивные NPZ/совместимые кривые; ПЛАН поверх существующего overlay |
| A18 | **Сравнение признаков при сопоставимых оборотах и нагрузке** — группы дат/графики и необнаруженные пики | [riya bearing monitor](https://github.com/riya0920/bearing-condition-monitoring), [bearing diagnostics dataset](https://github.com/Dingding1996/bearing-fault-diagnosis) | физически подтверждённые RPM/load metadata, same ADC/method/band, count | только серия архива; ПЛАН; нет load → не сравнивать под видом одного режима |
| A19 | **Повторяемость семейства на независимых записях** — доля наблюдений, 2+ гармоники, collision history | [viblearn diagnostics](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py), [CWRU study](https://github.com/riya0920/bearing-condition-monitoring) | источник, семейство, tolerances, min windows, noise floor, UTC, missing not zero | только серия NPZ/проверенных спектров, ПЛАН; не автономный диагноз |
| A20 | **Ретроспективный поиск и подтверждение признаков дефектов** — сравнение гипотез по сериям записей, фактические подтверждения и SNR-тренд | [viblearn evidence ledger](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py), [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c), [экран архива](CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md) | совместимые NPZ/спектры, АЦП, даты, RPM по каждой записи, единицы, источник, Hn и минимум независимых наблюдений, baseline/пропуски | **ТОЛЬКО СЕРИЯ АРХИВНЫХ ЗАПИСЕЙ, ПЛАН**; не реконструировать FFT из AUX4700 |

**Методы не «архивные» только потому, что данные хранятся.** Кюртограмма/STFT/CWT работают по **одному NPZ**, а тренды и EWMA требуют **серии**. Из одного сохранённого набора scalar AUX нельзя честно создавать исходный waveform.

## 4a. Автоматический анализ и диагностика — новый обязательный блок (D01–D44)

**Дополнено:** предыдущие 82 метода относились к LIVE/окну/архиву, но не раскрывали автоматическую диагностику как самостоятельный набор алгоритмов. **Теперь в полном каталоге 126 пунктов**: 19 LIVE + 43 ОКНО + 20 АРХИВ + **44 диагностических требования**. Эти 44 позиции — отдельные функции общего диагностического движка, не 44 подтверждённых вычислительных реализации. Существующие W32/A20 остаются общей оболочкой.

**Полные 44 строки** с формулами/признаками, исходными файлами, лицензиями, экранами, настроечными полями, требованиями к входному потоку, проверками и ограничениями: [AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md).

| Код | Семейство | Автоматический метод | Работа с данными | Приоритет | Статус | Подробности |
|---|---|---|---|---|---|---|
| **D01** | Качество | **Автоматический контроль пригодности сигнала** | LIVE / ОКНО / NPZ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D02** | Общий движок | **Независимый автоматический поиск реальных пиков** | LIVE preview / ОКНО / NPZ | P0 | ЧАСТИЧНО: локальный максимум есть; independent finder нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D03** | Общий движок | **Сопоставление реальных пиков с расчётными семействами** | ОКНО / NPZ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D04** | Общий движок | **Проверка нескольких гармоник и боковых полос** | ОКНО / NPZ | P0 | ЧАСТИЧНО: SNR/4Hn, полноценной проверки нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D05** | Подшипники | **Автопоиск признаков дефекта наружного кольца BPFO** | ОКНО / NPZ → АРХИВ | P0 | ПЛАН: теоретический маркер есть | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D06** | Подшипники | **Автопоиск признаков дефекта внутреннего кольца BPFI** | ОКНО / NPZ → АРХИВ | P0 | ПЛАН: теоретический маркер есть | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D07** | Подшипники | **Автопоиск признаков дефекта тела качения BSF/BDF** | ОКНО / NPZ → АРХИВ | P0 | ПЛАН: BSF есть, BDF как отдельная диагностика нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D08** | Подшипники | **Автопоиск признаков дефекта сепаратора FTF** | ОКНО / длинная NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D09** | Подшипники | **Контроль парных боковых полос подшипника** | ОКНО / NPZ → АРХИВ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D10** | Подшипники | **Рост высокочастотной энергии / распределённый износ** | ОКНО / NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D11** | Подшипники | **Автовыбор диагностической полосы по согласию методов** | ОКНО / NPZ | P2/R&D | R&D: только Fast Kurtogram реализован | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D12** | Редукторы | **Автопоиск частоты зацепления GMF и гармоник** | LIVE markers / ОКНО / NPZ | P0 | ЧАСТИЧНО: линии GMF, поиск пиков не завершён | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D13** | Редукторы | **Поиск локального дефекта зуба по боковым GMF** | ОКНО / NPZ → АРХИВ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D14** | Редукторы | **Признаки распределённого износа зубчатой пары** | ОКНО / NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D15** | Валы/опоры | **Автопоиск признаков дисбаланса ротора** | LIVE markers / ОКНО → АРХИВ | P1 | ПЛАН: 1× маркер есть | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D16** | Валы/опоры | **Автопоиск признаков несоосности валов** | ОКНО / NPZ → АРХИВ | P1 | УСЛОВНО: без осевых данных/фазы ограничено | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D17** | Валы/опоры | **Признаки механической ослабленности/крепежа** | ОКНО / NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D18** | Валы/опоры | **Признаки задевания, трения и контакта ротора** | ОКНО / NPZ → АРХИВ | P2 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D19** | Валы/опоры | **Признаки искривления вала/эксцентриситета** | ОКНО / NPZ → АРХИВ | ОТЛОЖИТЬ | УСЛОВНО: только признаки без синхронизированной фазы | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D20** | Валы/опоры | **Резонанс/возбуждение собственных частот** | ОКНО / серия на разных RPM | ОТЛОЖИТЬ | УСЛОВНО: нет проверенного RPM(t)/FRF | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D21** | Вентиляторы | **Частота прохождения лопаток BPF и гармоники** | LIVE markers / ОКНО / NPZ | P1 | ПЛАН: текстовый BPF прогноз в каталоге | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D22** | Вентиляторы | **Признаки повреждения лопатки / неравномерности** | ОКНО / NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D23** | Вентиляторы | **Аэродинамическая неустойчивость вентилятора** | ОКНО / серия NPZ | P2 | УСЛОВНО: нужен режим потока/нагрузки | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D24** | Насосы | **Автопоиск частот рабочего колеса VPF** | ОКНО / NPZ → АРХИВ | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D25** | Насосы | **Признаки кавитации/рециркуляции** | ОКНО / NPZ → АРХИВ | P2 | УСЛОВНО: без гидравлических данных нет подтверждения | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D26** | Ремённые передачи | **Ременная частота/проскальзывание/пульсация** | ОКНО / NPZ → АРХИВ | P2 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D27** | Электродвигатели | **Спектральные признаки 2× частоты питания** | ОКНО / NPZ → АРХИВ | P2 | УСЛОВНО: без питания/полюсов диагностика невозможна | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D28** | Электродвигатели | **Роторные стержни/кольца: частоты скольжения** | длинная NPZ / архив | ОТЛОЖИТЬ | УСЛОВНО: требуется физически подтверждённый slip и T | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D29** | Электродвигатели | **Эксцентриситет воздушного зазора / пазовые частоты** | длинная NPZ / архив | ОТЛОЖИТЬ | УСЛОВНО: без числа пазов/режима не оценено | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D30** | Подшипники скольжения | **Масляная вихревая неустойчивость / oil whirl-whip** | длинная NPZ / RPM history | ОТЛОЖИТЬ | УСЛОВНО: нет подтверждённого узла и RPM(t) | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D31** | События | **Автопоиск повторяющихся ударов/импульсов** | LIVE preview / ОКНО / NPZ | P1 | ЧАСТИЧНО: есть импульсные признаки, событийного списка нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D32** | Качество | **Автоопределение стационарности окна/скорости** | LIVE preview / ОКНО | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D33** | Аномалии | **Контроль по здоровой базе и робастным порогам** | АРХИВ | P1 | ЧАСТИЧНО: тренды есть, baseline gate нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D34** | Аномалии | **EWMA/CUSUM и адаптивные контрольные карты** | АРХИВ / короткий LIVE-тренд (после обучения) | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D35** | Аномалии | **Многомерный T² / Isolation Forest (без учителя)** | АРХИВ | P2/R&D | R&D; готового промышленного классификатора нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D36** | Аномалии | **Автоэнкодер/нейросетевая новизна** | АРХИВ / OFFLINE | ОТЛОЖИТЬ | R&D; не подключать к LIVE автоматически | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D37** | Общее состояние | **Оценка общего виброуровня по классу машины** | LIVE values / ОКНО → АРХИВ | P2 | УСЛОВНО: заводская зона пока ориентировочная | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D38** | Архив | **Автоматическая проверка сопоставимости измерений** | АРХИВ | P0 | ПЛАН: overlay есть, compatibility отсутствует | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D39** | Архив | **Проверка повторяемости признака на независимых записях** | АРХИВ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D40** | Решения | **Гистерезис, M-of-N, фиксация предупреждений** | АРХИВ / агрегированный LIVE после валидации | P1 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D41** | Решения | **Объединение конкурирующих гипотез и реестр доказательств** | ОКНО / АРХИВ | P0 | ПЛАН | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D42** | Решения | **Единый экран автоматического поиска признаков неисправностей** | ОКНО / АРХИВ | P0 | ПЛАН: W32/A20 в каталоге, экрана нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D43** | Машинное обучение | **Обучаемый классификатор типа дефекта** | АРХИВ / OFFLINE | ОТЛОЖИТЬ | R&D: нет верифицированной обученной модели MVK01 | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |
| **D44** | Прогноз | **Оценка деградации/RUL по траектории тренда** | АРХИВ | ОТЛОЖИТЬ | R&D: прогноза ресурса нет | [настройки и код](AUTOMATIC_DIAGNOSTICS_METHODS_AND_RULES_CATALOG_RU.md) |

**Единый Excel-фильтруемый список всех 126 позиций** (включая D): [UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.csv](UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.csv); [полная матрица Markdown](UNIFIED_IMPLEMENTATION_MATRIX_20261118_RU.md).

## 5. Сравнение приложений: какие экраны реально доступны, а где есть только код

| Программа | Реальная организация интерфейса | Настройки метода: исходники | Польза / ограничения |
|---|---|---|---|
| **OpenTest** (CRYSOUND) | Monitor — сетка графиков; Measure — настройка выбранного метода; Analysis — просмотр результатов; Records/Report — архив | [FFT form](https://github.com/crysound/OpenTest-Plugins/blob/main/plugins/fft-tools/frontend/src/contributions/measure/fft-measure/setting.vue), [grid](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/monitor/components/monitor-graphic-grid-viewer.vue), [digital filter](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/dashboard/digital-filter-config/index.vue), [cursor settings](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/chart-tools/cursor-view/cursor-settings-dialog.vue) | **Главный источник UX для MVK.** Не считать исходниками открытыми все коммерчески поставляемые плагины. OpenTest Community License не MIT. |
| **c-spectrum** | Постоянная тёмная левая диагностика, большой активный график: Spectrum, Waveform, Waterfall, Envelope, Control Chart | [cs_gui.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_gui.c), [cs_analysis.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_analysis.c), [cs_features.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_features.c), [cs_monitor.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c), [main.c CLI](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/main.c) | **Источник диагностической панели и графиков.** Многие параметры задаются CLI, не GUI; пороги/микрофонные единицы нельзя копировать на МВК. MIT. |
| **pySPWB** | Отдельные Qt-окна Time Data, FFT, TF/Coherence, Time-Frequency (3 связанных вида), Adaptive LMS | [FFT GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/fft_analysis.py), [TFA GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tfa_analysis.py), [Transfer GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/tf_analysis.py), [LMS GUI](https://github.com/Charette-AI-Group/pySPWB/blob/main/src/spwb/gui/lms_analysis.py) | Ближайший к нашему PySide6. Особенно полезны курсоры и связанные срезы; MIT. |
| **PySDKit** | Алгоритмы и демонстрационные графики, **не** готовый настольный измерительный UI | [Fast Kurtogram](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py), [SST](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/_tfa/sst.py), [IMCKD](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/deconvolution/_imckd.py) | Fast Kurtogram перенесён с лицензией MIT; его UI самостоятельно создаётся у нас. |
| **AccelSpectra** | Небольшой Qt6-экран: приборные настройки отдельно, FFT и X/Y/Z checkboxes | [MainWindow.cpp](https://github.com/electromake/AccelSpectra/blob/main/src/ui/MainWindow.cpp) | Компактная форма FFT, GPL-3 — не копировать исходники без оценки лицензии. |
| **REI SignalLab** | Широкий web-workbench, вкладки Spectrum/Order/Envelope/Balancing, демонстрационные orbit panels | [VibrationWorkbench.jsx](https://github.com/rootcastleco/rei-signallab/blob/main/frontend/src/components/VibrationWorkbench.jsx), [backend](https://github.com/rootcastleco/rei-signallab/blob/main/backend/app/vibration_engine.py) | Пример навигации и форм, не метрологическая валидация; в backend встречаются фиксированные «confidence» без калибровки. |
| **JYD-iBearing** | Веб-страницы Wave analysis / Spectrum analysis / historical / ML, часто загрузка CSV → анализ | [SpectrumUpload.tsx](https://github.com/kipp7/JYD-iBearing/blob/main/Web/app/spectrum-analysis/SpectrumUpload.tsx), [TimeDomainUpload.tsx](https://github.com/kipp7/JYD-iBearing/blob/main/Web/app/wave-analysis/TimeDomainUpload.tsx), [model_infer.py](https://github.com/kipp7/JYD-iBearing/blob/main/backend/model_infer.py) | Пример разделения post-record методов, не доказанный промышленный классификатор. |
| **enDAQ-python** | Скорее аналитическая Python-библиотека с plotting-функциями, чем единый Live GUI | [fft.py](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/fft.py), [psd.py](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/psd.py), [shock.py](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/shock.py) | Математический образец PSD, octave grouping, SRS; UI создавать в MVK. |
| **viblearn** | Python API и Matplotlib plot helpers, не настольная программа | [README](https://github.com/Liang-Guo-SD/viblearn), API features/faults/plotting | Для признаков, FFT, markers and frequency rules; не копировать универсальные нормы без условий. |
| **rota-order** | Matplotlib карты RPM-frequency, RPM-order, line/slices, run-up analyses | [maps.py](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/maps.py), [speed.py](https://github.com/ZhenxianLi/rota-order/blob/main/src/rota_order/speed.py), [plot](https://github.com/ZhenxianLi/rota-order/tree/main/docs/images) | Хорошие примеры Campbell/order, но нужна RPM(t); GPL-3. |
| **cyclo** | Python математический движок без готового нашего UI; двумерный cyclic spectrum/coherence | [analysis.py](https://github.com/TreyShenk/cyclo/blob/main/src/cyclo/analysis.py) | Дальнейший R&D для повторяющихся модуляций, требует вычислительной и физической проверки. |
| **DREAM 5 / ВАСТ** | Панели состояния, спектры/огибающая/диагноз/архив по диагностическим признакам | [видеоуроки DREAM](https://rutube.ru/channel/33303047/) | Промышленный ориентир, **не** копировать дерево оборудования и карточки. Исходники не предоставлены. |
| **Adash DDS** | Несколько совместных спектров, waveform, trends, вложенные диаграммы | [описание DDS](https://adash.com/software-vibration-analysis/digital-diagnostics-system) | Многографическая раскладка/overlay, без переноса закрытого кода. |
| **DewesoftX** | Настраиваемые измерительные/анализирующие дисплеи, FFT, waterfall, order, Campbell, orbit, FRF | [order manual](https://manual.dewesoft.com/x/setupmodule/modules/machinery/ordertracking), [виджеты](https://dewesoft.com/academy/online/display-widgets-in-dewesoftx) | Контекстные настройки выбранного графика и постобработка; закрытый промышленный продукт. |
| **OROS NVGate** | Вкладки FFT1–4 / Sync Order / 1/n Octave / Tachometer и подпредставления Main/Profile/Waterfall | [OROS waterfall](https://wiki.oros.com/index.php?title=NVGate_Waterfall), [FFT results screenshot](https://wiki.oros.com/index.php?title=File:FFT_results.png) | Сильный пример: параметры «Settings / Trigger / Average / FFT zoom» отдельно от графиков; закрытый код. |

## 6. Настоящие экраны из репозиториев — визуальная галерея для дизайна

**Подписи ниже обозначают НАСТОЯЩИЕ изображения авторов проектов, а не макеты MVK.** Файлы присутствуют в проверенных каталогах GitHub; ссылка на каждый PNG/WEBP ведёт в исходный репозиторий. Сами изображения не скопированы в MVK, не включаются в Windows-дистрибутив.

### 6.1. OpenTest: рабочее место и измерительные настройки

| Главное окно / Monitor | FFT — экран измерения | Octave — отдельная задача |
|---|---|---|
| ![OpenTest main](https://raw.githubusercontent.com/crysound/OpenTest/main/docs/assets/readme/opentest-main-window.webp) | ![OpenTest FFT](https://raw.githubusercontent.com/crysound/OpenTest/main/docs/assets/readme/module-fft.png) | ![OpenTest octave](https://raw.githubusercontent.com/crysound/OpenTest/main/docs/assets/readme/module-octave.png) |
| [Открыть](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/opentest-main-window.webp) | [Открыть](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/module-fft.png) | [Открыть](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/module-octave.png) |

| Measure mode | Analysis mode | Пример настроек и контролов |
|---|---|---|
| ![Measure](https://raw.githubusercontent.com/crysound/OpenTest/main/docs/assets/readme/mode-measure.png) | ![Analysis](https://raw.githubusercontent.com/crysound/OpenTest/main/docs/assets/readme/mode-analysis.png) | [Фактическая форма FFT, Vue](https://github.com/crysound/OpenTest-Plugins/blob/main/plugins/fft-tools/frontend/src/contributions/measure/fft-measure/setting.vue) |
| [Открыть](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/mode-measure.png) | [Открыть](https://github.com/crysound/OpenTest/blob/main/docs/assets/readme/mode-analysis.png) | Настройки на пяти раскрываемых секциях: acquisition, control, signal analysis, averaging, advanced. |

### 6.2. c-spectrum: пять видов, компактная диагностическая боковая панель

| Spectrum | Waveform | Waterfall |
|---|---|---|
| ![Spectrum](https://raw.githubusercontent.com/arkid-lutaj/c-spectrum/main/docs/assets/1-spectrum.png) | ![Waveform](https://raw.githubusercontent.com/arkid-lutaj/c-spectrum/main/docs/assets/2-waveform.png) | ![Waterfall](https://raw.githubusercontent.com/arkid-lutaj/c-spectrum/main/docs/assets/3-waterfall.png) |
| [Открыть](https://github.com/arkid-lutaj/c-spectrum/blob/main/docs/assets/1-spectrum.png) | [Открыть](https://github.com/arkid-lutaj/c-spectrum/blob/main/docs/assets/2-waveform.png) | [Открыть](https://github.com/arkid-lutaj/c-spectrum/blob/main/docs/assets/3-waterfall.png) |

| Envelope | Control Chart |
|---|---|
| ![Envelope](https://raw.githubusercontent.com/arkid-lutaj/c-spectrum/main/docs/assets/4-envelope.png) | ![Control chart](https://raw.githubusercontent.com/arkid-lutaj/c-spectrum/main/docs/assets/5-chart.png) |
| [Открыть](https://github.com/arkid-lutaj/c-spectrum/blob/main/docs/assets/4-envelope.png) | [Открыть](https://github.com/arkid-lutaj/c-spectrum/blob/main/docs/assets/5-chart.png) |

**Не путать графики с настройками:** в c-spectrum большая часть DSP-параметров находится в CLI (**src/main.c**, **src/cs_config.c**): fft N, hop, window, HP, envelope low/high, baseline duration, sigma, EWMA λ, consecutive, adapt, RPM. Поэтому собственную боковую форму MVK нужно строить **по принципам OpenTest**, а не копировать ограниченный c-spectrum GUI.

### 6.3. pySPWB: настоящий PySide6 анализ с инженерными курсорами

| FFT/harmonics | STFT + связанные срезы | Transfer/coherence |
|---|---|---|
| ![pySPWB FFT](https://raw.githubusercontent.com/Charette-AI-Group/pySPWB/main/docs/website/img/fft_harmonics.png) | ![pySPWB TFA](https://raw.githubusercontent.com/Charette-AI-Group/pySPWB/main/docs/website/img/tfa_log_sweep.png) | ![pySPWB Transfer](https://raw.githubusercontent.com/Charette-AI-Group/pySPWB/main/docs/website/img/tf_overview.png) |
| [Открыть](https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/fft_harmonics.png) | [Открыть](https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/tfa_log_sweep.png) | [Открыть](https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/tf_overview.png) |

| Time processing | LMS + сходимость |
|---|---|
| ![Time processing](https://raw.githubusercontent.com/Charette-AI-Group/pySPWB/main/docs/website/img/time_processing_overview.png) | ![LMS](https://raw.githubusercontent.com/Charette-AI-Group/pySPWB/main/docs/website/img/lms_overview.png) |
| [Открыть](https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/time_processing_overview.png) | [Открыть](https://github.com/Charette-AI-Group/pySPWB/blob/main/docs/website/img/lms_overview.png) |

### 6.4. rota-order: принцип карты Кэмпбелла и порядковых срезов (не внедрять до RPM(t))

| Карта частота/RPM | Карта порядок/RPM | Тренд одного порядка |
|---|---|---|
| ![RPM frequency](https://raw.githubusercontent.com/ZhenxianLi/rota-order/main/docs/images/plot_rpm_frequency_map.png) | ![RPM order](https://raw.githubusercontent.com/ZhenxianLi/rota-order/main/docs/images/plot_rpm_order_map.png) | ![Order slice](https://raw.githubusercontent.com/ZhenxianLi/rota-order/main/docs/images/plot_order_slice.png) |
| [Открыть](https://github.com/ZhenxianLi/rota-order/blob/main/docs/images/plot_rpm_frequency_map.png) | [Открыть](https://github.com/ZhenxianLi/rota-order/blob/main/docs/images/plot_rpm_order_map.png) | [Открыть](https://github.com/ZhenxianLi/rota-order/blob/main/docs/images/plot_order_slice.png) |

### 6.5. REI SignalLab: общий вид web-workbench

| Интерфейс | Спектр |
|---|---|
| ![REI interface](https://raw.githubusercontent.com/rootcastleco/rei-signallab/main/docs/images/signallab_real_app_screenshot.png) | ![REI spectrum](https://raw.githubusercontent.com/rootcastleco/rei-signallab/main/docs/images/plot_spectrum.png) |
| [Открыть](https://github.com/rootcastleco/rei-signallab/blob/main/docs/images/signallab_real_app_screenshot.png) | [Открыть](https://github.com/rootcastleco/rei-signallab/blob/main/docs/images/plot_spectrum.png) |

### 6.6. Закрытые профессиональные образцы

- [OROS NVGate FFT Results — настоящий скриншот и настройки](https://wiki.oros.com/index.php?title=File:FFT_results.png): вкладки FFT1–4 / order / 1/n octave / tachometer, подвиды main/profile/waterfall, справа выбранные каналы.
- [DewesoftX — конфигурация order tracking](https://manual.dewesoft.com/x/setupmodule/modules/machinery/ordertracking): source channel, order FFT, time FFT, binning, averaging, spectra vs RPM.
- [DewesoftX — Campbell Widget](https://manual.dewesoft.com/x/measure/viscontrol/vector-matrix-graphs/campbell-plot): отдельные настройки и отображение частота×RPM.
- [Adash DDS](https://adash.com/software-vibration-analysis/digital-diagnostics-system): совместное отображение waveform, FFT, stacked spectra и trend.
- [DREAM 5 ВАСТ — реальные видеоуроки](https://rutube.ru/channel/33303047/): диагностические графики и тренды, но **никаких** карточек/дерева машин в нашем текущем UI.

### Отдельные настройки подключения и список IP профилей

Подключение МВК01 необходимо вынести из главного экрана: компактное имя выбранного профиля и статус в шапке, полный экран с сохранёнными IP/избранными/последними успешными адресами в диалоге. Локальный Ethernet продолжает определяться автоматически; выбор IP не отправляет TCP и не обходит подтверждение оператора. Архитектура Qt QSettings, экраны и тесты: [CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md](CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md).

**Поиск признаков дефектов выделен отдельно:** W32 для выбранного окна реального временного сигнала и A20 для сопоставимых архивных записей. Это два планируемых рабочих экрана, а не то же самое, что W26 (совпадение гармоник) или A10 (общий контроль изменений).

## 7. Рекомендуемая структура MVK Live: что видно без переключений

~~~text
┌ MVK Live | МВК01 IP | Ethernet/TCP/RxPos | [ИЗМЕРИТЬ] [СТОП] [FREEZE] ┐
│  Измерение: [ОБЗОР] [Спектр] [Время] [Расчёты]                         │
│  Анализ окна: [Водопад] [STFT] [Кюртограмма] [Огибающая] [Методы...]  │
│  История: [Тренды] [Сравнение] [Архивный водопад]                     │
├───────────────┬───────────────────────────────┬──────────────────────┤
│ АЦП 1..8      │ [FFT выбранного АЦП]          │ Настройки активного  │
│ [1][2][3][4]  │  спектр с курсорами           │ графика:             │
│ [5][6][7][8]  ├───────────────────────────────┤ Вид/единицы          │
│               │ [ВРЕМЕННОЙ СИГНАЛ]           │ Фильтр / полоса     │
│ RMS / Peak    │  настоящие отсчёты           │ N / df / окно       │
│ Crest/Kurt    │                               │ Ось / курсоры        │
│ Rx + Fs       │ Выделение графика -> 1/2/4   │ [Дополнительно ▾]  │
├───────────────┴───────────────────────────────┴──────────────────────┤
│ СТАТУС: сеанс/ADC/RX/Fs/FRange применён в Go/архив/ошибки            │
└──────────────────────────────────────────────────────────────────────┘
~~~

**Логика:** слева компактные Live-показатели, центр — **одно или два** основных представления, справа контекстный инспектор. Дорогие методы **не** растягивают главный экран — работают по кнопке «Открыть в анализе окна». В истории отдельные даты/источники и свои настройки. Краткие Live-тренды не должны выглядеть как архивная история.

## 8. ЭКРАНЫ НАСТРОЕК МЕТОДОВ — обязательные формы реализации

Все формы имеют пять общих логических секций. Они могут быть раскрываемыми (OpenTest style), а не пятью отдельными окнами.

1. **Источник (Source):** АЦП, timestamp, RxPos/сохранённая запись, Fs, N available, session, ORIGINAL_AUX/APP_DERIVED. Fs/FRange в режиме МВК01 **только для чтения**.
2. **Расчёт (DSP):** *только относящиеся к этому методу* FFT length/window/overlap, filter/nominal band, threshold, averaging; проверить Nyquist до Apply.
3. **Представление (Display):** оси, dB reference, Y, X, цветовая шкала, линейный/log, легенда и курсоры — изменение этих настроек не вызывает повторного TCP.
4. **Действие:** LIVE stream auto или [Рассчитать] для окна, [Применить полосу] или [Экспорт] для анализа, [Добавить к сравнению] для архива. Предупредить, если данных недостаточно.
5. **Происхождение / сохранение:** физические единицы, алгоритм и версия, время, параметры, NPZ/SHA/ORIGINAL, экспорт PNG/CSV/JSON. Статус без вымышленных нулей.

### 8.1. Экран настроек LIVE спектра

~~~text
┌ Спектр · АЦП [1▼] · Fs [8192 Гц read-only] ┐
│ Величина: [ВУ▼] [ВС] [ВП]  Масштаб: [лин./дБ] │
│ Режим: [FFT▼] [Welch PSD] [ASD] [1/3]      │
│ FFT [8192▼]  df = Fs/N (авто)  T=N/Fs (авто) │
│ Окно [Hann▼]  Усреднение [тип▼] [число]      │
│ Фильтр [Без фильтра▼] [готовые 1/1,1/3,2] │
│ X [0..Nyquist] Y [Авто▼]                    │
│ Инструмент [A/B] [пики] [гармоники] [RMS полосы]│
│ [Сохранить NPZ] [График PNG] [Расчёт CSV]    │
└─────────────────────────────────────────────┘
~~~

Если включён ORIGINAL_AUX4700, интерфейс **не** показывает N FFT или настройки окон, которые не влияют на пришедшие аппаратные полосы; на этой странице доступны только view/ADC/история. По исходникам OpenTest разделение input acquisition / signal analysis / averaging / advanced это пять понятных секций, не 20 параметров в одной строке.

### 8.2. Экран настройки осциллограммы

~~~text
┌ Временной сигнал · АЦП [1▼] ┐
│ X [100 мс / 500 мс / 1 с / ...] [A–B]     │
│ Y [Авто / ±X м/с²] [Показать мин/макс]     │
│ Фильтр [Без фильтра / ФВЧ / ФНЧ / полосовой/...]│
│ Полоса [готовая▼] или [Расширенная ▾]     │
│ Freeze: [вкл/выкл] (только отображение)    │
│ [Сохранить реальные отсчёты NPZ]           │
│ Участок A–B: [Посчитать признаки] [FFT] [STFT] │
└───────────────────────────────────────────┘
~~~

При визуальном уменьшении числа точек строить min/max envelope в каждом экранном пикселе (как c-spectrum), а **СКЗ/куртозис рассчитывать по полным физическим отсчётам**, не по прореженной линии.

### 8.3. Экран настройки LIVE водопада + архивного водопада

~~~text
┌ Waterfall / Spectrogram [LIVE / АРХИВ] ┐
│ Источник [ADC] [FFT amplitude / PSD / ASD] │
│ Частота [0..fmax] Кадров [20/50/120/240]  │
│ Y = [время UTC/локальное | реальный кадр] │
│ Палитра [preset▼] Уровни цвета [min/max]  │
│ [клик по кадру] -> FFT этого кадра          │
│ [клик частоты] -> амплитуда этой частоты vs time│
└───────────────────────────────────────────┘
~~~

**Никогда** не выдавать порядковый номер кадра за timestamp, и не подстраивать каждый кадр под собственный maximum без явной команды. Для архива несовместимые Fs/FFT/units показывать раздельно или явно попросить оператора выбрать обработку.

### 8.4. Экран Fast Kurtogram и огибающей (два разных метода)

~~~text
┌ FAST KURTOGRAM PySDKit · АЦП 1 ──────────────────────┐
│ Источник [ОКНО / NPZ] N [4096/8192/16384/32768]     │
│ Дерево [2..6 level с проверкой N]  [РАССЧИТАТЬ]       │
│ ┌────────── частота fc / уровень k ───────────────┐   │
│ │             цветная карта эксцесса SK           │   │
│ │             курсор [fc, Δf, K]                 │   │
│ └─────────────────────────────────────────────────┘   │
│ [Выбрать максимум] [Полоса -> огибающая]                │
├ СПЕКТР ОГИБАЮЩЕЙ -------------------------------------┤
│ Метод [Hilbert сейчас / packet SES в будущем]          │
│ Полоса [low..high, применено из карты] RPM [вручную]    │
│ [FFT c BPFO/BPFI/BSF/FTF] [сводка гармоник/SNR]         │
│ [Экспорт] [Сохранить параметры]                         │
└───────────────────────────────────────────────────────┘
~~~

**Fast Kurtogram** = бинарно-троичный фильтробанк PySDKit/Antoni, каждый score соответствует реальному узлу. **Hilbert-огибающая** = отдельная локальная демодуляция в выбранной полосе. **SES PySDKit** — только будущий дополнительный метод, с собственной нормировкой. Высокий SK сам по себе не диагноз.

### 8.5. Экран STFT / CWT / кепстра / SST

| Метод | Панель входа | DSP-настройки | Результат и инструменты |
|---|---|---|---|
| STFT | ADC и окно NPZ/Live-снимок, Fs | nperseg 256/512/1024/2048/4096, overlap, window, fmax, color dB | Крупная теплокарта + **спектр при t** + **амплитуда при f vs time**, крест-курсор |
| CWT Morlet | ADC, N, Fs | wavelet, 16/24/40/64 scales, min/max f, карта амплитуды | Scalogram, курсор (t,f), цветовая шкала и легенда |
| Кепстр | ADC, N/Fs | window, max quefrency, преобразование log magnitude | Линия амплитуда vs quefrency (с); курсор = 1/q Hz, пояснение |
| SST | ADC/NPZ, Fs | Morlet/bump, scales, thresholds, frequency bounds | Более концентрированная T–F карта, режим R&D |
| IMCKD | ADC/NPZ, Fs | fault period, FIR length, iterations, shift order | Исходный/фильтрованный waveform, correlated kurtosis vs iteration; R&D |
| SRS/PVSS | NPZ acceleration | damping/Q, частотный диапазон, bins per octave, peak definition | SRS vs natural frequency; запись и паспорт расчёта |

### 8.6. Экран расчётных данных и диагностических признаков

~~~text
┌ Расчётные данные ─ АЦП 1 ───────────────────────────────┐
│ [Приборные 43 полосы] [24 позиции] [Локальные]           │
│ Частота/№ | Показатель | Значение | Unit | Source | T   │
│ [выбрали одну строку] -> [Тренд] [Сравнить даты]        │
└──────────────────────────────────────────────────────────┘

┌ Поиск диагностических ПРИЗНАКОВ (не диагноз) ───────────┐
│ Источник: NPZ/T, АЦП, Fs, FFT N, выбранная полоса        │
│ Возможная причина    Подтверждённые линии   Ограничения │
│ 1× / 2× / GMF        f, amplitude, SNR       RPM?        │
│ BPFO/BPFI/BSF/FTF    n гармоник, повтор.    geometry?   │
│ [Открыть конкретный FFT] [Пересчитать] [В историю]       │
└──────────────────────────────────────────────────────────┘
~~~

Приборная таблица не должна получать заголовки «скрытая частота» для 24 неизвестных позиций. Не ставить автоматическое «исправен», «дефект подтверждён» или фальшивый процент вероятности по одной записи. Модель JYD-iBearing основана на исследовательской ML-классификации, а в REI SignalLab встречаются вручную заданные confidence — не промышленный эталон.

### 8.7. Экраны настроек истории, сравнения и EWMA

| Экран | Основные настройки | Обязательные элементы графика |
|---|---|---|
| **Тренды** | ADC, показатель/source, период, UTC/local, f_center/position, допустимые пропуски | Дата по X, значение/единица по Y, A/B курсоры, щелчок открывает фактическую запись |
| **Наложение** | 2–8 дат, один ADC/quantity/unit/method; диапазон f; режим overlay/separate | Легенда всех дат, общая шкала, не смешивать разные Fs/normalization скрыто |
| **Архивный waterfall** | ADC, совместимые записи, Fs, единица, verified timestamps, цветовая шкала, bins | Карта f×time + FFT в выбранное время + trend frequency |
| **EWMA** | выбранный показатель, диапазон обучения baseline, λ, σ, consecutive, dwell, adapt | Линия признака + границы + отметки фактических событий; «Нет сопоставимого baseline» вместо тревоги |
| **Экспорт** | набор активных графиков, таблиц, единиц, source/algorithm/time, PNG/CSV/JSON | Итоговый пакет без изменения оригинальных данных |

### 8.8. Единый менеджер гармоник, боковых полос и кинематических частот

Обязательное дополнение к макетам FFT, осциллограммы, STFT, огибающей, водопада, кюртограммы и архива: [HARMONIC_OVERLAYS_AND_DIAGNOSTIC_METHODS_CATALOG_RU.md](HARMONIC_OVERLAYS_AND_DIAGNOSTIC_METHODS_CATALOG_RU.md).

В нём: 11 добавленных методик по временному окну, 4 LIVE-представления и 5 исторических сравнений, настоящий исходный UI OpenTest для H1..Hn и sidebands, viblearn для частот BPFO/BPFI/BSF/FTF/GMF и коллизий, phonometry для лопастей/двигателя, OROS/Dewesoft/Adash для курсоров, отдельная таблица различий ожидаемая/измеренная частота, допуск, фон и SNR. **Частотные гармоники накладываются только на ось частот; для waveform, cepstrum, Fast Kurtogram, оригинального AUX4700 и временных трендов используются другие физически подходящие инструменты.** Никаких карточек оборудования.

### 8.9. Углублённая диагностика подшипников по огибающей

**Отдельный аудит исходников и экранов:** [BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md). В нём разобраны c-spectrum, viblearn, riya0920, CaringNihilistic, tzarcrept, phonometry, PySDKit и MathWorks, с точными названиями BSF и BDF=2BSF, боковыми BPFI±fr/BDF±FTF, коллизиями BPFO×3/BPFI×2, формами настройки, Local SNR, SES, Autogram, EES/IES и многополосными методами. **Пока это план анализа и диагностики, не подтверждённый заводской алгоритм и не новый готовый диагностический модуль.**

### 8.10. Альтернативные селекторы полос и паспорт данных

**Добавлены W41–W43** — Protrugram, Infogram и Spectral Gini, как альтернативные исследовательские способы выбрать полосу перед FFT огибающей; все требуют реальных ADC samples и рассчитываются только по ОКНУ/NPZ, **не в постоянном LIVE и не из AUX4700**. В [дополнительном аудите](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md) есть сравнение карт, подробные формы настроек, Quality Gate, ограничения NPZ V1, наборы CWRU/Paderborn/IMS/FEMTO/XJTU-SY и актуальность ISO 20816-3:2026. Новых исполняемых методов эти записи не добавляют.

## 9. Какие настройки НЕ доступны пользователю для оригинальных данных МВК01

- Физическая Fs должна определяться по фактическим данным приёмника и структуре канала. Выпадающий список «Fs» может быть демонстрационным в лабораторном тесте, но в Live это **read-only**.
- FRange расшифрован и применяется один раз в Native Go; менять/умножать ещё раз в Qt нельзя.
- 43 оригинальные AUX4700-полосы нельзя выдавать за FFT или «заводской FIR», коэффициенты которого по трём приватным источникам ещё не восстановлены.
- Оригинальное меню из 32 названий фильтров восстановлено; коэффициенты оригинальных фильтров остаются отдельной задачей. Для локального фильтра требуется видимая надпись APP_DERIVED.
- Если нет реального waveform NPZ, возможности Kurtogram/STFT/CWT/SES/SRS/cepstrum следует выключить с пояснением «необходимо сохранённое окно АЦП», а не генерировать из спектральных скаляров.
- Смена ADC, сеанса, frozen/live, NPZ source или физического Fs должна переопределять/инвалидировать методы с привязкой к старым отсчётам. Историю не очищать.

## 10. Рекомендуемый режим доступа по умолчанию

| Где искать в программе | Методы, которые видны по умолчанию | Что только через действие |
|---|---|---|
| **Главный LIVE обзор** | Waveform, FFT, RMS/Peak/Crest, состояние RX, 1/3 OEM по кнопке, краткий тренд | Доп. STFT, Kurtogram, CWT, envelope, mean comparisons — перейти в Анализ окна |
| **LIVE детальные страницы** | FFT, waveform, ORIGINAL AUX4700, 24×3, краткий waterfall и short trend | Применить фильтр, cursors, save window, открытие анализа |
| **Анализ окна** | По выбранному реальному окну: Kurtogram, Hilbert, STFT, CWT, cepstrum, band RMS, bearing/gear markers | [Рассчитать], [Сохранить] и [Подать полосу в огибающую]; SRS/SES/SST/IMCKD позже |
| **История** | Тренды, даты, сравнение совместимых AUX или NPZ | Пересчёт архивного NPZ по любому методу, исторический waterfall и долгосрочный diagnostic evidence |
| **R&D / недоступно до аппаратных доказательств** | Список возможных методов в документации, **не** активные кнопки | Campbell/order tracking, FRF/coherence, orbit/phase/balancing, LMS/noise ref, automatic ML verdict |

## 11. План приёмки и что код реально умеет сегодня

**Подтверждено просмотром исходников ветки:** приложение имеет шесть верхних вкладок и восемь вложенных страниц «Доп. анализ»: водопад, Fast Kurtogram, краткий RMS-тренд, STFT, CWT, кепстр, подшипники, редукторы. Наличие кнопок не означает, что каждый метод работает по сохранённому NPZ через историю; часть дополнительных методов в текущем app.py читает Live Ring.

**Пакет 1 (UX, без изменений RX):** LIVE overview из FFT+waveform, контекстные инспекторы, сетка 1/2/4, полноценная таблица приборных значений и переходы в историю.

**Пакет 2 (взаимодействие):** курсоры A/B, RMS выделенной полосы, STFT 3 связанных графика, waterfall с реальным временем и шкалой, архивные waterfall/recalculate NPZ.

**Пакет 3 (новые численные методы):** SES, centroid, flatness, HF ratio и проверенные тренды, optional SRS/PVSS. Каждому методу собственные тесты с синусом/белым шумом/импульсами/DC/неполным окном.

**Пакет 4 (после данных):** multi-harmonic bearing evidence, EWMA с обучением/устойчивыми источниками, исследовательские SST/IMCKD/cyclostationary карты. Никаких надуманных вероятностей неисправности.

**Не внедрять сейчас:** карточки агрегатов/подшипников/редукторов, класс оборудования с неуказанными нормативами, синтетические результаты под видом физического МВК01, методы с неподтверждённой фазой/RPM(t)/синхронизацией.

**Приёмка:** Windows 1280×720 и 1920×1080 при 100/150% DPI; Live без прибора → NO DATA, никаких 0 или fake samples; смена ADC, Freeze, TCP disconnect, ошибочная частота, NPZ повреждён/SHA mismatch; unit tests для всех DSP и GitHub Actions/Windows EXE; физическая точность по реальному МВК01 **отдельно**. Все боковые экраны настройки доступны через QScrollArea и не уменьшают график до нечитаемого размера.

## 12. Лицензии и границы переноса

- **PySDKit:** MIT; нужное численное ядро Fast Kurtogram находится у нас отдельно с сохранённым [PYSDKIT_LICENSE_MIT.txt](PYSDKIT_LICENSE_MIT.txt). Сторонний Matplotlib-рисовальщик не переносился; Qt изображение собственное.
- **c-spectrum / pySPWB:** MIT, можно изучать и повторять инженерные принципы, непосредственное копирование требует сохранения авторских notices.
- **OpenTest / OpenTest-Plugins:** **OpenTest Community License**, это **не** стандартная permissive лицензия; использовать идеи UI/алгоритмов, код не копировать в продукт без отдельного решения.
- **rota-order / AccelSpectra:** GPL-3, не переносить исходники непосредственно без оценки влияния лицензии.
- **Dewesoft, OROS, Adash, DREAM:** промышленный UX и документация, не открытые кодовые библиотеки.
- **ML и диагностические пороги:** ни программы сторонних разработчиков, ни учебные датасеты не доказывают применимость к конкретному МВК01 без независимой валидации.

## 13. Сопутствующие документы MVK Live

- [UX главного экрана v2](WORKSPACE_V2_OPTIMAL_MAIN_AND_ANALYSIS_RU.md).
- [История / тренды / overlay](HISTORY_TRENDS_OVERLAY_DESIGN_RU.md).
- [OpenTest + c-spectrum + PySDKit аудит](OPEN_SOURCE_VIBRATION_UI_AND_CALC_AUDIT_RU.md).
- [Fast Kurtogram / waterfall / fault evidence](KURTOGRAM_WATERFALL_FAULT_DETECTION_RU.md).
- [Дополнительные методы и исходники](ADVANCED_GRAPHS_METHODS_SOURCE_COMPARISON_RU.md).
- [Гармоники и новые методы диагностики: исходники, настройки, применение к разным графикам](HARMONIC_OVERLAYS_AND_DIAGNOSTIC_METHODS_CATALOG_RU.md).
- [Глубокий аудит подшипников: гармоники спектра огибающей, боковые, BDF и новые методы](BEARING_ENVELOPE_DIAGNOSTICS_AND_OVERLAYS_AUDIT_RU.md).
- [Подключение, список IP и отдельные экраны поиска дефектов](CONNECTION_PROFILES_SETTINGS_AND_FAULT_SEARCH_UX_RU.md).
- [Селекторы Protrugram/Infogram/Gini, качество данных, тестовые датасеты и ISO 2026](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md).
- [Текущий README и фактические возможности](README_RU.md).

**Итог:** основной экран должен быть быстрым живым осциллографом/спектроанализатором, экран анализа окна — лабораторией тяжёлых методов по реальным отсчётам, архив — инструментом истории и верификации. Каждый метод имеет отдельный источник, параметры и экран; не смешивать LIVE, ОКНО и АРХИВ.
