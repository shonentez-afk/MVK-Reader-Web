> **STAGE111I — ФИНАЛЬНАЯ ОФЛАЙН-ПРОВЕРКА (2026-10-29):** [GitHub Actions #40871387647](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40871387647) завершён **SUCCESS** на исходном коммите `89a00244e75666385d0deb1791a27a1549effd35`. Linux Core **261/261 PASS**, Windows Core **261/261 PASS**, Windows Qt **10/10 PASS**. Windows PyInstaller **MVKViewCompatible_Stage111_PREVIEW.exe** и SHA256SUMS опубликованы; artifact `MVKViewCompatible_Stage111_Windows_Preview`, ID **12895893161**, ZIP **66 500 611 байт**, истекает **12.11.2026 12:16:51 UTC**. Все тесты synthetic/offline; идентичность с оригинальной работающей MVKView на тех же BIN/FRange/окне **НЕ ПРИНЯТА**, прибор не подключался. SHA артефакта и окончательный статус зафиксированы; дальнейшие изменения этих документов не меняют проверенную кодовую сборку.

# Stage111I — FRange Single, исходный порядок суммы мощности, численная и текстовая сверка MVKView

**Дата:** 29.10.2026. **Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. Программа — самостоятельный Windows Qt Desktop `mvk_compatible/`, **без сервера**, без соединения с прибором. **Исследовательский кандидат; полного оригинального Delphi parity ещё нет.**

## 1. Что подтверждено по реальному оригинальному коду

Из приватных `Projects.7z` и `mvkview.idp` (публичные исходные артефакты не загружались) выборочно сверены инструкции:

| Функция и IDR-адрес | Реально подтверждено | Практическое следствие |
|---|---|---|
| `TMvkChannelStorage.Create 007D0A61` | Поле `TMvkChannelStorage.FRange:Single` при создании заполняется битами `3F800000` (1.0) | **Начальное** значение, не сертификат коэффициента конкретного канала/архива |
| `ProcessBufferChunk 007D23D1–007D23E5` | Есть ветка `ApplyRange`, умножающая входные сохранённые float32 на FRange | Нельзя автоматически заключать, были ли сохранённые BIN уже масштабированы |
| `007D2228 / 007D22C8` | Отдельная ветка чтения буфера выполняет деление на FRange | Контекст выбранного пути чтения и точная калибровка требуют анализа исходного режима данных |
| `GetSignal 007D0D8F / 007D0DD2` | На выходе может умножать на FRange | Для амплитуды нужно учитывать источник и число преобразований |
| `GetSpectrum 007D1667 / 007D16F1 / 007D17B0 / 007D185A / 007D18F9` | Режимы и интегральные/пиковые значения используют поле `FRange:Single` | FRange должен быть явным численным входом при сравнении оригинального FFT |
| `GetNarrowbandValue 007D0FF0 / 007D109F` | Результат узкой полосы и шумового пика масштабируется FRange | Источник AUX4700 при этом **НЕ заменяется** |
| `GetSpectrum 007D1807–007D1810` | Полосовая сумма мощности: `fld qword accumulator; fadd Single[k]; fstp qword` **на каждом бине** | `np.sum` с pairwise-редукцией — другой порядок округления |

**Критическое ограничение:** физическая калибровка `FRange` для записанных BIN и конкретного датчика оригинальной MVKView пока **не получена**. Попытки автоматически подобрать множитель под выходные данные могут скрыть ошибки FFT, поэтому автоматическая подгонка НЕ выполняется. Статус `DEFAULT_ONE_NOT_CALIBRATION_VERIFIED` специально отличается от `OPERATOR_SUPPLIED_UNVERIFIED`.

## 2. Реальные изменения исходного кода

- `mvk_compatible/core/calibration_candidate.py`: общий `resolve_f_range`; допустим только положительный конечный Delphi `Single` (float32), ноль, переполнение, потеря в ноль и нечисловые параметры отвергаются; источник оператора протоколируется.
- `mvk_compatible/core/offline_export.py`: необязательный явный `f_range` для `spectrum_for_zip`, `OfflineSession.spectrum`, `pixel_spectrum_cursor`, `compare_fft_backends`, `narrowband` и `spectrum_envelope`. Обычный BIN FFT для режимов 1/2/3 умножает амплитуды на коэффициент **один раз**, `GetSpectrum.OutputMean`/`OutputPeakY` также используют коэффициент; логарифмический график режим 0 от коэффициента не меняется, однако физические суммарные уровни — меняются, как по оригинальному коду. Протокол включает `f_range_used`, `f_range_source`, `original_f_range_verified=false`.
- `mvk_compatible/core/narrowband_idr_candidate.py` и `envelope_spectrum_idr_candidate.py`: отдельные прямые функции также не допускают не представимых как Single значений; никаких silent Inf.
- `mvk_compatible/core/spectrum_metrics_idr_candidate.py`: исправлено накопление исходной мощности **по одному бину** с сохранением `float64` после каждого сложения; ранее использовалась парная векторная редукция NumPy. Поле `power_sum_order=DELPHI_STEPWISE_F64_STORED`; это более точная реконструкция порядка операций, **но x87-битовый parity ещё не проверен**.
- `mvk_compatible/reference_compare.py`: теперь сравнивает не только спектр огибающей (code 1..31 + приватный IDP), но и **обычный оригинальный локальный FFT (code 0)** на том же BIN. Обязательна точная FFT-сетка, запрещена интерполяция; `--f-range` вводится явно, в отчёте есть источник; `diagnostic_reference_over_candidate_gain_hint_not_applied` лишь объясняет, похожи ли ошибки на постоянный коэффициент, но **не пересчитывает** результат.
- `mvk_compatible/triplet_reference_compare.py`: для трёх оригинальных Copy-полей отдельно проверяет абсолютные/относительные численные ошибки и **совпадение текста** (TAB, запятая, `007B2090`-кандидат). `--require-display-text` завершает сравнение кодом 1, если текст не совпал, даже при совпадении чисел. Исходный TXT остаётся локальным, отчёт содержит только SHA и расхождения.
- `mvk_compatible/desktop/main_window.py`: в исследовательском разделе вкладки «Спектр» есть редактируемый `FRange` с предупреждением о неизвестной калибровке. Действует для обычного FFT, FFT огибающей, пиков и узкополосного анализа, не меняет BIN/VALUES/AUX. Добавлена кнопка **«Сверить 3 поля с MVKView…»**: явно выбранный локальный TXT оригинального Copy, три разницы и exact-text флаг; не отправляет данные, не утверждает полное совпадение.

## 3. Специальный тест точности суммирования

На **искусственном** массиве мощности `Nfft=262144`, один бин порядка `1e16` и остальные единичные, два метода дают разные результаты:

| Накопление | Различие от последовательной float64-суммы |
|---|---|
| `np.sum` с pairwise reduction | около **102 388** единиц мощности |
| Последовательное `fadd Single → fstp qword` (исходный IDR) | **0** в выбранном сравнении |

Это **не измерение прибора**, а намеренно сложный тест округления. Исходный qword storage подтверждён, но полный x87 регистр/форматирование/деление RTL ещё требуют оригинального эталона.

## 4. Тестирование и ограничения

Расширены тесты `test_f_range_calibration_candidate.py`, `test_reference_compare.py`, `test_triplet_reference_compare.py`, `test_spectrum_metrics_idr_candidate.py` и Windows offscreen Qt. Проверяются: Default vs operator provenance, mode0 vs 1/2/3, no double range, float32 representability, direct narrowband and original IDP envelope, отсутствие изменения DSP, локальные CSV/TXT сравнения и код отказа при несовпадении текста. Публичный GitHub содержит **только синтетические тестовые данные**. Последние фактические числа PASS указываются ниже после полностью завершённого GitHub Actions (не угадывать по предыдущему Stage).

**Никаких настоящих оригинальных результатов Copy/FFT на подтверждённо одинаковой записи и настройках пока не получено**. Поэтому `original_delphi_parity_verified=false` остаётся даже когда все синтетические тесты PASS и TXT совпадает.

## 5. Запуск настоящей сверки без исходного сервера

Обычный спектр (без огибающей, примеры имён файлов условные):
```powershell
python -m mvk_compatible.reference_compare --archive "C:\private\session.zip" --reference "C:\private\mvkview-spectrum.csv" --channel 4 --code 0 --n-fft 4096 --mode 1 --start-s 0 --backend idr_float32 --f-range 1 --decimal "," --delimiter ";" --report-json "C:\private\fullfft_diff.json"
python -m mvk_compatible.triplet_reference_compare --archive "C:\private\session.zip" --reference "C:\private\mvkview-copy.txt" --channel 4 --n-fft 4096 --mode 1 --start-s 0 --f-range 1 --require-display-text --report-json "C:\private\copy_diff.json"
```
Значение `--f-range 1` в примерах означает **только гипотезу для диагностического сравнения**, не установленную калибровку. Нельзя использовать численные совпадения без проверки одного и того же BIN, канала, источника калибровки, FFT N, физического окна/смещения, оригинального mode, источника копирования и версии MVKView.

## 6. Следующий Stage111J

1. Найти или получить **частный эталон оригинального MVKView** на тождественном полном BIN/TSXML: спектр, 3 TAB поля, входные параметры и положение окна. Анализировать найденные расхождения, а не произвольно настраивать масштаб.
2. Восстановить точную зависимость `FRange` от путей исходного Delphi буфера/датчика: `ProcessBufferChunk`, `007D2228`, архив/live, отображение и калькуляция.
3. Восстановить `TQGrapher` real pixel rectangle, масштаб и `CursorString` через скриншоты оригинала и x87/RTL `FormatFloat`.
4. Дальше — полная визуальная и функциональная приёмка 3 вкладок, затем Archive и Live только через один Native R6.1 Collector **по отдельному разрешению**.

**Следующий чат:** читать оба ADR, `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md`, этот Stage111I отчёт, матрицу и код `mvk_compatible/`. Стабильные `main`/v0.3.40 не менять; никаких команд прибору, никаких производственных BIN/IDP/PAS/DFM/PCAP в публичном GitHub.
