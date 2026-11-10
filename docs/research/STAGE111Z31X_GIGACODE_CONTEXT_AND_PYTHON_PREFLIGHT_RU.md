# Stage111Z31X — контекст и исполняемая проверка для GigaCode

Дата: 09.11.2026. Назначение: **GigaCode (его собственная модель)** + x64dbg Automate MCP + оригинальная Win32 MVKView 1.0.47; не Cline/GLM. Рабочая ветка: `research/stage111-mvkview-desktop-20261029`. Привязка к состоянию: original paused EIP `007D14AA`, переход на страницу спектра прерван **до отрисовки логарифмической шкалы**.

## Автоматизированная синтетическая проверка

[GitHub Actions #42612092918](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42612092918) — **2/2 SUCCESS**: Linux Python synthetic verifier PASS, Windows Python synthetic verifier PASS, Windows PowerShell 5.1 package smoke PASS. Новый `test_preflight_getspectrum.py` проверяет в обоих окружениях запускаемый Python self-test с четырьмя кейсами и обязательность аргумента папки. Это **не испытание на оригинальном процессе MVKView** и не восстановление полного A/B захвата. Исходные BIN/IDP не использовались и не публиковались.

## Роль агента

GigaCode — оператор MCP и исследователь несовпадений. **Математику, размер/тип, endianness, смещения и критерии PASS вычисляет локальный код.** Никаких выводов «готово» по собственному текстовому пересказу 60 байт. Отчёт `main/obmen` считается операторским журналом, не оригинальным бинарным доказательством.

Перед выполнением прочитать по порядку:

1. [Второй аудит, блокирующее несовпадение SpectrumMode](STAGE111Z31W_GIGACODE_SECOND_OBMEN_AUDIT_RU.md).
2. [Source-derived capture: шесть точек и схема A/B](STAGE111Z31R_SAFE_X32DBG_TWO_MODE_CAPTURE_RU.md).
3. [Stage31U: Float32 ring type0 вместо ошибочного type1](STAGE111Z31U_FADC_DATATYPE_SOURCE_FIX_RU.md).
4. [Существующий проверщик реального A/B](../../tools/research/stage111z31r_x32dbg_two_mode_capture/Verify-Capture.py).
5. [A (plain) x32dbg source-verified сценарий](../../tools/research/stage111z31r_x32dbg_two_mode_capture/RESUME_A_FROM_14AA.template.txt) и [B (envelope)](../../tools/research/stage111z31r_x32dbg_two_mode_capture/RESUME_B_FROM_14AA.template.txt).
6. [Восстановленная FFT](../../mvk_compatible/core/fft_idr_candidate.py), [отображаемое Y из Power](../../mvk_compatible/core/spectrum_display_source.py), [принятые числовые ворота](STAGE111Z30_SPECTRUM_PARITY_OPEN_GATES_RU.md).

Не считывать весь репозиторий в промпт: использовать эти ссылки как иерархию источников. Если GigaCode получил другую версию файла или недоступен GitHub — сообщить, не выдумывать содержание.

## Точная семантика

**Params:** `[EBX+04]=N`, `[EBX+08]=EnvelopeCode`, `[EBX+18]=SpectrumMode` (ожидается 0–3), `[EBX+20]=source window end`, `[EBX+2C]=Fs` на выбранной стадии, `[EBX+30..38]=финальные 3 Float32`. Значение `[EBX+18]=0x00048000` из GigaCode `main/obmen` **BLOCK**, а не «ещё один режим»; оно дублирует подозрительно `[EBX+20]`.

**Storage:** `[EBP-4]` указывает на storage. `[Storage+04]=FRange Float32` (`0x43FF4853 → 510.56503296`), `+0C` тип 0=Float32, 2=Byte; `+10` ёмкость в **отсчётах**, `+14` маска, `+18` raw Fs, `+20` write position, `+28` earliest, `+34` Float32 **ring pointer**. `[EBP-2C]` — отдельный **work pointer**. `[EBP-30]` на `17E7` — полный Y; на `14AA` значение ещё не готово, не считать финальным Y.

Последовательность: `14AA pre-DC` → `14B8 post-DC` → `153D preFFT after FIR or plain` → `154B postFFT pre-mode Power` → `17E7 postmode Power and Y` → `1900 summary`.

Для `N=262144`: вход `1048576` байт; **каждый** массив Power/Y = `N/2*4 = 524288` байт; Float32 ring capacity `2097152` **отсчётов** = `8388608` байт. Подтверждённые ранее операторские captures Tag0–3 дали `131072/131072` побитово по Power→Y и не требуют переписывания исходного математического кода. Полная same-run/same-window A/B provenance пока OPEN.

## Новая локальная машинная проверка без MCP-запуска

[Preflight-GetSpectrum.py](../../tools/research/stage111z31r_x32dbg_two_mode_capture/Preflight-GetSpectrum.py) — только стандартная библиотека Python, **никаких вызовов Debugger/сети/установки breakpoints**. Сначала `py -3 Preflight-GetSpectrum.py --self-test`. Затем, оставляя x32dbg Paused, сохранить **прямым MCP read_memory** в отдельную приватную папку (никаких «перепечаток таблицы») шесть файлов:

- `params_at_14AA.bin` — 60 байт по текущему `EBX`.
- `params_recheck_10_2f.bin` — независимое чтение 32 байт по текущему `EBX+0x10`.
- `storage_ptr_at_14AA.bin` — 4 байта из `[EBP-4]`.
- `storage_at_14AA.bin` — 56 байт по адресy storage, **раскрытому из бинарного 4-byte pointer**.
- `locals_at_14AA.bin` — 48 байт из `EBP-0x30` (до `EBP`).
- `session_at_14AA.json` — `{"state":"paused","eip":"0x007D14AA","ebx":"0x...","ebp":"0x...","pid":123,"tid":456}` на время того же снимка; значения получить из реальных status/registers MCP, не брать из старого текста.

Пример **только чтения**:

```powershell
py -3 Preflight-GetSpectrum.py --self-test
py -3 Preflight-GetSpectrum.py "C:\MVK_CAPTURE\GIGACODE_PREFLIGHT"
```

Ожидаемый результат на нормальных синтетических тестах: `SELF_TEST_PASS`. Для реального снимка результат `STRUCTURAL_PREFLIGHT_PASS_NOT_RUNTIME_ATTESTATION` либо `BLOCK` с объяснением. **Структурный PASS не доказывает действительность memory regions, совпадение потока/кадра между остановами, original BIN-window и работу FFT.** Их требуется отдельно проверять на реальном оригинале. При `BLOCK` процесс остаётся Paused; данные/оригинальные BIN/PAS/IDP/EXE остаются локально.

## План после реального строгого PASS

Оператор явно подтверждает разрешение на выполнение. Тогда отдельный контроллер может продолжить **тот же поток и EBP/EBX/source end** по шести проверенным точкам, сохраняя локально `input_normalized_pre_dc`, `input_after_dc`, `before_fft`, `power_before_mode`, `power_after_mode`, `display_y`, параметры/тройку, и вызывает **существующий** `Verify-Capture.py`. Любой drift, неожиданное число/режим/область памяти => STOP + локальный отчёт, не догадка. Исходный GUI не обязан дорисовывать шкалу пока стоит на 14AA. Не переключаться на UI/другие страницы до завершения спектров.

## Дополнение 10.11.2026 — проверка режима целевого A/B захвата

Новый `main/obmen` (Git blob `c9a0f23f78bf8e9336082a88cacbd75a2bb67962`) заявляет локальный структурный PASS при `[EBX+0x18]=0`, но это **LOG**, тогда как стандартный Z31R A/B пакет (`Prepare-Capture.ps1`) ожидает `SpectrumType=2` (**VELOCITY**), `EnvelopeCode=0` для A и `20` для B. Сам по себе mode0 структурно допустим, однако это **не PASS заданного VELOCITY захвата**. Также `obmen` не содержит полных raw MCP ответов, полного машинного stdout/JSON и полного SHA256 файлов; реальное утверждение GigaCode нельзя независимо воспроизвести из текста. Agent отдельно сообщает, что **пересоздал** Python script после file-not-found; не подтверждено побайтовое совпадение с GitHub-источником.

Для исключения ложного PASS усилен `Preflight-GetSpectrum.py`: опциональные `--expected-mode` и `--expected-envelope` отсекают нецелевой режим и фильтр, при этом сохраняют старое поведение без флагов. Self-test теперь 6/6: прежние 4 + mode mismatch и filter mismatch. Перед новым локальным запуском использовать **оригинальный файл из этой ветки, без пересоздания/переписывания агентом**.

Операторский preflight **для запланированного plain velocity A**:

```powershell
py -3 Preflight-GetSpectrum.py --self-test
py -3 Preflight-GetSpectrum.py "C:\\MVK_CAPTURE\\GIGACODE_PREFLIGHT" --expected-mode 2 --expected-envelope 0
```

Для B требуется `--expected-mode 2 --expected-envelope 20`, но это **другой реальный снимок на EIP14AA**; не менять метаданные A на B. При текущем заявленном mode0 ожидается `BLOCK_CAPTURE_MODE` для velocity A; **нельзя исправлять байты snapshot вручную или переключать оригинальную программу ради формального PASS**. Сначала сохранить подлинные данные, зарегистрировать режим и фактическое окно, затем выбрать корректную ветку расследования. На `EIP14AA` без подтверждения не нажимать F9 и не ставить новые BP.

GitHub CI synthetic подтверждает только тесты проверщика, **не** original x32dbg и не parity.

## Жёсткие правила

- При отсутствии доказательства писать `НЕ ПРОВЕРЕНО`, а не `PASS`.
- Запрещено без отдельного разрешения: F9/run/step, новые BP, изменение регистров, патчи памяти, исходных файлов, EXE, private dumps.
- Не отправлять большие raw BIN/IDP/EXE/сигналы в облако/публичный GitHub.
- Не считать ярлыки модели (`SpectrumMode`, `FFT`, `valid pointer`) доказательством без raw data, SHA, local deterministic unpack.
- Сохранять в `main/obmen` только результат и адреса ссылок, **не приватные данные**; исследование и код остаются в research-ветке.
