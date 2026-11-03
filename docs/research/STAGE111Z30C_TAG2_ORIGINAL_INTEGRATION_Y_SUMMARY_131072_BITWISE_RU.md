# Stage111Z30C — оригинальный Tag2 «Линейный ВС»: 131072/131072 Power + Y, 3/3 summary

**Дата:** 03.11.2026. **Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. Продукт — автономная Windows MVKView Compatible; не main/Web 0.3.40.

## 1. Происхождение

Оператор передал из оригинальной Windows MVKView/x32dbg V6 **девять приватных файлов**: `power_before_mode.bin`, `power_after_mode.bin`, `display_y.bin` (каждый **524288 байт** = 131072 Float32), `params_before.bin`, `params_after.bin`, `params_summary.bin` (каждый **60 байт**), `frange.bin` (4 байта), `summary_triplet.bin` (12 байт), `capture.log` (96 байт).

В **GitHub не публикуются исходные массивы, архивные измерения, оригинальные EXE/IDP, фрагменты сигнала или бинарные snapshots**. Сохраняются только хеши, агрегаты и source-derived regression gates. Файлы в этом чате доступны для повторной проверки локально.

`capture.log` содержит только редирект лога, нет BEGIN/DONE и фактических EIP/TID/EBX/EBP на всех трёх остановках. Поэтому **независимая аутентификация same-call/frame/thread остаётся OPEN**, даже при полном численном совпадении и согласованности трёх параметрических snapshots.

## 2. Структура и целостность

- `params_before.bin` и `params_after.bin` **побайтово идентичны**; в `params_summary.bin` те же байты `0x00..0x2F`, изменены только `+0x30/+0x34/+0x38` после расчёта.
- Все 3 snapshots: `N=262144`, `Half=131072`, `Fs=65536`, `SpectrumType=2`, `EnvelopeCode=0`, оригинальная позиция окна `[EBX+20]=0x00290000`, `[EBX+24]=0x00000000`.
- `frange.bin`: оригинальный Single word `43FF4853` = `510.5650329589844`.
- `summary_triplet.bin` — **ровно 12 байт**, побайтово равен `params_summary.bin[0x30:0x3C]`; исходные HEX `40B216B1 / 429F850B / 40B0B392`.
- Три массива являются конечными Float32, N/2 элементов. Power до/после неотрицателен, Y неотрицателен, нет NaN/Inf, after-mode бины 0–1 равны нулю.
- SHA256 `before-power` = `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`, **строго совпал с прежним оригинальным Z8 `after_power(1).bin`**. Поэтому FFT не исследуем заново.

SHA256 контрольных оригинальных дампов (без самих байтов):
```text
power_before_mode    16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34
power_after_mode     472b903103120d56d8d6d492c8308be5a14263f433c5c0ef32583254119b18b5
display_y            babb626dca3622b4f93edca20ead0e6785daea39246a00e25a80941bad03448c
frange               84eb688f8f548bf542dbdefefbadfc38163f1648ee56cfaa84afe882baea7d29
params_before        b6bca0b454e122359a67e4d4a60a9b11441c832c80e2652fabaeb334065eaec8
params_after         b6bca0b454e122359a67e4d4a60a9b11441c832c80e2652fabaeb334065eaec8
params_summary       68b5c1765cb953269a9ecbc17d24845544bed2505bf947c727b360ea749fa524
summary_triplet      0875b96c76cf21aad0650af990ec5f3952b59c69a0ab6db63f1179b1890a460d
```

## 3. Численная сверка ТЕКУЩЕГО кода, без подгонки

Кандидат из `core/envelope_spectrum_idr_candidate.py::_delphi_integration_power` применён **один раз** к исходной мощности после исходного `low=max(2,round(N/(2*Fs)))=2`, с `f[k]=k*Fs/N` и `K=159.154943091895`:

`P_after[k] = Single(P_before[k] * (K/f[k])²)` для k>=2, low bins = 0.

