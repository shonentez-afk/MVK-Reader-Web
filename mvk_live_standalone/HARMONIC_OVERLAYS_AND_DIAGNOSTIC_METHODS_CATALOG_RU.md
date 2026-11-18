# MVK Live — дополнительные диагностические методы и наложение гармоник

**Исследование: 18.11.2026.** Ветка feature/mvk-live-standalone-20261117. Это спецификация, не реализованный код. Дополнение к [общему каталогу](FULL_VIBRATION_METHODS_REALTIME_RECORDINGS_SETTINGS_SCREENS_RU.md). Карточки агрегатов, подшипников и редукторов НЕ СОЗДАВАТЬ.

## 1. Проверенные исходники и оригинальные UI-примеры

| Программа | Исходники/документация | Как устроены маркеры |
|---|---|---|
| [OpenTest](https://github.com/crysound/OpenTest) | [harmonic-order-dialog.vue](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/dashboard/harmonic-order/harmonic-order-dialog.vue), [cursor-settings-dialog.vue](https://github.com/crysound/OpenTest/blob/main/apps/frontend/src/modules/shared/data-graph/components/chart-tools/cursor-view/cursor-settings-dialog.vue) | Выбор H1..Hn, drag selection, настройка f0 и предпросмотр всех частот; боковая группа задаётся отдельно через f_center, delta и число пар |
| [viblearn](https://github.com/Liang-Guo-SD/viblearn) | [plotting/markers.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/plotting/markers.py), [bearing.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/faults/bearing.py), [gear.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/faults/gear.py), [diagnostics.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py) | Вертикальные пунктирные линии, собственный цвет семьи, Hn, допуск ±Hz как полупрозрачная область; список совпадений и КОЛЛИЗИЙ, когда один пик подпадает под несколько гипотез |
| [phonometry](https://github.com/jmrplens/phonometry) | [diagnostics.py](https://github.com/jmrplens/phonometry/blob/main/src/phonometry/vibration/machinery/diagnostics.py) | Формулы и семейства вращения, bearing, gear, motor, blade; harmonics/within/plot над measured envelope; вращающиеся blade–vane лопастные моды НЕ рисуются как отдельные ложные частоты |
| [OROS NVGate](https://wiki.oros.com/index.php?title=NVGate_Marker) | [Sideband/Envelope UI](https://wiki.oros.com/index.php?title=NVGate_Envelope_analysis) | Harmonic, sideband, kinematic, free/peak и power-band markers; Starting frequency, Delta, bands left/right, interpolation, привязка к одной/нескольким трассам |
| [DewesoftX](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers) | [Harmonic](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/harmonic-marker), [Sideband](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/sideband-marker), [2D markers](https://manual.dewesoft.com/x/measure/displaydesign/viscontrol/graph2d) | Мышью двигаем фундаментальную, все Hn следуют; Snap/bin, поиск пика в области, 3-точечная интерполяция, Current value/Full history, таблица ID/f/Y, sidebands ±kDelta |
| [Adash DDS](https://adashamerica.com/documents/DDS/Adash-DDS-software-manual.pdf) | [Find Harmonics Families](https://adash.com/support/tutorial-videos/how-to-decode-fft-using-families-function/) | Single, Harmonic, Sideband, Periodic waveform, Delta RMS, Peak, Band; автоматический поиск семейства, повторное нажатие ищет следующие |
| [MVK Live сейчас](app.py) | [app.py:_update_markers](app.py), [advanced.py:envelope_fault_lines](advanced.py), [vibration.py:bearing_frequency_markers](vibration.py) | Серые вертикальные пунктирные 1×..5×, BPFO/BPFI/BSF/FTF, GMF и несколько боковых по принятой 1×; поиск SNR в огибающей существует, но до сих пор НЕ реализован полноценный менеджер семей/таблица совпадений и коллизий |

**Лицензии:** OpenTest Community License — UX только; phonometry MIT; PySDKit MIT с сохранённой лицензией; закрытые Dewesoft/OROS/Adash — ссылки и принципы, не чужие исходники. Код третьих сторон в этом документе не переносился.

**Графические примеры с настоящих экранов:** [Dewesoft H1–H4 + таблица](https://manual.dewesoft.com/assets/img/pro_marker_harmonic.png), [FFT с гармониками и боковыми одновременно](https://dewesoft.com/applications/fft-analyzer), [Adash families](https://adash.com/support/tutorial-videos/how-to-decode-fft-using-families-function/), [OROS sideband marker](https://wiki.oros.com/index.php?title=NVGate_Envelope_analysis).

## 2. Универсальный редактор гармонических семейств — проект UI

~~~text
┌ Маркеры выбранного графика — АЦП 1, FFT, APP_DERIVED ─────────────────┐
│ [+ Гармоники] [+ Боковые] [+ Подшипник] [+ Редуктор] [+ Лопасти]    │
│ Основная частота: [Ручная / Принятая 1× из ВС / Выбрать пик]        │
│ f0 [25.0 Гц] или RPM [1500.0]  Источник [MANUAL]                    │
│ Показать [✓ H1][✓ H2][✓ H3][✓ H4][✓ H5][ ] H6…H12                  │
│ Режим [Прогноз частоты / Проверить измеренные пики]                 │
│ Поиск пика в допуске [предел с учётом Δf и RPM]  интерпол. [нет/да] │
│ Частотные семьи [✓1×] [ ]BPFO [ ]BPFI [ ]BSF [ ]FTF [ ]GMF [ ]BPF   │
│ [Скрыть все] [Найти гармоники] [Следующее семейство]                 │
├ FFT ────────────────────────────────────────────────────────────────┤
│     1×┆       2×┆       3×┆         BPFO┆      2BPFO┆             │
│    измеренный FFT:      ^             ^          ^                │
├ Таблица ────────────────────────────────────────────────────────────┤
│ Семья | Hn | f_ожидаемая | f_пик | ΔHz | допуск | уровень | SNR | ? │
│ Коллизия: один пик подходит BPFO×3 и иной семье → НЕ 2 находки      │
└─────────────────────────────────────────────────────────────────────┘
~~~

Установка: правая боковая панель выбранного графика с пятью общими секциями Источник / Расчёт / Отображение / Действие / Происхождение. Команда контекстного меню на спектре «Добавить семейство…» открывает только настройки этого вида. Из OpenTest — многовыбор Hn; из Dewesoft/OROS — source current curve vs selected compatible traces, вручную f0 или channel value, peak search и таблица. Все параметры семейств можно свернуть.

**Математические позиции, не диагноз:**

- Shaft: f_rot = RPM / 60; Hn = n × f0.
- Gear: GMF = зубьев × f_rot; около m × GMF показывать m × GMF ± k × f_mod (для вала обычно f_mod=f_rot). Ожидаемые боковые отделить от реально найденных.
- Bearing: BPFO, BPFI, BSF, FTF по подтверждённой геометрии и 1×; отдельные H1..Hn для каждой семьи. При BPFI проверять возможные ±k × f_rot как опциональную модель модуляции; без доказательств не выдавать за дефект внутреннего кольца.
- Blades: BPF = число лопастей × f_rot, 2BPF, 3BPF; число лопастей вручную **на этой странице**, без карточек вентилятора. Взаимодействие с направляющими лопатками не генерирует дополнительные произвольные линии из числа лепестков.
- Electrical rotor slots / supply lines: ТОЛЬКО при вручную подтверждённых электрических параметрах; отсутствие токового канала исключает полноценную MCSA.
- Не выходить за Nyquist/полосу; прогнозируемая частота может присутствовать без измеренного пика. Так и писать «Ожидаемая частота; пик не подтверждён».

**Подтверждение физического измеренного пика:** измеренная частота, амплитуда/единица, локальный шумовой фон и SNR считаются из **полной FFT**, не из прореженного plot downsampling. Допуск включает реальную Δf, неопределённость RPM и выбранную оператором относительную границу. Уже существующий в MVK допуск max(1.8 Δf, 1.2% f0) использовать только как тестовый ориентир, не универсальное правило. Peak interpolation должна быть явно подписана. Если один пик совпадает с несколькими семействами, фиксировать COLLISION и не считать двойным подтверждением. Отсутствующие наблюдения сохранять null, а не подставлять 0. Оценка по одной линии НЕ является диагнозом.

**Строка MarkerObservation:** family_id, Hn, nominal_hz, measured_peak_hz|null, tolerance_hz, amplitude+unit|null, local_snr_db|null, collision_group|null, source_adc, source_record/NPZ_SHA, session, UTC, Fs, nfft, normalization, filter, rpm_origin, APP_DERIVED.

## 3. Как физически правильно класть гармоники поверх разных графиков

| Тип графика | Наложение | Запрещённая подмена |
|---|---|---|
| FFT ВУ/ВС/ВП; Welch PSD/ASD | Вертикальные линии f0, Hn, GMF, BPF; обнаруженный пик — отдельная точка, band RMS — полупрозрачная область между f1 и f2 | Не суммировать PSD как FFT RMS, не считать пунктир измерением |
| Hilbert envelope / будущий SES | Вертикали BPFO/BPFI/BSF/FTF и их Hn; боковые, local-noise floor и таблица 2+ гармоник; отдельно фактическая точка | Не искать гармоники в прогнозе без физического спектра |
| STFT/CWT (X=time, Y=frequency) | ГОРИЗОНТАЛЬНЫЕ линии для постоянной f; при настоящей RPM(t) кривые f_n(t), курсор t → спектр, курсор f → тренд | Не вертикали из обычного FFT; CWT не эталонный FFT RMS |
| Waterfall (X=frequency, Y=time) | ВЕРТИКАЛЬНЫЕ линии постоянной f; динамические кривые при проверенной RPM(t). При перестановке осей маркеры перестраиваются | Один ручной RPM не становится временной траекторией RPM(t) |
| Waveform x(t) | ПЕРИОДИЧЕСКИЕ временные курсоры: T=1/f0, t0+kT; отсчёты ударов, A/B задержка | Нельзя наносить Hz как координату X-времени |
| Autocorrelation R(lag) | Линии задержки T, 2T, 3T в секундах, подписи 1/T Hz | Нельзя выдавать корреляционный период за отдельный спектральный пик |
| Cepstrum (quefrency) | Метки q0=1/Δf для ШАГА семейства спектральных пиков, k×q0 | Не переносить f0 Hz напрямую на ось кэфренции, секунды |
| Fast Kurtogram | Выбранная ЯЧЕЙКА fc/BW/SK, передача полосы в Hilbert envelope; семейства показывать в связанном спектре огибающей | H1..Hn на карте SK как на обычном FFT не рисовать |
| Оригинальная третьоктава AUX4700 | Подсветить целую 1/3-полосу, в которую попадает f0, с реальными границами | 43 значения по полосам не равны FFT-пикам |
| AUX4700 24 позиции | Нет гармонических маркеров, только исходный № позиции и значение | Частотное назначение позиций пока не доказано |
| Тренды (X=дата) | Тренд амплитуды выбранных гармоник по реально сохранённым NPZ/спектрам | Не наносить частоты Hz на календарную ось |
| 2–8 дат overlay | Семья должна быть привязана к каждому источнику/RPM/количеству зубьев; легенда дат + f номинальная/наблюдаемая | Не навешивать одну RPM на все записи без проверки |
| Campbell / order maps (условно) | В RPM–Hz наклонная линия f=n RPM/60; в RPM–order горизонтальная n; в time–Hz кривые RPM(t) | Без подтверждённой RPM(t) не активировать |

## 4. Экраны настроек для каждого маркера

**Гармоники:** Source=Manual/Accepted RPM/Selected peak (verified tach disabled), f0, выбранные H1..H12, show theoretical/detected, интерполяция peak, поиск следующего семейства, tolerance, cap Nyquist.

**Боковые:** Carrier=selected peak/GMF/2GMF/any f, Delta=rotation/other verified modulation/manual, number of ±pairs 1..6, around which GMF harmonics, show brackets, pair SNR/energy ratio, таблица center and left/right.

**Подшипник:** source ADC, RPM/manual-accepted, число тел, ball d, pitch D, угол, вид огибающей/Hilbert/SES, number Hn, optional BPFI±1×, локальный фон, допуск с учётом FFT и slip, collision marking. Ввод геометрии только здесь; не создаём карточку.

**Редуктор:** RPM/manual-accepted, число зубьев, carrier GMF, mesh H1..Hn, sideband spacing/number, matched peaks and local SNR, интегральный sideband index. Один GMF не означает повреждение зубьев.

**Вентилятор:** число лопастей, подтверждённый RPM, guide vane count только при нужной физической модели, BPF and harmonics, по каким FFT/PSD смотреть. Изменение BPF не равно диагнозу без сравнимых записей и режима.

**Поиск маркера:** right-panel table with Hn, f_nom, f_meas, Δ, tolerance, rms/psd unit, SNR, source; hover highlights only selected. Histogram of frequency mismatches can be an archive plot; не наслаивать много подписей на сам FFT.

## 5. Дополнительные методы из исходников и литературы — куда их включить

| Метод | Экран и основное вычисление | Настройки | Режим | Источник и статус |
|---|---|---|---|---|
| Wavelet Packet Decomposition/энергия полос | WPD панель коэффициентов/столбцы относительных энергий и куртозиса | wavelet db4/sym5/coif3, глубина, normalization, ROI | ОКНО, NPZ | [bearing-feature repository](https://github.com/Dingding1996/bearing-fault-diagnosis), [wavelet example](https://github.com/rajeevfee/Wavelet-Based-Bearing-Fault-Diagnosis); ПЛАН |
| EMD и VMD | IMF/моды в нескольких строках, огибающая каждого режима, сравнение | max IMF, VMD K/alpha/tau/init/tolerance, выбор IMF | ОКНО/NPZ | [CWRU decomposition.py](https://github.com/akshatverma1602/Signal-Processing-on-CWRU-Bearing-Dataset/blob/main/decomposition.py); ПЛАН |
| Cepstral pre-whitening | Spectrum before/after + SES после очистки | liftering/log smoothing/window/band; верность фазы и шума | ОКНО/NPZ | [MSSP study](https://www.sciencedirect.com/science/article/pii/S0888327012003950); ПЛАН/R&D |
| Teager–Kaiser energy operator | Ψ[x[n]]=x[n]²−x[n−1]x[n+1]; TKEO waveform/FFT | выбранная полоса, предварительная фильтрация, норма, артефакты шума | ОКНО/NPZ | [ISA study](https://www.sciencedirect.com/science/article/pii/S0019057812002005); ПЛАН, алгоритм написать самостоятельно |
| Spectral entropy | Результат Shannon entropy из распределения PSD + тренд | freq band, PSD resolution, window, normalisation; silence handling | ОКНО/NPZ → архив | [Dingding bearing source](https://github.com/Dingding1996/bearing-fault-diagnosis); ПЛАН |
| Многогармоническое подтверждение + коллизии | Спектр + таблица ожидаемых и найденных Hn, collision groups | число гармоник, RPM, tolerance, local floor, min supporting n | ОКНО/NPZ, тренд | [viblearn diagnostics](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py), [c-spectrum](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c); ПЛАН |
| Gear sideband energy ratio / SI | FFT с GMF±k×speed и график суммарной боковой энергии | carrier, modulation, число боковых, band/normalisation | ОКНО/NPZ → архив | [NREL report](https://docs.nrel.gov/docs/fy12osti/54530.pdf), [JSV ISER](https://www.sciencedirect.com/science/article/pii/S0022460X20305423); ПЛАН; режим RPM/load важен |
| AM/FM demodulation inspection | Hilbert analytical amplitude and derivative of phase → time/Hz, modulation spectrum | resonance filter, phase unwrap, minimum amplitude gate, noise rejection | ОКНО/NPZ | [planetary gearbox study](https://onlinelibrary.wiley.com/doi/10.1155/2017/6565237); ПЛАН/R&D |
| Peak width / damping marker | Peak f1/f2, bandwidth and Q only on suitable FRF/resonance | threshold dB, interpolation, curve/source kind | ОКНО, FRF условно | [Dewesoft damping](https://manual.dewesoft.com/x/setupmodule/modules/general/processing-markers/2d-3d-markers/damping-marker); измеренная ширина допустима, физическая ζ без FRF НЕ доступна |
| Periodic impulse events | Детектор ударов на waveform + распределение интервалов | amplitude/SNR threshold, deadtime, local baseline, min repeats | ОКНО/NPZ | [c-spectrum monitor](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_monitor.c), [enDAQ shock](https://github.com/MideTechnology/endaq-python/blob/main/endaq/calc/shock.py); ПЛАН |
| TSA | Синхронно усреднённый waveform и остаток, spectrum | подтверждённая RPM(t)/shaft phase, resampling/angle bins | УСЛОВНО, архив | [pyvib diagnosis example](https://github.com/andrek10/bearing-vibration-diagnostics-toolbox/blob/master/examples/diagnosis.py), [TSA reference](https://github.com/matlab/matlab-agentic-toolkit/blob/main/skills-catalog/control-systems/matlab-extract-rotating-machinery-features/references/tsa.md); ОТЛОЖЕНО |

**Остаются вне проекта до проверки данных:** order tracking/Campbell с физическим RPM(t), Bode/FRF/phase/coherence, X–Y orbit, балансировка, MCSA (требует электрический ток), нейросетевые диагнозы без обучения и независимой проверки. Исходный FRange не менять; всё новое APP_DERIVED.

### Что добавляется в историю

- Тренд амплитуды выбранной гармоники H1/H2/H3, частот BPFO/BPFI/BSF/FTF, GMF/sidebands/BPF — **только** из реально сохранённых совместимых спектров или NPZ.
- Тренд SNR/energy sidebands, количество подтверждённых гармоник; пропуски при отсутствии пика не равны нулю.
- Сравнение спектров 2–8 дат с независимым RPM-source и таблицей matching/collisions.
- История изменений по сопоставимым скоростям/нагрузкам, если нагрузка/RPM реально сохранена; без карточек машин.
- Матрица повторяемости предсказанных частот на нескольких датах с явными источниками. Это перечень гипотез, не автоматические окончательные диагнозы.

## 6. Ограничения и численные тесты для будущей реализации

1. Синтетические сигналы с fshaft=25 Hz: H1..H5, зубья=20 (GMF=500 Hz), fGMF±25/50/75 Hz; проверять границы Nyquist, шкалы Hz/log и Peak/RMS.
2. В FFT прогнозируемые H2 и реально найденный пик различаются объектами. Если пик не найден — null; тест совпадения одного пика с двумя гипотезами фиксирует collision, а не 2 дефекта.
3. Водафолл с (time,frequency) и (frequency,time) — гармонические линии меняют ориентацию; STFT t/f cursor и частотные линии физически осмысленны. Cepstrum — только quefrency 1/spacing.
4. У кюртограммы выделяется РЕАЛЬНАЯ ячейка банка PySDKit и её диапазон; на карту не наносятся фальшивые линии BPFO как на FFT.
5. Для оригинального AUX4700 43 полос нельзя выдавать маркер f0 за разрешённый отдельный FFT пик; 24 позиции нельзя называть частотными линиями.
6. Проверять ADC/RxPos/session/UTC/Fs/N/units; результаты старого сеанса не остаются «живыми». Никаких дополнительных TCP-запросов/дополнительного FRange.
7. Пик и локальный SNR брать по полным непрореженным данным; для удобства интерфейса рисовать только допустимое число overlay линий. Все графические семьи включаются и выключаются независимо.
8. Контроль реального устройства, реальных помех/скачков и разных RPM отдельно от CI. Синтетические совпадения не доказывают диагностической точности.

**Приоритет:** сначала менеджер гармоник/боковых/кинематических линий FFT+огибающая с таблицей и настройками; затем перенести линии в STFT/waterfall и period-cursors в waveform; затем сделать архивные тренды этих семейств и новые оконные методы. Оригинальную логику приёма и карточки оборудования не затрагивать.
