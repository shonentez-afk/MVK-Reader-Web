# Каталог тестов и контрольных материалов

Этот индекс обновлять при **каждой** новой тестовой программе, диагностическом скрипте и эталонном наборе.

| Путь | Назначение | Статус |
|---|---|---|
| `tools/tcp10230_passive_test/` | Подключение к TCP/10230 без прикладных команд, ограниченный приём | **Ожидает реального теста** |
| `tools/modbus_calibration_test/` | Только FC03: считывание 17 групп калибровочных регистров | Реальные результаты по двум приборам получены ранее |
| `protocol/mvk_calibration.py` | Безсетевой CDAB float32 и преобразование raw*gain | Код опубликован, проверка в CI не настроена |
| `protocol/test_mvk_calibration.py` | Модульные тесты декодирования коэффициентов | Есть в GitHub |
| `MVK_Reader_Web/tests/` | Тесты основной программы предыдущих версий | Перенесены из исходного пакета |
| `MVK_Reader_Web/CHECK_PC.py` | Локальная проверка Windows среды | Перенесён |
| `MVK_Reader_Web/pcap_session_compare.py` | Анализ PCAPNG/соединений | Перенесён |

## Добавление нового теста
1. Поместить исполняемый файл в `tools/<name>/` (полевой инструмент) или `MVK_Reader_Web/tests/` (автоматизированный тест).
2. Добавить README: назначение, команда запуска для Windows CMD и при необходимости Termux, требуемые библиотеки, разрешённые сетевые действия, таймауты, ожидаемые файлы отчёта.
3. Указать `offline`, `read-only network` или `requires device access`.
4. Добавить минимальный обезличенный фикстурный набор и ожидаемый результат, если возможно.
5. Зафиксировать версию/commit и результаты в `docs/TEST_RUNS_RU.md`.

## Внешние эталонные данные
Реальные PCAPNG/BIN/TSXML и JSON опросов могут содержать технические данные предприятия. Не добавлять их целиком в Git без отдельного разрешения/обезличивания. Сохранять описание и SHA256 в `docs/CAPTURE_MANIFEST_TEMPLATE.csv`, сами файлы — в закрытом хранилище вне Git.


## Stage79 (2026-10-28)
`tools/research/stage79_verify_tsxml_idr.py` — offline-only статическая проверка опор генерации TSXML по оригинальным `_Unit125.pas`, опционально `_Unit128.pas`. Пример: `python tools/research/stage79_verify_tsxml_idr.py _Unit125.pas --unit128 _Unit128.pas`. Скрипт ничего не пишет в сеть; нужен локальный IDR, не публикуемый в GitHub. 23/23 структурных маркера вручную проверены по листингу; проверка связки с реальным BIN открыта.

- `tools/research/stage79c_verify_bin_open.py` — offline-only статические проверки чтения TSXML, fallback и открытия BIN (вход: оригинальный `_Unit128.pas`, без сети/оборудования). Запуск: `python tools/research/stage79c_verify_bin_open.py _Unit128.pas`. Результаты адресной ручной перепроверки: 18/18 строковых опор.

- `tools/research/stage80_verify_storage_signal.py`: offline IDR static verification (14/14 anchors) of `_Unit115.pas`; run `python tools/research/stage80_verify_storage_signal.py _Unit115.pas`.

- `tools/research/stage80b_verify_bin_fft_chain.py` — только офлайн, исходные `_Unit128.pas` и `_Unit115.pas`; проверяет 14 статических опор пути BIN/FFT. Запуск `python tools/research/stage80b_verify_bin_fft_chain.py _Unit128.pas _Unit115.pas`. Никакой сети.

- `tools/research/stage80c_verify_normalization.py` — offline-only, требует оригинальные `_Unit128.pas` и `_Unit115.pas`: `python tools/research/stage80c_verify_normalization.py _Unit128.pas _Unit115.pas`. Проверяет 11 адресных инвариантов нормировки; без сетевых операций.

