> **19.11.2026 — ФИНАЛЬНАЯ ПРОГРАММНАЯ ПРИЁМКА FIR/source ring:** код [`f1d88fc`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/f1d88fc024e633c67b74b371169fdf466c62c4d4) — [Actions #44436325996](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44436325996), **5/5 PASS**: Linux Go source ring/RAW/export, Linux Core 2486, Windows Core/Qt 2722, Windows QPA DPI100/150, автономный Windows EXE 69 433 230 байт до 03.12.2026. Исправлены неправильные тестовые ожидания старой FIR-истории (`GetSignal` Code20: 20мс HTag → 1310+51=1361 входных → 655 выходных), точные оригинальные пункты `bSpecLines` и временной курсор. Численный оригинальный Delphi/x87 и живой FIR GetSignal остаются НЕ принятыми; `original_delphi_compatibility_verified=false`. Это подтверждение локальной реализации, не аппаратный 1:1.

# Единая цепочка MVK01 LIVE: bSpecLines (pre-FIR) → исходное кольцо Go → I/Q FIR → FFT

Дата 19.11.2026. Ветка research/stage111-mvkview-desktop-20261029.
**Не путать источник расчёта с оригинальным численным паритетом Delphi.**

## Проверены одновременно три приватных источника

- /mnt/data/Projects.7z — локально извлечены `_Unit115.pas`, `_Unit128.pas`, `_Unit114.pas`, `_Unit125.pas`, `mvkform.dfm`, 5/5 точных SHA256 соответствуют `source_files` в SQLite. Полные исходники **не** публикуются.
- /mnt/data/mvk_idr(1).sqlite — `quick_check=ok`. Подтверждены функции `TMvkChannelStorage.GetAdjustedEnvelopeLength 007D1158` (`_Unit115.pas:17216–17297`), `TMvkChannelStorage.GetSpectrum 007D13D4` (`17386–17889`), `GetSignal 007D0C30`, `007D1C48` (децимация), `007D1D50` (FIR), `007D1E70` (I/Q) и `007D1FE8` (Hann/FFT).
- /mnt/data/mvkview.idp — исходная память/метаданные `FRange`, FIR-банков и параметров каналов; SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Никакие приватные коэффициенты не входят в исходники, тесты CI или их артефакты.

## Исправление существенной математической ошибки

В Pascal `GetAdjustedEnvelopeLength`:

1. `ratio = FSampleRate div ENVELOPE_RATES[EnvelopeCode]`.
2. Для ratio=1/2/4/8 исходный offset соответственно 0/45/89/177, а для других оригинально допустимых значений используется отдельное промежуточное смещение.
3. **`AdjustedLength = selected bSpecLines N + offset + FIR_TAPS[final_stage] * ratio`** (адреса 007D1215–007D1228). Предыдущее умножение на `FIR_DECIM[final_stage]` было неверным.
4. `GetSpectrum 007D1462` записывает AdjustedLength обратно в `Params.Count`, затем `007D1C48` и `007D1E70` мутируют его вновь: `next = (current - FIR_TAPS[stage]) div FIR_DECIM[stage]`. **Фактический N, переданный 007D1FE8 FFT, отличается от значения bSpecLines в интерфейсе**.
5. Для допустимых исходных Fs, если `source_input_count` и обратная FIR-рекурсия по **post-FIR FFT N** не совпадают, вычисление запрещается. Никаких «улучшений» округлением, zero padding или подстановкой обычного FFT нет.

Примеры при Fs=65 536, выбранном bSpecLines=4096:

| FilterCode | Исходных Float32 | post-FIR FFT N | output Fs | Шаг FFT |
|---:|---:|---:|---:|---:|
| 1 | 4193 | 1024 | 16 384 Гц | 16 Гц |
| 5 | 4399 | 512 | 8192 Гц | 16 Гц |
| 20 | **4147** | **2048** | 32 768 Гц | **16 Гц** |
| 21 | 4243 | 1024 | 16 384 Гц | 16 Гц |
| 26 | 4145 | 4096 | 65 536 Гц | 16 Гц |

Старая модель `Code20 / N4096 → source 4198`, `post 2073` **не соответствует оригинальному Pascal**. Исследовательский inverse(4096) = 8243 относился ошибочно к **post-FIR** N4096, тогда как исходный bSpecLines N4096 после фильтра даёт N2048 и inverse(2048)=4147.

## Исполняемая цепочка, не дополнительный TCP

- `envelope_plan`: исправлен source multiplier `ratio`, исходные таблицы/ограничения сохранены.
- `source_selected_envelope_fft_plan`: проверены полный PRE-FIR исходный window, стадии/выходные количества, фактический post-FIR FFT N, Fs и df; его обратный счёт снова даёт точный source N.
- Один и тот же Go TCP-ридер и SHA-проверенное 2²¹-кольцо: локальный дискриминатор `HTag=-2` отдаёт строго допустимую `GetAdjustedEnvelopeLength` при конкретных `EnvelopeCode` и `original_bspec_lines`; отрицательный HTag **никогда не передаётся МВК01**. Утверждения об одном сокете, RAW и Freeze прежние.
- Python проверяет `session_id`, `FRxPos`, `FValidPos`, `device_index`, непрерывность, Fs, код фильтра/N, SHA, старение и домен Float32. Любой mismatch отказывается.
- Qt при наличии операторского **локально SHA-проверенного оригинального IDP** и разрешённого source-ring-окна запускает `source_selected_envelope_spectrum_candidate`: исходная синтетическая математика Single/x87 candidate, одна пред-FIR DC-компенсация, каскад FIR/IQ, оконная FFT по post-FIR N, post-power режимы 0..3, `FRange=1` для уже калиброванного Go BIN. График и подпись помечены как **локальный FIR/IQ кандидат, Delphi 1:1 НЕ подтверждён**. Copy/Save как оригинал заблокированы.
- При отсутствии подтверждённого IDP/Go ring/истории или при post-FFT N, для которого ещё не приняты локальные средства summary, **старый спектр очищается**; нечистый preview нельзя выдавать за огибающую. GetSignal с фильтром остаётся отдельно заблокированным до исходного HTag-курсорного теста.

## Регрессия/границы

Добавлены синтетические Python/Go/Windows Qt тесты: Code1/2/5/20/21/26, точное pre/post N, отсутствие повторного FRange, все четыре режима Y, байтовая идентичность Go ring и SHA, отказ при подмене кода/N/сессии/нехватке истории, переключение фильтра/курсор/Copy/Save. Исходные FIR-данные/PCAP не публиковались, сеть и физический прибор в тестах не используются.

**ОТКРЫТО:** реальное парное испытание исходной Delphi 1.0.47 против копии на одном МВК01, побитовое x87 совпадение 262144 Hann/FFT и FIR банков/сохранений, фактический коэффициент FRange из Session, исходный живой фильтр GetSignal/Hscale, оригинальные шкалы/курсоры и аппаратные timeout/Stop/SetRate. `original_delphi_compatibility_verified=false` до физического сравнения. Никаких автоматических команд прибора.

CI полная 5/5 матрица на одном CODE SHA: Linux Go, Linux Core, Windows Core/Qt, Windows QPA DPI100/150, Windows EXE. Не объявлять пакет принятым до фактических результатов.
