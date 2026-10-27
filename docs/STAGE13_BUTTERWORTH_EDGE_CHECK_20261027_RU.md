# Stage13: Проверка хвоста фильтра 10–3000 Гц, 27.10.2026

## Метод
Офлайн-анализ исходных BIN АЦП4 (33.75390625 с) и АЦП6 (61.0390625 с), fs=65536 Гц, BIN уже в м/с². Оценка полной periodogram PSD (boxcar, DC detrend), затем интеграл PSD умноженной на |H(f)|² для цифрового полосового фильтра Баттерворта 10–3000 Гц с SOS коэффициентами scipy.signal.butter. Нулевой фазовый фильтр sosfiltfilt **не** использован; оценивался эквивалент одиночного прохода по модулю АЧХ. Результат экспериментальной модели, не идентификация реализации MVKView.

| Модель | ADC4 RMS | ADC6 RMS |
|---|---:|---:|
| Идеальная 10–3000 Гц | 4.366532 | 2.860116 |
| Butterworth 1 порядок | 4.301261 | 5.791687 |
| Butterworth 2 порядок | 4.362733 | 4.091008 |
| Butterworth 3 порядок | 4.365510 | 3.538408 |
| Butterworth 4 порядок | 4.365593 | 3.317422 |
| Butterworth 5 порядок | 4.365856 | 3.202403 |
| Butterworth 6 порядок | 4.366173 | 3.131429 |
| Butterworth 8 порядок | 4.366629 | 3.047991 |

Текущие контрольные медианы MVKView VALUES: ADC4 4.376, ADC6 3.5385 м/с². Третий порядок практически воспроизводит обе медианы (ADC4 −0.24%, ADC6 ≈−0.003% по значениям), **но порядок выбран после просмотра результатов**, и источники записаны в разное время. Это подгонка гипотезы к наблюдению, а не независимая проверка реальной АЧХ. Надо независимо установить фильтры по руководству/коду или протестировать на другой записи без подбора.

Особенно большая высокочастотная энергия у ADC6 объясняет чувствительность полосового RMS к плавному спаду после 3000 Гц; у ADC4 это почти незаметно. Гипотеза дефекта ADC6 не доказана. Дополнительные сетевые подключения к устройствам не выполнялись. Основная v0.3.40 не изменялась.

## Cross-band check on both channels, 27.10.2026

The order-3 model chosen from ADC6 10-3000 was held fixed and applied without order retuning to **three bands** (10-1000, 10-2000, 10-3000 Hz) for ADC4 and ADC6. Frequency-domain PSD weighted by single-pass digital Butterworth bandpass magnitude squared, fs=65536 Hz. Each full BIN was used with DC detrend and boxcar periodogram. MVKView reference is the median of all numeric rows in the supplied VALUES CSV, not synchronized to BIN windows.

| Channel | Band Hz | Our ideal PSD | Butterworth order 3 | VALUES median | Relative error of model |
|---|---|---:|---:|---:|---:|
| ADC4 | 10-1000 | 4.00938 | 3.94265 | 3.9470 | -0.11% |
| ADC4 | 10-2000 | 4.31449 | 4.28796 | 4.3000 | -0.28% |
| ADC4 | 10-3000 | 4.36653 | 4.36551 | 4.3760 | -0.24% |
| ADC6 | 10-1000 | 1.67366 | 1.63067 | 1.6265 | +0.26% |
| ADC6 | 10-2000 | 1.91781 | 2.20639 | 2.1990 | +0.34% |
| ADC6 | 10-3000 | 2.86012 | 3.53841 | 3.5370 | +0.04% |

**Independent dimensions but not independent tuning dataset:** order 3 was originally selected after seeing ADC6 10-3000, so that cell is training/tuning evidence. Agreement in other bands and ADC4 adds out-of-target support, but both recordings were available during the hypothesis development, and this is not a prospective blind validation. Actual filter topology (including zero-phase or causal implementation) remains unknown.

Split-half robustness for 10-3000 order-3: ADC4 first/second = 4.37211/4.35889; ADC6 first/second = 3.51578/3.56091 m/s2. VALUES source medians are not time-matched to these halves; do not use split-half as strict validation of MVKView windows.

Conclusion: six bands reproduce medians within 0.35%. Strong evidence for **some Butterworth-like gradual rolloff**, not proof of the instrument's exact order or implementation. Do not change production code/filter until cross-validated on new independent recordings or supported by vendor documentation.
