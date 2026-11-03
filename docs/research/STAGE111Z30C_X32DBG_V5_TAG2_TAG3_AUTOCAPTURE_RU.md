# Stage111Z30C V5 — автоматический original GetSpectrum захват Tag2 (ВС) и Tag3 (ВП)

Дата 03.11.2026; ветка `research/stage111-mvkview-desktop-20261029`. Scope только оригинальная MVKView 32-bit под x32dbg для офлайн архивов, без подключения МВК, изменения оригинального EXE, данных или устройства.

## Почему V5

Предыдущий V4 сохранил Tag1 три полных массива, однако пользовательский `capture.log` имел только `MVK_CAPTURE_BEGIN`, без `MVK_CAPTURE_DONE`. Три original Tag1 summary HEX оператор позднее прочитал вручную с `[EBX+30/34/38]`: `40DC8F5E`, `466D8095`, `3F475279`. По загруженному Tag1 `power_after_mode.bin` наш `original_spectrum_summary` дал все 3/3 побитово, после ранее проверенных 131072/131072 power и Y. **Tag1 ЧИСЛЕННО ПРИНЯТ**; thread/frame provenance по неподписанному capture.log остаётся отдельным ограничением.

## Новый локальный пакет V5

В текущем чате изготовлен ZIP `MVK_STAGE111Z30C_X32DBG_V5_TAG2_TAG3.zip` (SHA256 `ee000c716c1070a1a6c85b8cab7a57d31f24f994e46036ee87e558c9a5c339e5`). Содержит:

- `Prepare-Tag2Tag3.ps1` для PowerShell 5.1; создаёт уникальную локальную папку `RUN_Z30C_V5_...`, не перезаписывает старые снимки; генерирует два x32dbg скрипта `CAPTURE_TAG2.txt` / `CAPTURE_TAG3.txt`.
- `CAPTURE_MODE.template.txt`: для каждого вызова `run` к `007D154B`, `007D17E7`, `007D1900`; проверяет оригинальные opcode signatures, mode=Tag2/3, EnvelopeCode=0, N power-of-two 1024..262144, half, Fs, FRange, EBX/EBP, original storage pointer, window source position, thread ID и buffer memory validity.
- Сохраняет **8 локальных бинарных файлов на каждый Tag**: оригинальный pre-mode power / post-mode power / displayed Y полными N/2×Float32; raw `params_before.bin`, `params_after.bin`, `params_summary.bin` (по 0x3C байт); `frange.bin` (4 байта); `summary_triplet.bin` (**12 байт исходных Float32**, точка 007D1900).
- `capture.log` только диагностический; **не зависит от завершённости лога для записи summary**. В конце показывает `MVK_V5_DONE_TAG2` либо `MVK_V5_DONE_TAG3` в отдельном окне.
- `Verify-Stage30C.py` на локальной Windows с Python/NumPy: проверяет длины/числовые диапазоны, SHA256, 3 snapshots metadata, тождество `summary_triplet.bin` последним 12 байтам `params_summary.bin`; `--tags 2` можно использовать после первого режима, затем оба Tag2/Tag3 вместе для проверки одинакового исходного окна/N/Fs/FRange.
- `tests/test_static_and_verifier.py`: **8/8 PASSED** в Linux/Python offline synthetic; ZIP CRC/test integrity PASSED.

**НИ x32dbg original runtime V5, НИ Windows PowerShell 5.1, НИ реальные оригинальные Tag2/Tag3 захваты пока НЕ ПРОВЕРЕНЫ**. V5 — кандидат для первого пользовательского испытания; вывод о полной numeric parity нельзя заявлять до оригинальных файлов. Источники скриптов пока находятся в downloadable ZIP этого чата, **не закоммичены в GitHub**; в репозиторий записываются документация и численные результаты только без оригинальных raw samples.

## Применение

1. Распаковать ZIP в `C:\MVK_X32AUTO_V5`. В Windows PowerShell из этой папки: `powershell -NoProfile -ExecutionPolicy Bypass -File .\Prepare-Tag2Tag3.ps1 -Adc 4`. Заменить 4 на фактический АЦП исходного GUI.
2. В оригинальном GUI открыть сохранённый **тот же архив и канал**; выбрать «Линейный ВС» Tag2, приостановить x32dbg (F12). В нижней командной строке x32dbg ввести полный сгенерированный `scriptexec \"C:\MVK_CAPTURE\RUN_Z30C_V5_...\CAPTURE_TAG2.txt\"`. Если требуется, обновить спектр в оригинальной программе, не нажимать F9 вручную во время сценария.
3. Только после завершения Tag2: в оригинальном MVKView выбрать «Линейный ВП» Tag3, x32dbg F12, `scriptexec ...\CAPTURE_TAG3.txt`. Не смешивать остановки с другими breakpoint/потоками.
4. В этой же папке PowerShell: `python Verify-Stage30C.py \"C:\MVK_CAPTURE\RUN_Z30C_V5_...\" --tags 2` (для одного режима), после обеих `python Verify-Stage30C.py \"C:\MVK_CAPTURE\RUN_Z30C_V5_...\"`; отдельный `V5_QC_REPORT.json` без raw measurements.
5. Для сравнения с рассчитанным original-derived `_delphi_integration_power` и Float32 Y: сохранить исходные 3 крупных BIN/Tag + 12 byte triplet локально и передать пользователем в этом чате, если возможно, но **ни в GitHub, ни CI не выгружать**.

## Технические ограничения

- `savedata` снимает блок памяти, но не удостоверяет владельца процесса криптографически; `Original Win32 parity` всегда отделять от operator-supplied capture.
- Перевод Tag2/Tag3 может изменить окно, Fs или параметры. V5 verifier сигнализирует о несовпадении, **не подгоняет** измерения и не перезаписывает эталоны.
- Старые Z8/Z10/Tag1 Power/Y/summary/Copy/PNG не требовать. Native R6.1, stable main/Web, оригинальные EXE/IDP/архивы не изменять.
