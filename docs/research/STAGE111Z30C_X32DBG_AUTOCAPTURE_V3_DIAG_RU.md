> **03.11.2026 — REAL TAG1 FIRST STOP HIT, CAPTURE DID NOT PASS:** operator screenshot Log has `MVK_CAPTURE_BEGIN EXPECTED_TAG=1 MODULE_BASE=00400000 CURRENT_EIP=765F10CC`, `INT3 breakpoint at mvkview.007D154B!`, then `MVK_CAPTURE_ABORT UNEXPECTED_BREAK_OR_WRONG_CONTEXT EIP=007D154B TID=00002CE8`. Thus `run + one-shot 007D154B` **worked**. Fail is one of the subsequent compound `bad_state` checks (params/frame/N/half/Fs/FRange/power buffer), NOT a wrong checkpoint. Capture not completed, no valid Tag1 power/Y goldens yet. Created client-side read-only `DIAG_TAG1_AT_154B.txt` which isolates 14 fail branches without run/savedata; static syntax/label checks passed, original Windows x32dbg execution not yet tested. **Keep x32dbg paused at 007D154B**, run diagnostic and report `MVK_DIAG_...` lines. Do not request another app startup or old Z8/Z10 dumps. Avoid automatic retry until root cause known.

# Stage111Z30C V3 — нет MVK_READY_CHECK_PASS: диагностика исполнения x32dbg

Дата: 03.11.2026.

## Симптом

Пользователь сообщил, что после предыдущего пакета V2 в x32dbg **не появилось** `MVK_READY_CHECK_PASS`. Это пока не позволяет отличить непопадание в Log, невыполнение скрипта, прекращение на адресе/signature либо другое состояние процесса. Не утверждать, что причина однозначно System Breakpoint.

## Исправленный локальный ZIP V3

В этой беседе создан проверенный по ZIP integrity файл `MVK_STAGE111Z30C_X32DBG_AUTOCAPTURE_V3_DIAGNOSTIC.zip`, 21795 bytes, SHA256 `2bd759fd67ad9c3123807eba23134e0ca99a1fe090b9e06e3d012d40d2e78c97`.
В архиве `MVK_X32AUTO/CHECK_READY_V3.txt`, обновлённый `Prepare-MVKCapture.ps1`, прежний `Verify-MVKCapture.ps1`, README, synthetic/static tests. Статические тесты 5/5 PASS; x32dbg live и Windows PowerShell smoke **НЕ запускались** в этой среде. ZIP доступен в текущем чате, **исходники V3 ещё НЕ коммитились в GitHub**.

## Действия

1. Оригинальный `mvkview.exe` уже открыт в **x32dbg** (не x64dbg) с офлайн-архивом, программа приостановлена F12.
2. В консоли x32dbg `log "MVK_LOG_TEST"` и убедиться, что вкладка Log не отключена.
3. Исполнить **именно** `scriptexec "C:\MVK_X32AUTO\CHECK_READY_V3.txt"` — если архив распакован именно по этому пути. Можно использовать любой реальный полный путь к этому файлу.
4. **Первое** действие V3 — модальное сообщение `MVK_CHECK_V3_SCRIPT_STARTED`. Если отсутствует — сценарий не начал выполняться; проверить существование пути, консоль x32dbg, вкладку Script и статус предыдущего сценария.
5. После OK второе модальное сообщение: `MVK_READY_CHECK_PASS` либо `MVK_V3_FAIL_...` с конкретным типом ошибки. В Log дополнительно пишутся base/EIP и три короткие opcode signatures.
6. При FAIL **не запускать CAPTURE_TAG1**, попросить скриншот окна x32dbg с EIP, Script и Log + код ошибки. Не трогать старые Z8/Z10/Z13/Z14 эталоны.

Проверка читает только исходные адреса и инструкционные байты, не вызывает `run`, `savedata`, не пишет memory/device/network. Сохранить status для нового чата; не считать original Tag1..3 golden полученными.
