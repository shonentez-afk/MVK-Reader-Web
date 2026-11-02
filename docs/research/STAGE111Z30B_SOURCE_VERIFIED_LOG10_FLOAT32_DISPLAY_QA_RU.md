> **INDEPENDENT PRIVATE IDP CHECK (02.11.2026):** uploaded mvkview.idp SHA256 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438; executable opcode pattern `55 8B EC D9 EC D9 45 08 D9 F1 9B 5D C2 04 00` for helper 00447DB8 appears **exactly once** in local IDP (offset 0x46EE0). This independently corroborates the log10 instruction sequence from private Winapi.Messages.pas; no original bytes/source published. Stage30A verified onefile EXE SHA256 0dd09bf1404845990361160a7b0ae0932fa59f95d60e92eab2c5bd1c0d082f1e (different from uploaded artifact ZIP digest).

# Stage111Z30B — original GetSpectrum log10 and full Float32 display Y

Дата: 02.11.2026. Ветка: research/stage111-mvkview-desktop-20261029.

## Проверка сделанного Stage30A

- CODE commit 7186a5da1d016e7f8e807c3cba04186e1ae4c43f.
- GitHub Actions #41422369872: **3/3 SUCCESS**. Linux **1179 passed**, 5 skipped, 30 subtests; Windows Core **1182 passed**, 2 skipped, 30 subtests; Windows Qt **49 passed**. Embedded Go R6.1 / onefile Windows EXE build SHA/PE verification SUCCESS.
- EXE artifact 13130771299, ZIP 68 540 151 bytes, reported artifact digest sha256:60c945ee8de4c87d7ac3cb799585bbdb5d2e29b1bfc035c8781ea7f075bf56bd. Не путать ZIP digest с отдельным EXE SHA.
- Подтверждено по приватному исходному _Unit115.pas: в 007D154B источник FFT power scratch [EBP-2C] ДО mode; в 007D17E7 тот же scratch ПОСЛЕ mode, до summary. Для Stage30A source адреса выбраны правильно, и нужны разные дампы одной оригинальной функции. Нет original Tag1–3 runtime goldens.

## Новый исходный факт — логарифм

В исходном Winapi.Messages.pas (локальный Projects.7z) original helper 00447DB8 содержит 00447DBB FLDLG2; 00447DBD FLD Single; 00447DC0 FYL2X. Это **log10(Single)**, а не неустановленное основание.

В _Unit115.pas оригинальный GetSpectrum mode0:
- 007D15F2 вызывает log10(N/2), 007D15F7 умножает на 2, 007D15FD записывает полученный offset в Single [EBP-18].
- Для положительного power 007D1624 вызывает log10(P); 007D1629 вычитает уже сохранённый Single offset; 007D162C умножает на 10; 007D1635 пишет Float32 Y. Нулевая мощность получает -180 (0xC3340000).
- Tag1/2/3 пишет FRange/(N/2) как Single, затем sqrt(power/2) * этот Single scale, результат — Single Y. Для Tag2/3 предварительно выполняется исходная функция интегрирования power 007D2164 один/два раза.

SOURCE-VERIFIED: log10, Single offset/scale/output, графические mode branches. Не утверждать полное числовое bitwise Delphi x87 vs NumPy по всем окнам и режимам.

## Что сделано в коде Stage30B

1. Новый core/spectrum_display_source.py: четыре режима, промежуточное Float32 округление, full N/2 Float32 массив Y. Исходный post-mode power не изменяется.
2. core/offline_export.py (обычный архивный спектр) и core/envelope_spectrum_idr_candidate.py (огибающая) используют один общий source-derived display helper. Логарифм больше не маркируется как гипотетическое основание; исходные FFT/power, итоговые summary и FIR не переписаны; логарифмическая единица GUI остаётся компактной «дБ».
3. Новый private_getspectrum_display_y_compare.py: read-only comparison original full [EBP-2C] post-mode power и [EBP-30] original full displayed Y с одной остановки 007D17E7. Имеется отдельная сравнительная диагностика старой double-формулы, без автоподгонки.
4. tests/test_stage111z30b_source_display.py: synthetic-only четыре режима, источник log10 и Float32, SHA256, один ULP, неверные файлы/размеры/NaN/negative/symlink.
5. Локально проверен helper Python compile и synthetic smoke по Tag0/1/2/3 (PASS). Полный GitHub CI и готовность нового EXE должны оцениваться только по фактическому workflow SUCCESS, а не по наличию коммита.

## Как снять действительно НЕДОСТАЮЩЕЕ original runtime Y (без повторения Z8/Z10)

Если нужен новый оригинальный display-массив, для одного вызова GetSpectrum остановиться в 007D17E7. В одном и том же x32dbg stop:
- [EBX+28] — N/2 Float32 элементов; [EBX+18] — mode 0/1/2/3; [EBX+2C] — Fs; [EBX+8] — EnvelopeCode.
- Оригинальный FRange: storage object находится в [EBP-4], Single FRange по offset +4.
- [EBP-2C] содержит УКАЗАТЕЛЬ на N/2 original post-mode Float32 power.
- [EBP-30] содержит УКАЗАТЕЛЬ на N/2 original full display Float32 Y; это НЕ power.
- Сохранить два локальных raw Float32 файла (по N/2*4 байт) и отдельные SHA256, метаданные original mode/ADC/Fs/EnvelopeCode/FRange. Не подменять их CSV, графиком или скриншотом.
- Команда сравнения: python -m mvk_compatible.private_getspectrum_display_y_compare PRIVATE_DISPLAY_PAIR.json.
- Формат манифеста: schema=MVKVIEW_ORIGINAL_DISPLAY_Y_PAIR_V1, fft_n, output_sample_rate_hz, spectrum_mode, channel_index_zero_based, envelope_code, f_range_bits, power_stop_va=0x007D17E7, display_stop_va=0x007D17E7, power_buffer_role=EBP-2C, display_buffer_role=EBP-30, same_invocation_operator_confirmed=true, post_mode_power_file, display_y_file, post_mode_power_sha256, display_y_sha256. Только корректные SHA256 lowercase. Инструмент не доказывает криптографически происхождение реального original runtime; это заявление оператора.

**Не требовать заново** уже снятые before_fft(1).bin, after_power(1).bin, summary_power.bin, оригинальный Tag0 3/3, Copy 6,89/3800/0,7786 или оригинальный скриншот. Эти материалы — Stage Z8/Z10/Z13/Z14, не новые full Y buffer runtime.

## QA и открытые этапы

GitHub источник Stage30B: 1111f2a62553f8a8b4bcf2bb71f5c8c2a9c39ae1, исходный CI #41423644257, последующий fix compact dB label commit 29ad4c85aa5ae46a566e2760cd96abe8ecb3d4c8. **Не объявлять финальную Windows EXE verified до завершения соответствующего полного CI.**

S01 same-run original/native ring and BIN, S04-S06 original Tag1/2/3 post-mode full arrays, S07 GetSignal/FIR original return, S08 original vs Qt pixel/Copy, S09 long live N65536/262144, S10 all-mode end-to-end остаются OPEN. Не менять main/Web v0.3.40, уже проверенный Native R6.1, старые FFT golden Z8 и summary Z10. Все приватные оригиналы сохранять локально, ни в GitHub, ни в Actions не публиковать.
