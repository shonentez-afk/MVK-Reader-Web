# Stage111Z.9 — оригинальный GetSpectrum OutputMean / PeakX / PeakY: source audit и runtime capture

Дата: 31.10.2026. Ветка: `research/stage111-mvkview-desktop-20261029`. Основной продукт — автономная Windows MVKView Compatible (Qt/PySide6), не прежний Web UI.

## 1. Что доказано непосредственно оригинальным кодом

Локально изучены пользовательские приватные `Projects.7z/_Unit115.pas` и `mvkview.idp` (IDR v3). Машинные байты шести участков оригинального EXE внутри IDP **сверены по SHA256**. Подлинные PAS, IDP, EXE, BIN, PCAPNG, заводские измерения и сырой FFT-массив в GitHub/CI **не публиковались**.

| Исходный участок | VA original 32-bit | Реально подтвержденная операция |
|---|---|---|
| границы суммы | `007D154B–007D15BC` | high=`TRUNC(N/2.56)`, low=`max(2, ROUND(N/(2*Fs)))` |
| сумма и максимум | `007D17E7–007D1832` | суммирует `P[k]` по одному с `FSTP Float64` после каждой суммы, выбирает первый максимум при равных значениях |
| среднее и нулевой пик | `007D1832–007D1876` | `sqrt(total/2) / (N/2) * FRange` как OutputMean Single; при max bin<=2 PeakX/Y=0 |
| пять бинов пика | `007D1876–007D18D1` | диапазон найденного максимума ±2, с ограничением верхом массива; вызывает weighted-центроид |
| OutputPeakY и выход | `007D18D1–007D191D` | `sqrt(energy_5bins/2)/(N/2)*FRange`, сохраняется Single в `[EBX+38]` |
| weighted sum helper | `007D21A8–007D2223` | `sum(k*P[k]) / sum(P[k])`; две суммы сохраняются как **Single** после каждого шага |

**Структурные поля original `TMvkChannelStorageCalcParams`:**
- `[EBX+30]` — OutputMean Single.
- `[EBX+34]` — OutputPeakX Single **в единицах бинов**, НЕ Герц.
- `[EBX+38]` — OutputPeakY Single.
- `[EBX+4]` — N, `[EBX+28]` — N/2, `[EBX+2C]` — Fs, `[EBX+18]` — SpectrumType Tag0..3.
- `[[EBP-4]+4]` — FRange Single исходного выбранного канала.
- `007D17E7` — вход в summary после преобразования режима, `007D1900` — все три выхода готовы, буфер ещё не освобождён.

**Ключевое различие между режимами:** ранее полученный `after_power(1).bin` из `007D154B` был **до** интегрирования режимов ВС/ВП; для triplet-сравнения этих режимов он непригоден. В `007D17E7` сохраняется уже итоговый для summary power buffer **N/2 Float32 после mode processing и low-bin zeroing**.

## 2. Анализ ранее полученного ненулевого FFT power capture (условно до mode processing)

Файлы `before_fft(1).bin` и `after_power(1).bin`, принятые на Stage111Z.8 как одна исходная пользовательская пара, имеют N=262144 и 131072 мощностей. **Source-derived `idr_float32` ранее совпал с этим массивом 131072/131072 побитово**; provenance same-call подтверждается пользователем, CI исходное содержимое не видит.

Из `after_power(1).bin` без угадывания Fs/FRange/Tag можно диагностировать:
- raw power maximum внутри исходной расчётной полосы: **бин 15200**;
- взвешенный максимум по пяти бинам ±2: прибл. **15200.1455** в единицах FFT бинов;
- условный интервал `high=TRUNC(262144/2.56)=102400` по исходному коду.
- Нельзя выдавать физическую частоту `OutputPeakX*Fs/N` и физические `OutputMean/OutputPeakY` без **реальных** исходных Fs и FRange.
- Для Tag 2/3 нужно сначала оригинальное mode processing, поэтому нельзя отождествлять прежний raw `after_power(1)` с окончательным `P` на `007D17E7`.

