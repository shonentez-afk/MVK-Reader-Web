# MVK Live — углублённый анализ спектра огибающей и поиска дефектов подшипника

Дата: 18.11.2026. Статус: сравнительное исследование и спецификация; **не утверждение о реализованном диагносте**. Не меняем Go RX/TCP, FRange, AUX4700 и не делаем карточек подшипников/редукторов/агрегатов.

## 1. Текущее состояние MVK Live, сверенное с кодом

- [vibration.py](vibration.py): band-pass Butterworth на ускорении → Hilbert abs → удаление постоянной составляющей → FFT огибающей с физическими Hz, аппаратный FRange дополнительно НЕ применяется.
- [kurtogram.py](kurtogram.py): настоящая бинарно-троичная Fast Kurtogram PySDKit с картой полос; выбранная полоса передаётся в локальную Hilbert-огибающую.
- [advanced.py](advanced.py), функция envelope_fault_lines: BPFO/BPFI/BSF/FTF, до 4 гармоник, локальная медиана, допуск max(1.8 df, 1.2% частоты), SNR. Флаг noteworthy срабатывает уже при **ОДНОЙ** линии с SNR >= 6 dB — для поиска дефекта этого недостаточно.
- [app.py](app.py), вкладка «Подшипники»: параметры оборотов, число тел качения, d/D, угол, полоса, NFFT и график огибающей. На отдельном bearing_plot нет полноценного графического слоя BPFO/BPFI, BDF=2BSF, боковых полос, реальных найденных пиков и таблицы SNR; результат выдаётся текстом. На основном FFT отдельные теоретические маркеры уже имеются.
- Основных данных для полноценного анализа архива требует NPZ с реальными ADC samples; 43+24x3 оригинальных AUX4700 не являются сохранённой огибающей.

## 2. Исследованные исходники: метод, параметры и фактические особенности

