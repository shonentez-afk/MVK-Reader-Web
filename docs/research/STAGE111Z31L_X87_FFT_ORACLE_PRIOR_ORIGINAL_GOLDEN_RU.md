# Stage111Z31L — независимый x87 FFT и сохранение уже принятого реального golden

**Дата:** 05.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Scope:** только СПЕКТР и его численная совместимость с оригинальной MVKView; страницы, временной сигнал, приборное ПО, Web/main не меняются.

## 1. Исправлено историческое упущение — настоящая FFT сверка УЖЕ была

При повторной проверке [Stage111Z8](STAGE111Z8_FIRST_NONZERO_ORIGINAL_FFT_262144_BITWISE_GOLDEN_RU.md) и [Stage111Z22](STAGE111Z22_ORIGINAL_FFT_MEMORY_PAIR_INDEPENDENT_REFERENCE_RU.md) обнаружено, что формулировка Stage31K «входное оригинальное FFT→Power ещё не было проверено на одной реальной паре» **неверна**:

- **30.10.2026** пользователь передал операторские ненулевые original-runtime-claimed `before_fft(1).bin` (262144 Float32, SHA256 `9832b04ced202b793533823a2ec8d14c38971568c6e3cbd446eb2d7101d70d2d`) и `after_power(1).bin` (131072 Float32, SHA256 `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`).
- Существующий `mvk_compatible/private_getspectrum_raw_pair_compare.py` вычислил **131072/131072 full Float32 power bitwise exact** собственным `idr_float32`, `remove_dc=False` из этой original-operator-claimed пары. Изменение twiddle single-store приводило только к 4068/131072; NumPy DOUBLE FFT совпало лишь 733/131072.
- Стадия **Stage111Z8 — принята как numerical CASE-SPECIFIC оригинальный golden**. Отсутствует независимая криптографическая привязка исходных bin к одному Win32 process/thread/call, другим каналам и N. Не объявлять универсальный оригинальный FFT паритет.
- В текущем чате приватные исходные `before_fft(1)`/`after_power(1)` не приложены; есть `Projects.7z` и `mvkview.idp`. Повторно проверять старый реальный capture нечем и **не нужно**. Уже имеющиеся исторические агрегаты/хеши сохранены, оригинальные бин-данные НЕ публиковались.

Отчёт [Stage111Z31K](STAGE111Z31K_SPECTRUM_CALCULATION_AUDIT_RU.md) исправлен: больше не требует повторного StageZ8. Новый диагностический `core/original_spectrum_independent_check.py::compare_source_idr_fft_capture_pair` остаётся дополнительным исследовательским инструментом; **каноническая историческая приёмка** — существующий `private_getspectrum_raw_pair_compare.py`.

## 2. Что дополнительно сделал Stage111Z31L

По исходному приватному operator-provided `Projects.7z/_Unit115.pas` изучил арифметическую структуру оригинала (в GitHub original PAS/DFM/EXE/IDP не переносились):

- `007D205A..007D2080` — `Single` вход × `Single` Hann table, `FSTP Single` в комплексный вход FFT; положительный Unnormalized FFT.
- `007CC198..007CC3F8` — bit reversal, radix-2, `Sin` при `Single` угле из `2*pi/m`, `alpha=2*sin²(angle/2)`, `beta=sin(angle)`, `Single` twiddle stores и `Single` butterfly output, positive angle.
- `007D2095..007D20B1` — `FSTP Single(Re²+Im²)` N/2; никаких дополнительных DC removal, low-bin-zero или интегрирования внутри этого этапа.
- Окно `N262144` берётся из `Single` source-derived периодической Hann/RMS таблицы `262144` с шагом `262144/N`.

Создал **полностью независимую от Python исследовательскую C/x87 реализацию** `tools/research/fft_x87_reference_stage111z31l.c`. Она без сети, файлов прибора, Qt и proprietary coefficient assets; получает ровно N входных подготовленных Float32 из stdin, считает Hann+FFT+полный Power на x87 с `CW=0x1372`, выдаёт только N/2 бинарных powers на stdout. Никакого изменения штатного FFT-бэкенда нет.