Это **вычисленные производные факты пользовательского файла**, не оригинальный runtime golden трёх полей.

## 3. Что добавлено в исследовательскую ветку

1. `mvk_compatible/private_getspectrum_summary_source_audit.py`: приватный read-only SHA + opcode/callsite verifier шести окон; проверяет точные три смещения, x87 Single/Double stores, ROUND/TRUNC/SQRT/weighted helper. Никакие оригинальные bytes/paths не выводятся.
2. `mvk_compatible/tests/test_private_getspectrum_summary_source_audit.py`: только синтетические опкоды/подписи и fail-closed проверки.
3. `mvk_compatible/private_getspectrum_summary_triplet_compare.py`: читает приватный `summary_power.bin` и JSON с настоящими исходными метаданными и тремя Float32 HEX, сравнивает `original_spectrum_summary` с оригинальными полями. Возвращает только битовое равенство, ULP и относительные/абсолютные ошибки для каждого из 3 полей; не выводит исходные HEX, значения мощности, пути, реальные Fs/FRange.
4. `mvk_compatible/tests/test_stage111z9_private_getspectrum_summary_triplet_compare.py`: синтетические success/error case, 1 ULP mismatch, все четыре режима после обработки, запрет NaN/Inf, неполной/небезопасной структуры, symlink, нулевого дампа, опасных имён.
5. `docs/research/STAGE111Z9_X32DBG_SPECTRUM_SUMMARY_CAPTURE_RU.md`: точные два breakpoint и read-only сохранение исходного буфера для всех режимов.

**Основной модуль `core/spectrum_metrics_idr_candidate.py` не изменён:** источник структуры подтверждён, но полное Delphi x87 округление `Sqrt` и три настоящих runtime значения ещё не получены. Исправлять численную формулу «идеальным» округлением без оригинала нельзя.

## 4. Операторский runtime эксперимент для Stage111Z.10

На оригинальной Windows MVKView открыть один офлайн архив/канал/режим и поставить:

```text
bp 007D17E7
bp 007D1900
```

На первой остановке, перед summary, сохранить **N/2 Single** после всех mode transforms:

```text
savedata "C:\MVK_CAPTURE\summary_power.bin", dword:[ebp-2C], dword:[ebx+28]*4
```

Записать `EBX`/N/Fs/Tag/FRange (проверить адрес/числа по инструкции). На второй остановке `007D1900` того же вызова записать:

```text
dword:[ebx+30]    // OutputMean Single bits
dword:[ebx+34]    // OutputPeakX Single bits (бин)
dword:[ebx+38]    // OutputPeakY Single bits
```

Полный `summary_capture.json` и локальный запуск:

```powershell
python -m mvk_compatible.private_getspectrum_summary_triplet_compare "C:\MVK_CAPTURE\summary_capture.json"
```

Инструкция: [Stage111Z.9 x32dbg](STAGE111Z9_X32DBG_SPECTRUM_SUMMARY_CAPTURE_RU.md). Присылать достаточно три HEX, Fs, FRange, N и Tag и при необходимости `summary_power.bin` лично в диалог для исследования; в публичный GitHub не загружать.

**Ограничение:** на 31.10.2026 есть подтвержденный пользователем полный FFT power одного N262144 архива, но **нет настоящего оригинального runtime triplet по трем полям**. Даже когда три synthetic тестовых показателя совпадают, флаг `original_delphi_summary_bitwise_parity_accepted` остаётся false до настоящего оригинального референса. Не переносить FFT-pass на CursorString/Graph Canvas.

## 5. Следующий шаг

Stage111Z.10: получить оригинальные три поля, сравнить Float32 ULP и при выявлении ошибки локализовать `Sqrt`/FRange/x87 суммирование. Затем проверять `bSpecCopyValueClick` текст 3 полей с `007B2090`, частоту `OutputPeakX*XScale`, курсор и TQGrapher UI. Не затрагивать stable `main` и Web v0.3.40.
