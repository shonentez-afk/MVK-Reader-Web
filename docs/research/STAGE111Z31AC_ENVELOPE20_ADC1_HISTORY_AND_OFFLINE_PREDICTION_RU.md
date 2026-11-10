# Stage111Z31AC — EnvelopeCode20: проверка физической истории ADC1 и предварительный FIR/IQ (10.11.2026)

## Назначение

Исправление интерпретации отчёта GigaCode о `Z31R_FAIL_HISTORY` и подготовка физически сопоставимого `B` на том же ADC1 BIN. Это **НЕ** оригинальный runtime capture: MVKView со слов GigaCode всё ещё Paused `EIP=007D1900`, после уже принятого LOG `A`; GUI, CPU, регистры не трогались. В исследовании используем локально предоставленные пользователем **`MVK00000043-ADC1-2026-10-29--13-32-12.bin`** (SHA256 `b598d466f9f70f49e4a5f6a0f2a20d4870af43f9864f5e4c9f7cfd51c9d2fad1`) и приватный оригинальный `mvkview.idp` (SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`).

## История FIR по существующему source-derived коду

Из `core/envelope_idr_candidate.py`: `ENVELOPE_RATES[20]=65536`, `ENVELOPE_STAGES[20]=5`, `FIR_TAPS[5]=51`, `FIR_DECIM[5]=2`, `pre_stage=second_stage=None`; `Fs_output=65536/2=32768 Hz`, Nyquist=16000 Hz, `df=0.125 Hz`. Меню `1окт 16 кГц` согласуется с Nyquist 16k. `required_original_history(N=262144,Fs=65536,code=20)` возвращает **524339 исходных Float32** (`2*262144+51`). Эта величина — входная минимальная длина текущей Python-инверсии FIR; точное фактическое `[EBX+4]` оригинала при `EIP=14AA` остаётся непроверенным и может отличаться вследствие Win32 `GetAdjustedEnvelopeLength`/выбора окна.

**Текущий старый ring**: `end=294912`, `oldest=32768`; источников до oldest в памяти нет. При неизменном end `end<524339`, поэтому `RESUME_B` достигнет **`Z31R_FAIL_WINDOW` раньше `Z31R_FAIL_HISTORY`**, вопреки предположению GigaCode. Нельзя утверждать, что выбор фильтра автоматически меняет end/oldest или перезагружает историю; оригинал следует измерить на новом stop.

**Но сам физический BIN ПОЛОН**: 1965824 Float32. Уже принятый original LOG A на нём: начало 1703281, конец exclusive 1965425. Для FIR-кандидата с **тем же физическим концом** нужное окно: `[1441086,1965425)`, ровно **524339 samples = 2097356 байт**. Оно существует полностью, не требует нового измерения, содержит всю предыдущую A-последовательность хвостом и имеет SHA256 `ded1253c1d708169fe21dedeb99c980bd17f48e8bd3f1c1fee7a0f5394a2579d`. Дополнительная реальная история — **262195 samples**. Доступность в `BIN` **не равна** доступности в исходной старой адресации `Storage`: новая загрузка должна быть подтверждена по `[EBP-4]` и сохранённым raw bytes. По одному имени BIN невозможно утверждать, что новый x32dbg B использует именно эти байты.

## Дополнительный локальный offline кандидат (не original runtime)

Мы выполнили **прямое offline вычисление** по приведённому полному ADC1 BIN и **настоящим приватным FIR-коэффициентам** из hash-проверенного оригинального IDP (`stage5`, 51 I/Q taps, 2x decimation, Float32 stores after each accumulator addition), повторив существующую `source-derived` логику нормализации/FRange, mean-center, FIR sqrt(I²+Q²), Hann/FFT, low-bin power, LOG Y. Ни байты коэффициентов, ни Float32 измерения **в GitHub не размещены**.

| Массив расчётной модели | SHA256 исхода модели | Статус |
|---|---|---|
| ADC1 B full raw 524339 Float32 | `ded1253c1d708169fe21dedeb99c980bd17f48e8bd3f1c1fee7a0f5394a2579d` | физическое окно в BIN, byte-exact |
| After FRange / pre DC | `a28310afd03146cd25c98c55d342c6372d9f919a6abeeba8fe339e1d15041a35` | candidate |
| After DC / pre FIR | `432acbbd15da998b943c19769f8bd4fcdd93deab203d7fc1c55a285630de03aa` | candidate |
| After IQ magnitude / preFFT 262144 | `3b340c457162df5521802a2cc4fe7bb21aac3b1e52dcc1c005ba30bdcb654b7d` | candidate |
| Before-mode Power 131072 | `af61ca38d702db07dced1e058091be153ce492351f4b4684d9918009678d5182` | candidate |
| After-mode Power 131072 | `d0d197f5c5b90a4c59a7af9a057d3dcd0e8a76b50673497277014a3ecdbe3377` | candidate |
| LOG display Y 131072 | `11f032268fdda60e61e9cb8561974cd439fa843422e1e1a83c5f4967f8162b89` | candidate |

Пик этой **модели**, не оригинала: бин 653 × 0.125 Hz = 81.625 Hz, Y приблизительно -78.816765 dB. **Нельзя объявлять FIR/IQ bitwise PASS**, поскольку нет соответствующего настоящего `B` GetSpectrum runtime; при расхождениях выяснять физическое end, actual rawN, stage, Y and rounding, не подгонять модель.

## Новый безопасный порядок работы GigaCode

1. Оставить оригинальный процесс Paused `EIP=1900`; сначала локально hash-validate ADC1 BIN, IDP и историю `[1441086,1965425)`. Проверить собственным импортом из GitHub `required_original_history`, не вручную на глаз. При проверке будущего B использовать `-Adc 1`, `-SpectrumType 0`, `EnvelopeCode20`.
2. Подготовить **отдельный read-only preflight с остановкой** для нового обращения к `EIP=14AA` при `[EBX+8]=0x14`, `[EBX+18]=0`. Только после отдельного разрешения оператора возможно F9/GUI: никакого Auto-F9 или слепого запуска `RESUME_B`.
3. На остановке B **до исполнения** проверить фактические `[EBX+04]` rawN, `[EBX+20/24]` end, `Storage oldest/writepos/cap/type/FRange/ring ptr`, достаточность истории и физические bytes, затем сохранить полный ring и SHA. Не предполагать, что оригинал «сам расширит буфер», — это гипотеза.
4. Только если исходное окно B реально доступно и привязано к **тому же физическому BIN endpoint** (сверка полного raw tail с уже принятым A и/или physical BIN), однократно выполнять `RESUME_B`; при `FAIL_WINDOW`/`FAIL_HISTORY`/другом — STOP без изменения регистров или принудительного zero-pad.
5. Существующий `Verify-Capture.py` без флагов требует A+B с **тем же оригинальным логическим end**; он может отказать после новой загрузки, даже если физически BIN одинаков. Не обходить verifier ручным редактированием `end`; для B-only/перезагруженных колец нужна явная новая проверка по **физическим raw bytes в BIN**. Original raw A оставлять как golden.
6. Получить copy/paste реального MCP/x32dbg Log (последний A `capture_log_a_snapshot.txt` в ZIP был **0 байт**) и сохранить local fingerprints; не выкладывать пользовательские measurements и IDP в публичный репозиторий.

**Статус:** original обычный LOG для одного ADC1 BIN полностью проверен source-derived; source/model EnvelopeCode20 **офлайн вычислен, но оригинальная FIR-паритетность OPEN**. Следующее узкое место — обеспечить оригинальную загрузку более длинной истории или обоснованно выбрать другое end, затем физически захватить и сравнить B. Остальные спектры/GUI пока не трогать.