**Результат: 131072 / 131072 Float32 побитовых совпадений, max ULP=0, SHA рассчитанного массива совпал с оригиналом.** Это подтверждает source-derived **однократное интегрирование мощности** для данного исходного окна.

Кандидат `core/spectrum_display_source.py::source_derived_mode_display` для режима 2 с исходным Single scale `Single(FRange/(N/2))` и `Single(sqrt(P_after/2)*scale)`:

**Результат: 131072 / 131072 оригинальных displayed Y Float32 побитовых совпадений, max ULP=0, SHA рассчитанного Y совпал с оригиналом.**

Существующий `core/spectrum_metrics_idr_candidate.py::original_spectrum_summary` в той же полосе `first=2, last=102400`, с последовательной Double-суммой и поэлементными Single-сохранениями `±2` пика даёт:

| Поле | Оригинал (файл, HEX) | Вычислено | Float32 exact |
|---|---|---|---|
| OutputMean | `40B216B1` | `5.565269947052002` | ДА |
| OutputPeakX FFT bin | `429F850B` | `79.75984954833984` bins | ДА |
| OutputPeakY | `40B0B392` | `5.521920204162598` | ДА |

Частота по `OutputPeakX × Fs/N` = **19.93996238708496 Гц**. Максимум post-mode Power и отображаемого Y находится на bin80 (20 Гц), что не следует путать с энергетическим центром 79.7598495 bins.

## 4. Неожиданное совпадение со старым исходным Copy

В [Stage111Z12](STAGE111Z12_COPY_SELECTED_RECORD_SOURCE_AND_TWO_OPERATOR_TEXTS_RU.md) оператор давно сообщал строку **`5,57 TAB 19,94 TAB 5,522`** как результат original «Копировать» для соседней спектральной записи. Полученные сейчас независимые Tag2 значения при исходном округлении 3/4/4 **совпадают по всем трём текстовым полям**. Это объясняет происхождение старого ряда чисел, **но не доказывает**, что нажатие «Копировать» и данный x32dbg GetSpectrum были в одном вызове/записи; same-click `ESI`, `XScale`, raw Clipboard provenance тогда не фиксировались.

Другое раннее Copy `6,15 / 19,93 / 6,096` пока не привязывать к Tag3 и не объявлять эталоном без отдельных проверенных исходных массивов.

## 5. Статус и следующие шаги

**Tag2 S05 NUMERIC PASS на пользовательском original-runtime-claimed захвате:** Postmode Power 131072/131072 (0 ULP) + displayed Y 131072/131072 (0 ULP) + original triplet 3/3 Float32 exact, подтверждённые тремя согласованными снимками Params. Следовательно, источник алгоритма VS integration и Full Y на этом измерении успешно восстановлен, в текущем `core` изменения **не требуются**.

**Границы:** не доказан независимый same-thread/frame Win32 контекст за пределами сохранённых параметрических snapshots; всё ещё нет полной матрицы по другим N/каналам/окнам; `capture.log` redirect-only; оригинальный Tag0 full Y пока не поступал; `Tag3` два интегрирования и Y ещё OPEN.

**Далее:** не повторять Z8/Z10/Tag1/Tag2. В том же оригинальном архиве/АЦП перейти к **Tag3 Линейный ВП**, получить через уже подготовленный V6 `RESUME_TAG3_FROM_154B.txt` полные three buffers + FRange + 3 Params + physical `summary_triplet.bin`. Повторить независимую цифровую проверку 131072/131072 и 3/3. Исходный Native Go R6.1, прошивку и `main/Web` не менять.

Локальный aggregated report `MVK_STAGE111Z30C_TAG2_NUMERIC_ACCEPTANCE_20261103.json`, SHA256 `0eed001e9b4322eba9abfeb7874e674d1818dcb95993217452c048d806cb4d48` доступен в чате, содержит только хеши/параметры/числа без raw samples.
