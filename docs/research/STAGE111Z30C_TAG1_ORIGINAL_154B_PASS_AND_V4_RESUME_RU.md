# Stage111Z30C — реальная проверка Tag1 и восстановление захвата с текущего EIP (V4)

Дата: 03.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`. Разработка только автономной Windows MVKView Compatible.

## Операторский оригинальный runtime x32dbg

На исходном `mvkview.exe` отладчик действительно попал в **GetSpectrum 007D154B**, но прежний `CAPTURE_TAG1` остановился `MVK_CAPTURE_ABORT UNEXPECTED_BREAK_OR_WRONG_CONTEXT`. Отдельный read-only `DIAG_TAG1_AT_154B` выполнил все 14 независимых проверок и сообщил:

`MVK_DIAG_TAG1_ALL_GATES_PASS`.

Подтверждено операторским live-run: mode=1, EnvelopeCode=0, `N=262144`, `HALF=131072`, `Fs=65536`, FRange известен в оригинальном Single HEX, buffer валиден. Прежний автоматический `bad_state` — ложный отказ. **Точное конкретное выражение исходного script, давшее ложный результат, ещё не выделено**; текущая остановка верна. До успешной выгрузки файлов Stage30C S04 остаётся OPEN.

## Приготовлен пакет восстановления V4

В текущем чате создан `MVK_STAGE111Z30C_V4_TAG1_RECOVER_CURRENT_STOP.zip`, SHA256 `39a98ffb85dcfe2cc5bf3394bc410e532a27049be840168b73e872172b766e2f`, 10845 bytes. Содержимое:

- `Prepare-ResumeTag1.ps1`: создаёт **новую уникальную** локальную директорию `C:\MVK_CAPTURE\RUN_RECOVER_<timestamp>_<guid>\TAG1` и отдельный x32dbg script.
- `RESUME_TAG1_FROM_154B.template.txt`: НЕ ставит повторно `007D154B`, а начинает с уже остановленного `EIP=007D154B`, сохраняет `power_before_mode.bin`; затем однократный `run 007D17E7` сохраняет `power_after_mode.bin` и `display_y.bin`; `run 007D1900` записывает OutputMean/PeakX/PeakY и маркер `MVK_CAPTURE_DONE TAG=1`.
- Отдельные named fail branches на each original source checkpoint вместо общего `bad_state`, детерминированное сравнение `N/2` через временный регистр сценария; проверки `TID/EBX/EBP/OBJ/N/Fs/FRange/Window/EnvelopeCode`.
- `Verify-MVKCapture.ps1` — прежний локальный verifier для `-Session <path> -Tags 1 -Adc <actual>`, с SHA256 и strict JSON для Stage30A/30B/Z9.
- `tests/test_v4_static_contract.py`: **5/5 PASS** на локальном синтетическом/static contract в Linux. ZIP CRC test PASS; **реальная работа x32dbg V4 и Windows PowerShell пока не проверены**.

ВАЖНО: подготовительный PowerShell не запускает отладчик и не возобновляет приложение. Оператору следует оставить x32dbg **PAUSED** на 007D154B, распаковать ZIP, выполнить `powershell -NoProfile -ExecutionPolicy Bypass -File .\Prepare-ResumeTag1.ps1`, вставить сформированную `scriptexec` команду в x32dbg. **НЕЛЬЗЯ нажимать F9 вручную**, иначе потеряется правильный текущий стоп. Если V4 заявляет ошибку, записать её имя и оставаться в stop до анализа. От исходной пары Z8/Z10 повторные дампы не требовать.

Этот отчёт сохраняет состояние чата, но **V4 текстовые исходники и реальные BIN не закоммичены**. Исходники остаются в доступном пользователю ZIP из чата. После подтверждения Windows на Tag1 отдельно привести к той же fail-closed логике Tag2/Tag3 и сохранить тестируемые скрипты в GitHub. Ни исходный EXE/IDP, ни реальные измерения, ни обновления прибора не помещать в GitHub.