| Проект | Исходник | Что действительно делает | Что брать |
| --- | --- | --- | --- |
| [c-spectrum](https://github.com/arkid-lutaj/c-spectrum) | [cs_envelope.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c) | BP resonance → **rectification + LPF/decimation**, Hann FFT; 4 гармоники, ±4% tolerance, медианный фон, min 2 harmonic, prominence>=8 и доля уровня>=3%, обороты при наличии. Это НЕ Hilbert-огибающая | Многоступенчатое доказательство вместо одного пика; числа порогов исследовательские, НЕ нормы MVK |
| [viblearn](https://github.com/Liang-Guo-SD/viblearn) | [bearing.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/faults/bearing.py), [markers.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/plotting/markers.py), [diagnostics.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py) | BearingGeometry → частоты; цветные пунктирные H1…Hn и ±tolerance; сравнение с физическими пиками, коллизии между частотными семьями | Графические наложения и раздельные ожидаемые/реальные частоты, отметка неоднозначности |
| [riya0920/bearing-condition-monitoring](https://github.com/riya0920/bearing-condition-monitoring) | [features.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/features.py), [order_tracking.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/order_tracking.py) | FFT Hilbert огибающей в выбранной полосе; гармонический score с весами 1/0.6/0.3, sidebands BPFI ± f_rot, 2BSF; проверяет collision BPFO×3 ≈ BPFI×2 | Учесть важное испытание: деление суммы sidebands на сильный центр дало НЕВЕРНЫЙ результат на реальных CWRU; новый sideband prominence нормируется по фону, но и он требует валидации |
| [CaringNihilistic/bearing-fault-monitor](https://github.com/CaringNihilistic/bearing-fault-monitor) | [frequency_domain.py](https://github.com/CaringNihilistic/bearing-fault-monitor/blob/main/src/bearing_pdm/features/frequency_domain.py), [bearing_physics.py](https://github.com/CaringNihilistic/bearing-fault-monitor/blob/main/src/bearing_pdm/features/bearing_physics.py) | Энергетические показатели огибающей около частот дефектов и гармоник | **Несовместимость обозначений:** здесь автор осознанно называет «BSF» частоту ударов 2×стандартной BSF; в MVK придерживаться истинной BSF, отдельно BDF=2×BSF |
| [tzarcrept/bearing-fault-detection](https://github.com/tzarcrept/bearing-fault-detection) | [features.py](https://github.com/tzarcrept/bearing-fault-detection/blob/main/src/mafaulda/features.py) | BP + Hilbert + FFT, медианный уровень, BPFO/BPFI/FTF/BSF/2BSF, обороты по тахометру; BPFO≈3× и BPFI≈5×shaft на конкретной геометрии | Отдельно маркировать пересечение со shaft harmonics; без тахометра надёжность меньше |
| [phonometry](https://github.com/jmrplens/phonometry) | [diagnostics.py](https://github.com/jmrplens/phonometry/blob/main/src/phonometry/vibration/machinery/diagnostics.py) | FaultFrequencyResult с harmonics(), within(), plot() поверх настоящего envelope spectrum; **BSF и BDF=2BSF разделены** | Модель теоретических семейств, не готовый диагноз |
| [PySDKit](https://github.com/wwhenxuan/PySDKit) | [_kurtogram.py](https://github.com/wwhenxuan/PySDKit/blob/main/pysdkit/utils/_kurtogram.py) | Настоящий Fast Kurtogram для резонансной полосы и комплексной пакетной огибающей | Уже внедрено численное ядро; к найденной полосе добавить отдельный harmonic-evidence анализ |
| [MathWorks / MATLAB](https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html) | [bearingFaultBands options](https://www.mathworks.com/help/predmaint/ref/bearingfaultbands.html), [envspectrum](https://www.mathworks.com/help/signal/ref/envspectrum.html) | Harmonics=[1,3,5], Sidebands=[1,2,3], Width, Domain=frequency/order; двойное отображение спектра с цветными combs; сравнение здоровой/повреждённой записи, batch trends BPFO/BPFI | Лучший образец настройки частотных семей и архивных трендов; MATLAB-код НЕ открыт для копирования в проект |

### Стандартные физические названия, которые должны быть одинаковы во всех наших расчётах

Обозначим f_rot=RPM/60, Z=число тел, d=диаметр тела, D=делительный диаметр, α=контактный угол, r=(d/D) cos α.

- BPFO = Z*f_rot/2*(1-r)
- BPFI = Z*f_rot/2*(1+r)
- FTF = f_rot/2*(1-r)
- BSF = D*f_rot/(2d)*(1-r²)
- **BDF = 2*BSF** (ball defect frequency), часто выраженная линия при повреждении тела качения.

Исходник CaringNihilistic называет последнюю частоту «BSF», прямо пояснив определение. Это не баг реализации того проекта, а опасная несовместимость названий при переносе данных. В MVK нужны **две разные метки**.

## 3. Наложение гармоник ПОВЕРХ FFT огибающей: схема и настройка

| Диагностическая семья | Наносимые теоретические линии | Возможные боковые | Что сравнивать с реальным измерением |
| --- | --- | --- | --- |
| BPFO наружного кольца | BPFO, 2BPFO, 3BPFO… | кандидаты близких shaft harmonics, slip tolerance | независимые пики, local SNR, динамика |
| BPFI внутреннего кольца | BPFI, 2BPFI, 3BPFI… | для nBPFI ±f_rot, ±2f_rot | реальные боковые пики и отношение к собственному фону |
| BSF/BDF тела качения | BSF, **BDF=2BSF**, 2BDF, 3BDF… | nBDF ± FTF, ±2FTF | несколько линий на BDF/гармониках и FTF sidebands |
| FTF сепаратора | FTF, 2FTF, 3FTF… | возможные сложные комбинационные линии | отдельное длинное окно N, нужное разрешение df |
| 1× shaft и другие семьи | 1×,2×,3×, GMF (по необходимости) | разные группы на одном графике | пересечения/коллизии с BPFO/BPFI без двойного подсчёта |

Вспомогательные механические маркеры должны включаться по выбору. Не рисовать одновременно все серии и тысячи ярлыков.

**Четыре разных визуальных объекта:**
1. Тонкий цветной пунктир — рассчитанная геометрическая частота, не измеренный пик.
2. Прозрачная полоса вокруг пунктира — явно выбранная tolerance Hz/%, с учётом df, RPM uncertainty/slip.
3. Маленькая точка/треугольник на линии измеренного спектра — реально найденный peak, клик открывает фактическую f, amplitude, единицу и local SNR.
4. Символ конфликта — один реальный пик подходит нескольким семьям (BPFO×3 ≈ BPFI×2 и другие); не считать два независимых подтверждения.

Геометрия и обороты задаются на экране метода. Источник 1× = MANUAL / принят кандидат ВС; не выдавать за TACH. Отсутствие RPM или d/D/Z означает «не оценено» для этой семьи, не «дефект отсутствует».

## 4. Более глубокие методы, которых ещё нет как самостоятельных в MVK

| Метод | Реализация/основание | Экран настроек | Режим |
| --- | --- | --- | --- |
| **Энергия полос около частот дефектов** (BPFO/BPFI/BDF/FTF + Hn) | [CaringNihilistic frequency_domain.py](https://github.com/CaringNihilistic/bearing-fault-monitor/blob/main/src/bearing_pdm/features/frequency_domain.py), [MathWorks batch](https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html) | диапазон вокруг линии, PSD и energy normalization, Hn, период измерений, background | ОКНО/NPZ, после сохранения — архивный тренд; ПЛАН |
| **Боковой prominence подшипника** (BPFI±1×, BDF±FTF) | [riya features.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/features.py) | carrier, spacing f_rot/FTF, число пар, f_tol, медианный фон, SNR | ОКНО/NPZ, ПЛАН |
| **Многогармоническая проверка** с 2+ линиями, collision-control, local noise | [c-spectrum cs_envelope.c](https://github.com/arkid-lutaj/c-spectrum/blob/main/src/cs_envelope.c), [viblearn diagnostics.py](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/diagnostics.py) | Hn 1..10, Δf, tolerance, min independent lines, local SNR, prominence, interpolation | ОКНО/NPZ; **исправить** текущий однопиковый noteworthy |
| **SES — спектр квадрата огибающей**, рядом с Hilbert | [MathWorks envspectrum](https://www.mathworks.com/help/signal/ref/envspectrum.html); комплексная packet-огибающая [PySDKit](https://github.com/wwhenxuan/PySDKit) | полоса, FFT N, окно, DC removal, нормировка отдельно от Hilbert amplitude | ОКНО/NPZ, ПЛАН |
| **Autogram** — autocorrelation squared envelope по банку полос | [Moshrefzadeh & Fasana, MSSP 2018](https://www.sciencedirect.com/science/article/pii/S0888327017306441) | фильтробанк, lag/период, глубина, показатель повторяемости, selected band | ОКНО/NPZ, R&D; альтернативен SK при импульсных помехах |
| **EES / IES** — интегральная огибающая из cyclic spectral coherence | [MSSP 2020](https://www.sciencedirect.com/science/article/pii/S0888327020300595) | α-range, spectral f, FFT segment/overlap, выбор чувствительной полосы, budget | ОКНО/NPZ, R&D; особенно VFD/EMI, нет готовой версии в MVK |
| **WCES / взвешенная многополосная огибающая** | [Measurement 2022](https://www.sciencedirect.com/science/article/pii/S026322412101335X) | число полос, веса/качество полос, α-f map, масштаб, сравнение с SES | ОКНО/NPZ, R&D |
| **IESCFFOgram** — подбор информативной полосы по кандидатным fault frequencies | [Journal of Sound and Vibration 2022](https://www.sciencedirect.com/science/article/pii/S0022460X22000037) | BPFO/BPFI/BDF hypothesis, α tolerance, spectral band/weights | ОКНО/NPZ, R&D; риск смещения при неверной геометрии |
| **SACA** — spectral auto-correlation, усиление периодического гребня | [MSSP 2013](https://www.sciencedirect.com/science/article/pii/S0888327013003798) | FFT, lag, число итераций, нормировка | ОКНО/NPZ, R&D |
| **Tacholess envelope order tracking** при меняющейся RPM | [riya order_tracking.py](https://github.com/riya0920/bearing-condition-monitoring/blob/main/src/order_tracking.py), [Sensors 2013](https://www.mdpi.com/1424-8220/13/8/10856) | физически проверенная RPM(t), angular-resampling, samples/rev, Hz-band before resampling | УСЛОВНО — отложить, пока нет проверенной RPM(t) |
| **История огибающей и сравнение записей** | [MathWorks batch features](https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html) | ADC, сохранённые NPZ, source/frequency family, одинаковые units/N/band, dates/RPM per record | АРХИВ, ПЛАН |

**Классификация дефектов по этим методам всегда гипотетическая.** Реальные исходники предупреждают о false positives и несовпадении лабораторных CWRU/MAFAULDA данных с оборудованием MVK01; алгоритмы статей не являются подтверждённым готовым ПО для копирования.

## 5. Предлагаемый отдельный экран «Подшипники / Огибающая»

~~~text
┌ Подшипники · Огибающая / Кюртограмма / Гармоники / Боковые / Признаки ┐
│ Источник [АЦП 1 / Freeze / NPZ] Fs/N/UTC/APP_DERIVED               │
├───────────────────────────────────────┬─────────────────────────────┤
│ FFT ОГИБАЮЩЕЙ в физических Гц         │ Параметры выбранного метода │
│ ^ реальный peak   ┆ расчётный BPFO   │ RPM [ручной/принятый 1×]   │
│       ┆ BPFO  2BPFO  3BPFO           │ Z, d, D, угол             │
│       ┆ BPFI±fr                     │ [✓ BPFO][✓ BPFI][✓ BDF]   │
│       ┆ BDF±FTF                     │ [✓ FTF][ ] BSF             │
│       график с курсорами и допуском  │ H1..H10, ±k, tolerance    │
│                                       │ [Найти пики] [Сохранить]   │
├ ТАБЛИЦА ──────────────────────────────┴─────────────────────────────┤
│ Семья/Hn | f теор. | f измер. | ΔHz | Ампл./ед | SNR | Коллизия    │
├ ПРОВЕРКА ПРИЗНАКОВ ────────────────────────────────────────────────┤
│ Не оценено / Недостаточно / Признаки / Не найдено в данном окне      │
│ [Временная огибающая] [Сравнить несколько записей] [История]         │
└─────────────────────────────────────────────────────────────────────┘
~~~

**Контекстные формы:**
- «Огибающая»: resonance band из PySDKit или вручную, метод Hilbert/будущий SES, FFT N, окно, fmax, физические units.
- «Гармоники»: выбираемые семейства BPFO/BPFI/BSF/BDF/FTF, H1…H10, допуски, флажок «Показать реальный пик», min-2 test.
- «Боковые»: carrier = BPFI или BDF, spacing = f_rot или FTF, пары ±1…±6, local SNR/коллизии.
- «Признаки»: полная таблица с фактическими значениями и статусами, не общая «вероятность неисправности».
- «История»: NPZ по датам, повторяемость, сравнение 2–8 огибающих, тренд harmonic/floor/sideband и сохранённых настроек.

Настоящие изображения и эталонные формы: [Diagnostics 101 с цветными маркерами](https://www.mdpi.com/2076-3417/10/20/7302), [MathWorks алгоритм и графики](https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html), [MathWorks настройки Harmonics/Sidebands/Width/Domain](https://www.mathworks.com/help/predmaint/ref/bearingfaultbands.html), [viblearn plot_fault_markers](https://github.com/Liang-Guo-SD/viblearn/blob/main/src/viblearn/plotting/markers.py).

**Дополнительное исследование:** [Protrugram, Infogram, спектральный индекс Gini, качество измерения и эталонные датасеты](BAND_SELECTION_DATA_QUALITY_VALIDATION_STANDARDS_2026_RU.md). Эти методы лишь выбирают резонансную полосу, не заменяют поиск измеренных гармоник BPFO/BPFI/BDF/FTF и пока не реализованы в MVK Live.

## 6. Приёмка и приоритет

**P0:** отдельные реальные линии и точки на bearing_plot, BSF vs 2BSF/BDF, BPFI±f_rot, BDF±FTF, таблица f_nom/f_measured/SNR/collision, доказательство из нескольких гармоник вместо single noteworthy. Удерживать исходные ADC/NPZ/Fs/filter и не вводить скрытых данных.

**P1:** SES, band-energy features, sideband prominence, сравнение 2-3 реально доступных резонансных полос, архивные тренды огибающей.

**P2/R&D:** Autogram, CSCoh/EES/IES, WCES, IESCFFOgram, SACA и envelope order tracking (последний только при подтверждённой RPM(t)). Не выдавать числа учебных порогов за промышленные нормативы.

**Тесты:** чистые BPFO/BPFI/BDF/FTF с 2–5 гармониками и боковыми, коллизия BPFO×3 vs BPFI×2, целочисленная shaft-гармоника, шум/EMI/одиночный удар, отсутствие RPM/геометрии, короткое окно, Nyquist, неверный Fs, разные спектральные единицы и коэффициенты, переключение АЦП, архив с неполными данными. Независимая проверка реальных сигналов МВК01 обязательна перед автоматическими выводами.

**Вывод:** отдельная страница огибающей должна показывать измеренные пики, диагностические семьи и неоднозначности, а не только текстовые значения SNR или вертикали из формул.
