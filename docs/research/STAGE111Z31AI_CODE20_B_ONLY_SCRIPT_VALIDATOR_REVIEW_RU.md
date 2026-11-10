# STAGE111Z31AI — аудит присланного GigaCode B-сценария, исправление и офлайн-приёмка (2026-11-10)

## Источники

Пользователь прислал `STAGE111Z31AE_SCENARIO_B_PACKAGE.zip`, SHA256 `05e13fca17ffb065932d6772fb4dc527ff013b80ab3d653882d3dba4af6ab7c9`. В архиве **четыре файла**: `RESUME_B_CODE20.txt` (13581B), `Verify-Capture-Code20.py` (14138B), `Preflight-GetSpectrum-Z31AE-patched.py` (11308B), `capture_config_code20.txt` (135B). Реального B-захвата FIR/FFT внутри нет; `work_raw.bin` остаётся в предыдущем приватном Stage111Z31AE ZIP (выверен в Stage111Z31AH).

## Конкретные дефекты входного GigaCode ZIP

1. **Неверная длина на `EIP=007D153D`.** GigaCode оставил `cmp [EBX+04],0x00040033` (262195) после FIR; настоящий исходный `_Unit115.pas` вызов `007D14E9` stage5 изменяет `[EBX+4]` на `(262195-51)//2=131072 = 0x20000`. Скрипт гарантированно отвергнет нормальный вызов в проверке `Z31R_FAIL_LENGTH`. Для `before_fft.bin` ошибочно предполагался размер 262195×4=1048780 вместо FFTN131072×4=524288.
2. В проверке `rawN` на 14AA скрипт требовал только `rawN>=262195`, не точного равенства. Новый guard строго `==262195`.
3. Буквальный плейсхолдер **`__OUT__`** оставлен во всех путях `savedata`/log. Готовый сценарий не должен содержать плейсхолдеров.
4. `capture_config_code20.txt` содержит `{schema=...,fft_n=...}` и **не является JSON**. При этом валидатор требует `capture_config.json` правильного JSON schema.
5. GigaCode скопировал старый двухрежимный `Verify-Capture.py`: он ВСЕГДА загружает A/ из `verify(root)`, затем B/. Для самостоятельного фильтра20 B нет A/, поэтому валидатор отклонит захват даже при правильных оригинальных массивах.
6. Обещанная последовательность «сначала на 153D проверить вручную, а затем запустить RESUME_B_FROM_14AA» **логически противоречива**: после продолжения до 153D уже нельзя повторно запускать from14AA без нового вызова. Исправленный single-pass script выполняет проверку сам и блокирует неправильные N/Fs на 153D; **ручной hold 153D требует отдельного двухфазного сценария**.

## Подтверждение по декомпилированному оригиналу

Приватный `Projects.7z/Projects/_Unit115.pas` просмотрен локально (не публиковать). В `GetSpectrum` оригинал: подготовка raw `007D14A5`, DC `007D14B3`, предварительная обработка `007D14D0`, FIR/IQ `007D14E9`, установка output Fs `007D150A`, `N/2` в `[EBX+28]` на `007D151B`, далее preFFT checkpoint `007D153D`, FFT `007D1546`, postFFT `007D154B`. FIR stage5 51 taps / decim2 → Output Fs32768, FFT N131072, Y half65536 (262144 bytes).

Сохранённая в Stage111Z31AH исходная работа preDC: `rawN=262195` SHA256 `86856251ab33201aec2ccbf43f0e33ea0bf658cd3f1112183071d13b665949c5`; исходный ADC1 BIN физический `[1703230,1965425)`; tail[51:] полностью совпадает с LOG A. Logical original `WindowEnd=557107, WindowStart=294912=StorageOldest`; memory provenance via GigaCode claim.

## Реализация

В ветку `research/stage111-mvkview-desktop-20261029` добавлено:

- [Исправленный staged x32dbg script](../../tools/research/stage111z31ai_envelope20_b/RESUME_B_CODE20_Z31AI_REVIEWED.txt) — отдельные rawN и FFTN guards, exact source-end 557107, oldest294912, source Fs65536, FRange0x43FF4853, cap2097152; снимает полный `pre_dc, after_dc, before_fft, power_before_mode, power_after_mode, display_y, summary`.
- [B-only verifier](../../tools/research/stage111z31ai_envelope20_b/Verify-Capture-Code20-BOnly.py) — модификация проверенного Stage111Z31R v1.5 `verify_one` с `B/` без зависимости от `A/`, проверкой всех sizes, stage params, ring, same logical end и битового SHA `preDC` из Stage111Z31AH. Результат намеренно называется `B_CAPTURE_FILES_VALID_NOT_NUMERIC_PARITY`, не parity PASS.
- [JSON config](../../tools/research/stage111z31ai_envelope20_b/capture_config.json), [операторская инструкция](../../tools/research/stage111z31ai_envelope20_b/README_RU.md), [offline static tests](../../tests/test_stage111z31ai_code20_b_capture_static.py).

Локально дополнительно подготовлен пользователю пакет `MVK_STAGE111Z31AI_B_CORRECTED_REVIEW.zip` с этими инструментами, офлайн README и автономными unit-тестами (в ChatGPT файлах, не GitHub; приватные данные отсутствуют).

## QA / доказательства

- На контейнере проведено **22/22** синтетических позитивных/негативных проверок двух независимых реализаций B-only verifier (14 для standalone + 8 для port v1.5, включая отсутствие A/, битовый SHA, неправильный FFTN/источник/ring/параметры/файлы).
- 16 статических инвариантов script — PASS (5 стадий, все ожидаемые массивы, отсутствуют плейсхолдеры, rawN exact, FFTN postFIR, Y).
- Реальный x32dbg **НЕ запускался и НЕ доступен из этой среды**, поэтому нельзя утверждать, что x32dbg интерпретатор принимает каждую команду или массивы оригинала совпали с клоном. Успешного raw B по `153D/154B/17E7/1900` пока нет. **Оригинал остаётся Paused на `007D14AA` по последнему отчёту GigaCode.**

## Следующее действие

GigaCode **только готовит отдельный новый каталог** `C:\MVK_LOG\STAGE111Z31AI_B_CAPTURE\B`, скачивает проверенные файлы в отдельную директорию, сверяет реально паузу EIP14AA и metadata (rawN262195, End557107, oldest294912, Code20/Mode0), сравнивает preDC с `work_raw.bin` SHA. Не выполнять `F9`, `run`, `RESUME_B` до явного согласования пользователя. Затем при разрешении один полный guarded B capture from14AA → 1900 и офлайн валидатор с передачей результатов для побитового сравнения Python/x87. Все значения показывать по фактическому дампу, а не из конфигурации. GitHub ведёт ChatGPT.
