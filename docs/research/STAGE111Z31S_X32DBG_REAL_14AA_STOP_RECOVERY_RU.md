# Stage111Z31S — x32dbg дошёл до 007D14AA, восстановление после прерванного скрипта

**09.11.2026.** Приоритет — СПЕКТР, не возвращаться к принятым FFT/FRange/Tag0–3/отдельным FIR коэффициентам. Ветка `research/stage111-mvkview-desktop-20261029`; оригинальный EXE/IDP/BIN/PCAP и вычислительные данные **не коммитить**.

## 1. НОВОЕ оригинальное свидетельство — фото x32dbg

Оператор показал x32dbg с логом:
- `Z31R_PREFLIGHT_OK` и `Z31R_READY_OK` — короткие сигнатуры контрольных адресов совпали;
- `Z31R_A_WAIT`, `Breakpoint at 007D14AA set!`, `INT3 breakpoint at mvkview.007D14AA!` — **первый реальный оригинальный stop GetSpectrum ДО DC/FIR действительно достигнут**;
- затем `Script is terminated by user`, не появились файлы A/Summary и подтверждённый второй проход; прерывание может быть связано с ручной остановкой/диалогом timeout/состоянием сценария, точная причина по одному фото **не установлена**;
- при втором запуске монолитного `CAPTURE_BOTH` EIP уже внутри GetSpectrum, поэтому сработала **правильная** защита `Z31R_FAIL_STARTUP`. Дополнительная строка `Debugger must be paused to run a script!` — запуск нового скрипта при выполняющемся процессе.

**Не ошибочная исходная адресация, не доказанный баг спектрального алгоритма.** Не просить пользователя перепроверять FRange/FFT/оригинальную подпись фильтра 20; без full Y и raw нельзя заявлять numeric parity.

## 2. Реальное исправление — один комплект, два коротких возобновления

Новый ZIP: `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_3_RESUME.zip`, размер **23670 bytes**, SHA256 `0ebbed00b5de3996a8fd8c6b36517656c80f4127bfc28800beff82cab85025f6`. ZIP в пользовательском чате, **не GitHub binary artifact**; все исходники в [`tools/research/stage111z31r_x32dbg_two_mode_capture/`](../../tools/research/stage111z31r_x32dbg_two_mode_capture/README_RU.md).

- Убран опасный монолитный `run 007D14AA` с человеческим ожиданием изменения фильтра: `Prepare-Capture.ps1` **больше не создаёт** `CAPTURE_BOTH.txt`.
- `RESUME_A_FROM_14AA.txt` начинает только при **EIP=007D14AA и коде0**, затем шесть исходных остановок/снимков. Если пользователь всё ещё на 14AA после предыдущего aborted run, может **возобновить без нового GETSPECTRUM** и без F9. Сохранение `A` до `Z31R_A_SAVED`.
- `ARM_B_ONLY.txt` (только команды `bp`, `bpcond`, без `run`) ставит условный breakpoint `007D14AA` на `[EBX+8]==0x14`. После завершения ARM и однократного F9 в оригинальном GUI выбирается **«1окт 16 кГц»** (EnvelopeCode20), затем доходим до 14AA без ложного code0 stop.
- `RESUME_B_FROM_14AA.txt`: **только при EIP=14AA/code20**, удаляет свой breakpoint, выполняет шесть исходных проверок и сохраняет B. Лог `Z31R_BOTH_COMPLETE` не означает численный паритет.
- В `A` и `B` независимые `capture_log_a_snapshot.txt`/`capture_log_b_snapshot.txt`; `Verify-Capture.py` считает текстовые маркеры только при наличии **обоих** или legacy монолитного лога, но физические Params/bin проверяет обязательно независимо от текстового лога.
- Защита указателей `mem.base`, истории ring/wrap, Fs/N, EBX/EBP/TID/кодов, no-zero-padding и одинакового end/tail **сохранены**, никаких оригинальных измерений в тестах/CI нет.

## 3. Испытания исправления

[GitHub Actions #42563110474](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42563110474): Linux **17/17 PASS**, Windows **17/17 PASS**, Windows PowerShell 5.1 prepare + SHA checks **PASS**, оба CI jobs SUCCESS. Дополнительно автономный ZIP CRC/manifest SHA256 локально верифицирован. **Проверки x32dbg на живом оригинальном Win32 после исправления ещё нет**, поэтому реальное END-TO-END принятие остаётся OPEN.

## 4. Передача пользователю: короткий порядок

1. Распаковать ZIP v1.3, запустить `Prepare-Capture.cmd`, открыть новый приватный `RUN_ME.txt`.
2. **Если EIP на 007D14AA, Paused, оригинальный код0**, не нажимать F9, не повторять `CAPTURE_BOTH`. Выполнить `scriptexec "...\\RESUME_A_FROM_14AA.txt"`.
3. После `Z31R_A_SAVED` и EIP=1900 запустить `ARM_B_ONLY.txt`, только после завершения ARM нажать F9 один раз, выбрать оригинальный пункт «1окт 16 кГц» и пересчитать спектр.
4. На новом EIP=14AA/code20 (Paused) выполнить `RESUME_B_FROM_14AA.txt`. Проверить `Verify-Capture.py`, приложить архив в **личный чат**, не GitHub.
5. Если EIP уже не 14AA/программа перезапущена, от текущего GUI в Paused **командой отладчика** `run 0x007D14AA` дождаться GetSpectrum и делать шаг 2. `scriptexec` допустим только при остановленном debuggee. Не пытаться продолжить с EIP1900 как будто это 14AA.

**Никаких изменений основной MVKView-Compatible desktop math/Native R6.1/main.** Дальше — фактический полный original same-window BIN/FIR/Y и сравнение Stage111Z31Q, не web и не остальные страницы.
