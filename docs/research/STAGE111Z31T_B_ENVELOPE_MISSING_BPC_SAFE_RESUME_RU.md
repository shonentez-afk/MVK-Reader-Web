# Stage111Z31T — реальная ошибка No such breakpoint на B; безопасное исправление текущего сеанса

**Дата:** 09.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`. Приоритет: только СПЕКТР, original envelope same BIN/window и оригинальный full Y. Не переснимать и не изменять принятые FFT, FRange, Hann, Tag0–3/FIR банки.

## Свидетельство оператора

Пользователь находился **Paused/EIP=007D14AA**, `dword:[ebx+8]=00000014` (EnvelopeCode=20, в оригинальном меню «1окт 16 кГц»), запустил **сначала A**, но A правильно отказал `Z31R_FAIL_FILTER` (ожидал код0). После попытки B в новом логе:

```text
Log will be redirected to C:\MVK_CAPTURE\Z31R_20261109_115102_88200486\capture_b.log
Z31R_PREFLIGHT_BEGIN
Z31R_PREFLIGHT_OK: original image instruction anchors match IDP
No such breakpoint "0x007D14AA"
Error executing command!
```

Причина подтверждена кодом оригинального **нашего** инструмента: `RESUME_B_FROM_14AA.template.txt` после сравнения EIP всегда исполнял `bpc 0x007D14AA`, предполагая существующий breakpoint. Предыдущие неудачные сценарии могли его уже убрать; даже при паузе по EIP он не обязан существовать. `bpc` вернул ошибку, и B прекратился **до всех savedata**, это **не ошибка расчёта MVKView или FRange/FFT/FIR**. Скрин не доказывает никакого полного числа Y или результата FIR; физические B-файлы ещё не представлены.

## Исправление

В `tools/research/stage111z31r_x32dbg_two_mode_capture/RESUME_B_FROM_14AA.template.txt` **удалён безусловный `bpc`**. При условии `EIP=007D14AA` подтверждается code20, и выполняются прежние защищённые шаги B. Исследовательская корректность Ptr/ring/окна/EBX/EBP/TID/N/Fs/source не ослаблена, код оригинального EXE не менялся.

`Fix-Existing-B.ps1` умеет **восстановить уже созданную** папку `Z31R_YYYYMMDD_HHMMSS_GUID` без создания другого сеанса: проверяет точное содержимое legacy B и SHA старого B из `capture_config.json`, делает `RESUME_B_FROM_14AA.v13.backup.txt`, заменяет **ровно один** `bpc` на комментарий, переписывает SHA `script_b_sha256`. Не запускает x32dbg, не нажимает F9, не изменяет исходный BIN/массивы и не пытается удалять отсутствующий breakpoint. Если script уже исправлен/не тот каталог, отказ без повтора. В будущем `Prepare-Capture.ps1` генерирует правильный B из v1.4.

## Пакет и приёмка

ZIP `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_4_NO_BPC.zip`: **26 610 байт**, SHA256 `4b8009bafc6951c3e88206123ff4bf251a1b7101ca75034c8d8285f1a7b0413b`. Предоставлен пользователю как sandbox-файл. В публичный GitHub выложены только текстовые исходники/тесты инструмента и документация, без EXE/IDP/измерений.

Код commit `6e4a36d649831e25278f1e7cdb525d8a582cc3b4`.
[CI #42564978974](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42564978974): **2/2 SUCCESS**, Linux **19/19** synthetic/static, Windows **19/19** и физический Windows PowerShell5.1 smoke — в том числе тест *имитации старого сгенерированного B* `bpc 0x007D14AA`, успешная замена `Z31R_B_PATCH_OK`, сохранённый backup и неизменный A и корректное новое SHA в config. Это **не живой original x32dbg end-to-end B PASS**.

## Точные дальнейшие действия

Если x32dbg остался Paused/EIP=007D14AA/code20: **не нажимать F9** и не запускать `ARM_B_ONLY`/`RESUME_A`/старый `CAPTURE_BOTH`. Выполнить на ПК:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\MVK_TOOLS\Z31R_V14\MVK_STAGE111Z31R\Fix-Existing-B.ps1" -RunFolder "C:\MVK_CAPTURE\Z31R_20261109_115102_88200486"
```

Путь к извлечённому `Fix-Existing-B.ps1` меняется по фактической распаковке. После `Z31R_B_PATCH_OK` в командной строке x32dbg (только Paused) запустить:

```text
scriptexec "C:\MVK_CAPTURE\Z31R_20261109_115102_88200486\RESUME_B_FROM_14AA.txt"
```

При `Z31R_FAIL_*` передать лог, EIP и не давать F9. При `Z31R_BOTH_COMPLETE` **НЕ предполагать, что A существует**: это historical marker конца B-скрипта; `Verify-Capture.py` обязан отдельно найти оба физических A/B набора и проверить identical end/tail. Если A отсутствует, успешно полученный B хранить и затем снять A на той же записи без повторных общих исследований.