- `tools/research/stage81_verify_spectrum_modes.py` — offline IDR verification of `_Unit115.pas`, 17 anchors; run `python tools/research/stage81_verify_spectrum_modes.py _Unit115.pas`. No devices/network.

- `tools/research/stage81b_verify_fft_primitives.py` — offline static IDR verifier (16/16 markers); invoke `python tools/research/stage81b_verify_fft_primitives.py _Unit115.pas`. No device/network access.

- `tools/research/stage81c_verify_idr.py`: offline, original `_Unit115.pas`, check 6/6 static groups. Run: `python tools/research/stage81c_verify_idr.py _Unit115.pas`.
- `tools/research/stage81c_numeric_selftest.py`: offline synthetic window RMS and frequency transform; run: `python tools/research/stage81c_numeric_selftest.py`. This is not a real-data regression.

- `tools/research/stage81d_verify_fft_backend.py` — offline structural IDR check, 15 anchors for FFT core and dB output; command: `python tools/research/stage81d_verify_fft_backend.py _Unit115.pas`. No network/device operations.

- `tools/research/stage81e_numeric_candidate.py` — offline NumPy synthetic FFT test at N=256,1024,8192; `python tools/research/stage81e_numeric_candidate.py`. Does not validate genuine MVKView archives.

- `tools/research/stage81f_candidate_clone_audit.py` — офлайн аудит кандидата (4 исходных Python-файла), синтаксис и контрольные инварианты. Запуск: `python tools/research/stage81f_candidate_clone_audit.py <каталог_копии>`. Отсутствие настоящих валидационных файлов отражается как OPEN/FAIL, не как результат измерения. Сеть не используется.

- `tools/research/stage82_archive_fft_candidate.py` — offline BIN+TSXML candidate FFT (NumPy); requires no device, output local CSV (not original MVKView export). `python tools/research/stage82_archive_fft_candidate.py --bin RECORD.bin --tsxml RECORD.bin.tsxml --n 8192 --out CHECK.csv`.
- `tools/research/stage82_archive_fft_selftest.py` — offline synthetic BIN+TSXML regression, `python tools/research/stage82_archive_fft_selftest.py`; executable check pending independent CI report.

- `tools/research/stage83_compare_spectra.py`: offline strict spectrum comparator, requires candidate and reference CSV, provenance manifest; no interpolation or device IO.
- `tools/research/stage83_compare_selftest.py`: synthetic-only tests for matching data, mismatch and incompatible frequency grids; run `python tools/research/stage83_compare_selftest.py`.

- `tools/research/stage86_verify_values_time.py` checks five original `_Unit125.pas` IDR anchor groups for VALUES wall-clock timestamp, independent BIN/VALUES start, and TSXML current date; run `python tools/research/stage86_verify_values_time.py _Unit125.pas` (offline).

- Stage89 real archive validation scripts `validate_stage89.py` and `low_time.py` with 129-band JSON and Russian report supplied in `stage89_validation_package.zip` in conversation; private recordings not published. GitHub report `docs/research/STAGE89_REAL_43_BAND_VALIDATION_RU.md`.


Stage90 2026-10-29: independently re-aggregated Stage89 129 real MVK43 band results. Median per-band absolute relative error across all 43 bands vs reference >=0.001 m/s2 vs >=0.01 m/s2: ADC1 6.69/3.38/3.16%, ADC3 7.90/6.75/5.85%, ADC6 10.49/5.51/4.78%. Thus tiny denominator strongly affects global percent error, but high mismatches at significant reference levels remain: ADC1 16Hz 228%, 25Hz 144%; ADC3 40Hz 147%; ADC6 31.5Hz 141%. Stream boundary mismatches are channel-dependent; no evidence one universal off-by-one. Evidence docs/research/STAGE90_LOW_REFERENCE_AND_BAND_BOUNDARIES_RU.md, reproducible stage90_audit_package.zip attached in conversation. Next Stage91 inspect real BIN tonal peaks near these edges and half-record changes. PCAP excluded (different session), stable v0.3.40 unchanged.
