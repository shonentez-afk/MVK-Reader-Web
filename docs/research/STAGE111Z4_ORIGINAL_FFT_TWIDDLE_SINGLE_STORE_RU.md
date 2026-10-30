# Stage111Z.4 — исходный FFT: промежуточные Single-store и знак FFT

Дата: 30.10.2026. Рабочая ветка: research/stage111-mvkview-desktop-20261029.
Цель — единая автономная Windows Qt/PySide6 MVKView Compatible, не Web v0.3.40.

## Что проверено на приватном оригинале

Локально проверены семь кодовых окон оригинального mvkview.idp (IDR v3), только по SHA256. Оригинальные байты/исходники/производственные измерения не переданы в GitHub.

| Исходный участок | VA | Длина |
|---|---|---:|
| Spectrum FFT forward wrapper | 007CC3F8–007CC403 | 11 B |
| FFT alternate wrapper | 007CC404–007CC414 | 16 B |
| Twiddle recurrence | 007CC316–007CC348 | 50 B |
| Butterfly kernel | 007CC22D–007CC37F | 338 B |
| GetSpectrum FFT call and power | 007D2083–007D20B6 | 51 B |
| Spectrum Hann multiplication | 007D205A–007D2080 | 38 B |
| DC running mean + subtraction | 007D2344–007D2397 | 83 B |

Source-verified:
1. GetSpectrum по 007D2083 вызывает 007CC3F8, **положительный угол +2π (Float32 0x40C90FDB)**. Отдельная процедура 007CC404 использует −2π (0xC0C90FDB); не смешивать её с текущим спектральным путём.
2. В twiddle recurrence на 007CC325 выполняется **одно** FSTP Single для промежуточной действительной суммы alpha*Wr + beta*Wi. Мнимая разность alpha*Wi − beta*Wr остаётся в x87 до вычитания из Wi. Затем обновлённые Wi и Wr сохраняются как Single на 007CC33A и 007CC344.
3. Оригинал использует Single-запись после применения оконного коэффициента Hann и после каждого шага накопления среднего. Указанные исходные окна сверены по SHA.

## Изменения программы

Исправлена изолированная функция поворотных коэффициентов FFT в mvk_compatible/core/fft_idr_candidate.py.

Суть исправления:
- temp_real = float32(alpha*old_wr + beta*old_wi)
- next_wi = float32(old_wi − (alpha*old_wi − beta*old_wr))
- next_wr = float32(old_wr − temp_real)

**Важно:** нет отдельного Single-округления imaginary-intermediate. При первой проверке такая лишняя операция ошибочно присутствовала в черновом варианте; после проверки оригинального машинного кода она устранена. Forward FFT остаётся положительным.

Новые регрессии:
- mvk_compatible/tests/test_stage111z4_fft_single_twiddle.py — битовые синтетические примеры, независимая scalar recurrence, знак FFT и спектральная мощность.
- mvk_compatible/private_fft_source_rounding_audit.py — локальный read-only аудитор исходного IDP: 7 SHA окон, знаки wrapper, вызов FFT, позиции Single-store, mean и Hann, fail closed.
- mvk_compatible/tests/test_private_fft_source_rounding_audit.py — только синтетические данные, ошибки подписи и изменённых инструкций.

## Измеренные синтетические отличия (не оригинальный golden)

Контрпример wr=-0.4884991348, wi=-0.4235749543, alpha=0.3196847737, beta=0.2604950070:
- Прежняя свёртка float64: Wr = HEX BE635275.
- Source-aligned Single-store: Wr = HEX BE635276.
- Разница: один float32 ULP.

При half=8192 отличается **989/8192** пар twiddle-коэффициентов относительно прежней версии. На синтетическом FFT N=8192 с тремя гармониками изменились **3985/8192** комплексных пар и **1857/4096** float32 мощностей. Это эффекты реконструкции порядка операций, не доказательство полного совпадения с реальной Delphi FFT.

**Исправление предварительной цифры:** в ранней черновой проверке упоминались 6788/8192, но она дополнительно округляла imaginary intermediate, чего оригинал не делает. После проверенного source-порядка актуально 989/8192.

## CI и приёмка

- [Linux Core #147](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/147) SUCCESS и [Windows Core+Qt #148](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/148) SUCCESS для кодового SHA 0e231f2f59bd7f9ef6003f10f524b79a94d267f1.
- [Linux Core #154](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/154) SUCCESS для SHA 5ae3c87737b4721a8e4f5d0564384cfad9373fd5, включая новый приватный source-аудитор и синтетические проверки.
- Windows Core+Qt #153 и Windows Preview EXE для SHA 5ae3c87737b4721a8e4f5d0564384cfad9373fd5 в момент фиксации не подтверждены; не заявлять их успех.
- Локально проверены оригинальные 7 IDP code SHA и структурные условия. Оригинальный runtime FFT на реальном архиве в этом этапе не запускался.

## Границы доказанного и следующий шаг

Подтверждено по оригинальному source: знак FFT, callsite, места Single-store twiddle, mean и Hann. Реализован source-aligned, Qt-независимый FFT-кандидат; синтетические Core тесты проходят.

Не подтверждены: битовая идентичность исходных sin/cos с Python, x87 CW при FFT в оригинальном Windows-процессе, битовый оригинальный runtime Hann, идентичность полного FFT/амплитуд по BIN, CursorString и TPaintBox. Не объявлять эти элементы аттестованными и не менять текущую Qt Y-ось без оригинального эталона.

**Далее Stage111Z.5:** исследовать генератор оригинального Hann и порядок FFT window/sample position, затем сравнить оригинальный спектр и курсор на одном офлайн-архиве. Реальный прибор, stable main, Web v0.3.40 и закрытые оригиналы не трогать.
