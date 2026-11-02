# Stage111Z29C2 — исходный FRange до FIR огибающей: реализация и независимая проверка

Дата: 02.11.2026. Ветка: research/stage111-mvkview-desktop-20261029.
Точный проверяемый SOURCE SHA: `5cbb0d69adf904160df33e41d55f58a56b3daceb`.
**CODE + Linux Core + Windows Core/Qt CI VERIFIED; Go/PyInstaller Windows EXE артефакт проверяется отдельно. Реальный Win32 GetSignal/FIR/same-run numeric parity ещё НЕ достигнут.**

## 1. Не повторять Stage111J, Stage52 и оригинальный FFT

Original float-ring FRange division before RemoveMean/FIR/FFT уже SOURCE-VERIFIED 29 октября: `_Unit115:007D14A5 → 007D2228(flag=1) → 007D22A1..22D4` (Stage111J). Исходное `Single(ring/FRange)` штатно восстановлено для *обычного спектра* в `core/storage_f_range_idr_candidate.py::prepare_original_fft_input`. Старый тест FFT N262144 131072/131072 побитово и GetSpectrum Tag0 summary 3/3 уже приняты по одной операторской паре. [Результаты повторной проверки Stage29R](STAGE111Z29_PRIOR_ORIGINAL_COMPARISONS_REAUDIT_RU.md).

В Stage111Z29C1 оставалась не новая неизвестная исходная операция, а интеграция **того же** проверенного helper в ветвь огибающей. У Native R6 BIN по умолчанию calibrated_bin; нельзя автоматически принимать его за внутреннее float-ring оригинального Delphi. source_data/gain не изменять.

## 2. Фактические изменения

- `core/envelope_spectrum_idr_candidate.py`: добавлен явный `input_domain`; `original_float_storage` применяет `Single(BIN/FRange)` через существующий Stage111J-helper ДО единственного RemoveMean и FIR. По умолчанию calibrated_bin передаёт исходные Float32 без деления. После FIR повторного DC нет; FFT/интеграции Tag0–3/summary не переписаны.
- Дополнительно хранятся SHA256 реальных исходных BIN-отсчётов до нормализации, Float32 после выбранного read-domain ДО RemoveMean/FIR и отдельный прежний Float32 после FIR перед Hann. Наличие трёх отпечатков локализует расхождения без раскрытия массива. Флаги `original_source_buffer_provenance_verified=false`, `calibrated_native_bin_is_original_storage_verified=false`, `original_delphi_numerical_parity_verified=false` сохраняются.
- `core/offline_export.py::OfflineSession.spectrum_envelope()` принимает и передаёт домен; структура Native RAW, 19 output files, аудиты и калиброванные BIN не меняются.
- `desktop/main_window.py`: исследовательский ComboBox source-domain теперь работает с огибающей при локальном original-IDP. GUI явно предупреждает, что original_float_storage — гипотеза, что /FRange идёт ДО FIR; запрещённый без проверенного локального IDP случай не изменён.
- `reference_compare.py` и `triplet_reference_compare.py`: ранее реализованные CSV/Copy-same-window локальные CLI принимают оба явных домена для кода огибающей 1..31 и всех четырёх режимов. Это инструменты диагностики, не новые оригинальные данные.
- Новый `private_getspectrum_prefft_envelope_compare.py`: read-only локальный сравнитель original **prepared** Float32 `before_fft(1).bin` против реконструированного pre-Hann массива после source-domain/DC/FIR. Требуются SHA-audited Native ZIP, локально SHA-проверенный оригинальный IDP, исходный Win32 дамп и независимо установленные ADC/источник/N/EnvelopeCode/FRange/точный старт окна. Печатает только SHA, число точных Float32, ULP агрегаты, не пути/коэффициенты/сырой сигнал. Программа не подключается к прибору и не подбирает параметры.

## 3. QA и границы

Только SYNTHETIC public CI: 4/4 spectrum modes, нормализация до FIR, default no double FRange, same-window SHA/pre-FFT SHA, original-mode vs заранее нормализованная цепочка, изменения CLI CSV/Copy для Tag0–3, защита от неверного/недостаточного BIN/NaN/пустых исходных дампов, one-ULP mutation, Qt переключение и отсутствие IDP.

[GitHub Actions #41420012495](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41420012495): Linux Core **1149 passed, 5 skipped, 30 subtests**, Windows Core **1152 passed, 2 skipped, 30 subtests**, Windows Qt **49 passed**. Сборка EXE/Go — проверить отдельно по этому же исходному SHA.

## 4. Старый оригинальный дамп — используем только доказанные сведения

В Stage111Z8 пользователь уже сохранил `before_fft(1).bin` N262144 SHA256 `9832b04ced202b793533823a2ec8d14c38971568c6e3cbd446eb2d7101d70d2d` и `after_power(1).bin` N/2; 131072/131072 битовая идентичность исходного FFT ДЕЙСТВИТЕЛЬНО подтверждена на одном случае. Не нужно просить их переснять. Но в старом manifest отсутствуют код огибающей `[EBX+08]`, точное время начала, ADC/FRange/Float-ring тип и подтверждение одного исходного сеанса. `before_fft` — это **не возвращённый GetSignal буфер**, а уже подготовленная к FFT последовательность. Пока эти метаданные не подтверждены, исходный FIR/огибающую и GetSignal нельзя сертифицировать по Z8 задним числом.

Для проверки existing local original дампа: `python -m mvk_compatible.private_getspectrum_prefft_envelope_compare --help`. Используются только локальные файлы и обязательные параметры; оригинальный IDP, BIN и дампы не загружаются в GitHub.

## 5. Что дальше

Stage29C2 **SOURCE/CODE/CORE-Qt CI CLOSED**, real original runtime Data Gate OPEN. Следующий Stage30 должен затронуть только НЕДОСТАЮЩИЕ оригинальные full after-mode массивы Tag1/2/3, x87 различия при неизвестном режиме и full same-run spectrum comparison. Stage29B original GetSignal RETURN, Stage26C long live 65536/262144, Stage31 pixel parity и Stage27B same-run original/native BIN также OPEN. Не повторять Stage111J, Z2, Z8, Z10, Z13/14 или уже проверенные реальные исходные FIR-банки.

Stable main/Web untouched; никаких оригинальных EXE/IDP/PAS/DFM/BIN/RAW/PCAPNG/PNG в GitHub или CI.