Добавлен `mvk_compatible/tests/test_stage111z31l_fft_x87_source_oracle.py`:
- Вход — **только публичная синтетика**, детерминированный LCG `uint32` без платформенной зависимости trig/PRNG, хранение Float32 битов без мутации.
- Полные ожидаемые SHA256 мощности, независимо полученные C/x87, проверяются против существующего `idr_power_spectrum(remove_dc=False)` для `N=1024,2048,4096,16384,65536,262144`. Всего **175616/175616** Float32 выходных бинов без разницы на этих шести наборах.
- Под Linux x86 CI дополнительно компилирует независимую C-схему `cc -O2 -std=gnu11 -ffp-contract=off -fno-fast-math` и сравнивает **все** Float32 C/Python для N=1024,4096,262144. На Windows тесты полного SHA выполняются как Python-only, GNU C/x87 компиляция осознанно пропускается.
- Локально дополнительно проверены гармонические и seeded random Float32 синтетические входы на N до 262144; для 262144 Float32 мощности рассчитаны побитово одинаково независимыми источниками. **Синтетическое совпадение НЕ является новой оригинальной runtime приёмкой.**

**SHA полного N262144 синтетического Float32 Power C/x87**: `84f2b70dad10d5bf507ef2e7bae46d8987e77442e26ea52044eae852f4969237`. Это отпечаток открытого синтетического сценария, НЕ исходного пользователя.

Ранее Stage111Z31K уже подтвердил независимой x87 реализацией всю модель 262144 коэффициентов периодического Hann (`df10f6ab747656aefaeb17dee2764dd552e80cb738a5390108b8943615398069` SHA256), 4 из которых измерены в настоящем оригинальном процессе. Переопределения FFT коэффициентов или новые патчи под результат не делались.

## 3. Проверенный GitHub CI и EXE

**Тестированный код SHA:** `738f04975b3fa4bc22da1801d0e4a06f75520b14`.

[GitHub Actions #41982404277](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41982404277) **3/3 JOB SUCCESS**:

| Gate | Подтверждено |
|---|---:|
| Linux Core | 1418 passed, 44 skipped, 1 warning, 30 subtests |
| Windows Core | 1455 passed, 7 skipped, 1 warning, 30 subtests |
| Windows Qt | 49 passed |
| Windows measured DPR=1.5 Qt | 37 passed |
| Go Native R6.1 source test/build; PyInstaller PE/SHA verify | SUCCESS |

[Windows EXE artifact #13394786722](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41982404277/artifacts/13394786722), ZIP **68 547 910 bytes**, SHA256 ZIP `21cc817f70c4ec97585dbd5d7046c806e9e126f0c4004587938ab40df0b46eea`; embedded `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256 `ef3b10d9c234c8ccd3653e77014d7c2827ba9f47ffe81e15ea3fb851f21bf0f3`; expires **19.11.2026**. Новая C/x87 исследовательская программа — отдельный исходный oracle, **не подменяет штатную программу и не обязана входить в EXE**.

## 4. Что дальше — всё ещё только СПЕКТР

**Закрыто в имеющихся original-case data:** StageZ8 original-claimed N262144 preFFT→Power **131072/131072**; StageZ30 original captured Power→display Y по **131072/131072** в каждом Tag0, Tag1, Tag2, Tag3, с 3/3 summary HEX на каждый mode. Эти результаты НЕ терять и НЕ повторять бесконечно.

**Не закрыто:** другие оригинальные N/Fs/ADC/archive window identity, режим огибающей и original same-run FIR/IQ, корректная связь original BIN/TSXML→input после FRange, независимая аутентификация operator source snapshots; **TQGrapher original runtime GDI Font/PPI/PixelRect и 1:1 screenshot, cursor/zoom/pan/clipboard/export**. Без этого нельзя объявлять полную копию спектра.

**Stage111Z31M — следующий приоритет:** больше не переписывать математику подтверждённого N262144. Продолжить восстановление **оригинального GDI/TCanvas physical pixel и точного графического спектра** по уже предоставленному original экрану/DFM, при этом отдельно сохранить открытые gate для новых оригинальных N/архивных окон и envelope. После полного СПЕКТРА — временной сигнал/GetSignal, затем расчётные данные и лишь потом страницы.

**Приватность:** operator `Projects.7z`, `mvkview.idp`, `before_fft`, `after_power`, Power/Y, оригинальные screenshots/EXE/PAS/DFM и архивы в GitHub/CI не загружались.
