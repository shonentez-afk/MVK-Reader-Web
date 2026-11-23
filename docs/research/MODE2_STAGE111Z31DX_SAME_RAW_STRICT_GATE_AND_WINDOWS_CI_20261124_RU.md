# Stage111Z31DX — единая приёмка same-RAW: строгий файловый gate и Windows Qt CI

**Дата:** 24.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Никакого изменения main, сетевых команд прибора, Go-приёмника, DSP и интерфейсных меню этим пакетом.**

## Подтверждено по оригинальной базе функций

Локально прочитан `mvk_idr(1).sqlite` (в GitHub не выгружен). Восстановленные вызовы `TMvkChannelStorage.GetSpectrum` по адресу `007D13D4`:

- `007D1426` → `CheckDataAvailability`
- `007D146A` → `GetAdjustedEnvelopeLength`
- `007D14D0` → `007D1C48`, `007D14E9` → `007D1E70` — ветви FIR
- `007D16D7`, `007D1761`, `007D1796` → `007D2164` — шаги интегрирования
- `007D1910` → `FreeMem`

Индекс исходника `_Unit115.pas` указан в каждой строке; индекс — подтверждение структурного пути вызовов, **не** аппаратное подтверждение результата. Частные `Projects.7z`, `mvkview.idp`, SQLite не публиковались. Исходная коррекция PRE-FIR `bSpecLines`→POST-FIR FFT N/Fs остаётся без изменения.

## Исправлен P0 недостаток строгой приёмки

`mvk_compatible/core/original_mode2_paired_acceptance.py` теперь имеет отдельный флаг CLI `--require-complete-same-raw`. Ранее по умолчанию 0 возвращался при побайтовом совпадении даже единственной пары файлов, хотя это **не** завершённый full-cycle gate.

Строгий режим (exit 0 только при полном наборе):
- обе локальные копии одинакового ненулевого TCP RAW, потоковый SHA/байтовое сравнение;
- присутствуют pre-Hann, windowed, complex FFT, power, postmode power и Y;
- явно представлены четыре уникальных оригинальных Tag0..3 Y, postmode Power Tag2 и Tag3;
- ADC BIN, TSXML, VALUES и TABLE присутствуют и все заявленные пары побайтово идентичны.

Если хоть один пункт отсутствует, различается либо RAW не совпадает, строгий CLI возвращает **exit 3**. Старый режим сравнений сохраняет прежнюю семантику. Дополнительные поля ответа: `strict_same_raw_file_evidence_complete`, `strict_same_raw_is_physical_attestation=false`. Этот флаг означает **только полноту сравнения переданных файлов**; подлинность оригинального Win32 запуска, реальную сессию прибора, x87, FRange, правильность операторских файлов и Stop он НЕ подтверждает. Даже идеальное сравнение оставляет `original_hardware_parity_verified=false` и `original_1_to_1_release_gate_passed=false`.

Добавлены три synthetic regression-теста: неполный, но побайтово равный набор обязан падать в strict; полный синтетический набор проходит strict, но не аппаратную аттестацию; один изменённый Tag0 Y ломает gate.

## Разобран упавший CI нового FIR/FFT

Actions [#45233871699](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45233871699) для `aa3dd2ef` завершён FAILURE: Linux Core SUCCESS, Go RX/export SUCCESS, Windows native QPA/DPI SUCCESS, Windows Core **2934 passed/15 skipped**, далее старый smoke Qt **58 passed, 1 failed** (`test_qt_stage111f_spectrum_envelope_requires_private_profile`). В тесте `test_desktop_qt.py:259` сравнивалось старое `APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE` с фактическим новым `SOURCE_SELECTED_GETSPECTRUM_FIR_IQ_IDR_CANDIDATE`. Это **регрессия тестового ожидания**, не установленный численный DSP-дефект. Тест исправлен на source-selected контракт и дополнен проверками `original_source_fft_plan.post_fir_fft_n` и `post_fir_sample_rate_hz`. Дальнейший CI/EXE требуется проверять по **новому кодовому SHA**, а не прежнему `aa3dd2ef`.

## Реально открыто

Не существует подтверждённой одной и той же физической MVK01/оригинальной Win32 сессии на всех стадиях: `IP → Измерить → Task2 → RX → GetSignal/GetSpectrum → Hann → FFT → Power → 4 режима → WriteData/WriteValues → Stop`. На одних только synthetic CI и статическом индексе функций нельзя выдать 100% паритет. Нужны локальные подлинные одинаковые RX и stage Float32 capture с original Win32, их проверка данным компаратором и отдельная операторская аттестация исходного прибора, а также 7 страниц/3 формы и GDI/курсор. Отдельные BIN/TSXML/VALUES/TABLE из разных замеров нельзя подменять одним same-run эталоном.

**Не вводить изменения в настоящий МВК01 без разрешения оператора. Приватные файлы не коммитить.**
