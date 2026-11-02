# Stage111Z30C — автоматизация оригинального x32dbg захвата (02.11.2026)

## Статус

В текущем чате изготовлен **локальный загрузочный пакет** `MVK_STAGE111Z30C_X32DBG_AUTOCAPTURE_2026-11-02.zip` (~15,5 KB), SHA256 последней сборки `b2162cca044502de2ec3f4dd033e9646cd62ff845453599973a5b1fffb27ace8`.

Состав ZIP: `Prepare-MVKCapture.ps1`, `Verify-MVKCapture.ps1`, `README_RU.md`, `tests/Smoke-Offline.ps1`, `tests/test_static_contract.py`, `PACKAGE_MANIFEST.json`. **В репозиторий в данном этапе записана документация, НЕ сами файлы скрипта и НЕ оригинальные дампы.** ZIP пользователь может получить из чата; для долгосрочного хранения нужно дополнительно поместить текстовые исходники в отдельный путь `tools/research/stage111z30c_x32dbg_auto/` после проверки на Windows. Не утверждать, что исходники уже находятся в GitHub.

## Действие

PowerShell 5.1 `Prepare-MVKCapture.ps1` генерирует 4 отдельных готовых x32dbg `CAPTURE_TAG0/1/2/3.txt` в **новом уникальном** локальном каталоге `C:\MVK_CAPTURE\RUN_<timestamp>_<id>`. Для каждого режима один вызов `scriptexec "...CAPTURE_TAGn.txt"`: оригинальная MVKView должна работать с **офлайн-архивом, без подключения прибора**. Пользователь вручную выбирает Tag1 ВУ, Tag2 ВС, Tag3 ВП; Tag0 необязателен.

Каждый script использует только `run <RVA>` (one-shot BP), `savedata`, `cmp/Jxx`, `log` и `RedirectLog`, сначала проверяет оригинальные opcodes Stage111Y и затем строго ведёт через три точки:

1. `007D154B`: `[EBP-2C]` → `power_before_mode.bin` (N/2×Float32).
2. `007D17E7`: `[EBP-2C]` → `power_after_mode.bin`, `[EBP-30]` → `display_y.bin`.
3. `007D1900`: `[EBX+30/34/38]` оригинальные Single HEX в `capture.log`.

Сверяются исходные mode, N, Fs, EnvelopeCode=0, FRange, storage pointer, EBX/EBP, TID, window position. Отдельный verifier PowerShell проверяет лог, размеры, SHA256, Float32 QC, original one-call metadata, межрежимные N/FS/storage/FRange/window; создаёт 3 строгих локальных JSON для уже имеющихся компараторов Stage30A/30B/Z9. Никаких автоматических переключений GUI и никаких сетевых действий.

## QA / ограничения

Linux/Python static contract: **2/2 PASS**. В ZIP включён Windows PowerShell 5.1 synthetic smoke test, но **он ещё не выполнялся в текущей среде**. Нет доступа к x32dbg.exe/оригинальному Windows-процессу в этом чате; `live original script success` ещё НЕ подтверждён. Также сам Windows EXE автора, данные пользователя, private PAS/IDP, BIN, PCAPNG **не включены в ZIP/GitHub**. Вывод Stage30A/B — numerical candidate, не full original 1:1.

## Следующий шаг

Пользователь запускает только в Windows `Prepare-MVKCapture.ps1`, затем `scriptexec` для Tag1/Tag2/Tag3, `Verify-MVKCapture.ps1 -Session <path> -Adc <1..8>` и передаёт ZIP трёх папок или агрегированные отчёты. Не требовать старые Z8 power, Z10 summary, Z13 Copy, Z14 screenshot повторно. Если ошибка: проверить `capture.log` и поправить сценарий, НЕ допускать молчаливой подмены/перезаписи, НЕ менять native R6.1/main/Web.