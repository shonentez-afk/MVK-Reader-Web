# MVKView Compatible — текущий проверенный статус

> **Stage111Z31V — наблюдение UI при INT3:** пользователь уточнил, что при переходе на вкладку спектра оригинальная MVKView немедленно остановилась на `007D14AA`, когда логарифмическая шкала ещё не прогрузилась. Это совместимо с `GetSpectrum` до FFT: незавершённый график **не ошибка и не подтверждение mode=0/1**. Не нажимать F9 ради дорисовки до снятия исходного окна. Настоящий SpectrumMode только `[EBX+0x18]`. Зафиксировано в отчёте Z31V.


## Stage111Z31V — проверка GigaCode MCP obmen, 09.11.2026

Оператор передал полный [main/obmen](https://github.com/shonentez-afk/MVK-Reader-Web/blob/main/obmen): GigaCode через MCP дошёл до EIP 007D14AA, указал EBX=02A40E58, EBP=0019F270 и type0, но неправильно вычислил Fs из байт `00 00 01 00` как **256 вместо 65536**, FRange `53 48 FF 43` как ≈510.28 вместо **510.56503296**, неверно распознал Float32 из первых четырёх слов; ошибочно объявил `SpectrumMode=[EBX+0C]` вместо **[EBX+18]**, N262144 ≠ размер FFT и 4096 из [EBP-14] размером выходного спектра. Перепутал контрольные точки: 14B8 **после DC**, 153D **до FFT после FIR**, 154B **после FFT до mode**, 17E7 **после mode с полным Y**, 1900 **summary**. `Storage+34` ring и `[EBP-2C]` work имеют разные адреса по определению; отличие от ECX не является доказательством invalid. Оригинальный source/FFT Tag0–3 не изменять. [Полный аудит Stage111Z31V](docs/research/STAGE111Z31V_GIGACODE_OBMEN_MCP_AUDIT_RU.md).

**STOP:** НЕ запускать рекомендованные GigaCode шесть single-shot BP и F9, пока не получены сырые bytes EBX 0x3C/Storage 0x38/EBP locals через MCP и повторно детерминированно декодированы локальным Python `struct` с доказанными region/bounds. MCP+отладчик CONNECT observed, original FULL A/B parity OPEN.


## Stage111Z31U — исправлен исходный тип Float32 ring в x32dbg (09.11.2026)

**REAL пользовательский скрин:** `Z31R_B_RESUME` прошёл; дальше `Z31R_FAIL_STORAGE: ... FAdcDataType not 1`. В приватном исходнике `_Unit115.pas` `007D0A04..007D0A2F` подтверждено: **TMvkChannelStorage.FAdcDataType=0 для Float32, =2 для byte, 1 INVALID**. Прежние v1.4 B/A и `Verify-Capture.py` ошибочно проверяли type1; их синтетические тесты тоже строили type1. На текущем скрине **нет действительного значения original storage type**, поэтому реальный x32dbg numeric test остаётся OPEN; не считать установленным, что там0.

Исходный исправленный код `fcbbca15` (и workflow `3e8dfac1`): A/B и verifier теперь type0, split pointer/type ошибки, probe pointer/type/Fs перед guards, усиленный memory-region check, отдельный `Fix-Existing-Storage.ps1` для уже подготовленной папки `C:\MVK_CAPTURE\Z31R_20261109_115102_88200486` с SHA/backup и сохранением A/B/logs. ZIP **v1.5** `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_5_STORAGE_FIX.zip` (32 543 байта, SHA256 `7aff9e0546bff112f5e7001e089a9c975ce996bd9350b1529049328b2fbead5d`) доступен в чате; в GitHub только текстовые исходники. [Отчёт Z31U](docs/research/STAGE111Z31U_FADC_DATATYPE_SOURCE_FIX_RU.md).

[QA #42566735159](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42566735159) **2/2 SUCCESS**, Linux 21/21, Windows 21/21 + реальный PowerShell 5.1 patched existing B `Z31R_STORAGE_PATCH_OK`, old backup / config SHA / A unchanged. **Далее сначала пользователь в x32dbg Paused/EIP14AA/code20 читает `dword:[ebp-4]` и `dword:[dword:[ebp-4]+0x0C]`**. Если type0 — запускать патчер v1.5 и текущий B; иначе прислать тип и адрес. F9 НЕ нажимать. Оригинальные полные Y/FIR/а затем A ещё не сняты. Не возвращаться к уже принятым FFT/FRange/Tag0–3. Main/Native/десктоп не изменены.


## Stage111Z31T — устранён реальный сбой B на отсутствующем breakpoint (09.11.2026)

**REAL screenshot:** пользователь находился Paused на `EIP=007D14AA`, `[EBX+8]=0x14` (огибающая «1окт 16 кГц»); A дал ожидаемый `Z31R_FAIL_FILTER`, B прошёл preflight и остановился на `No such breakpoint "0x007D14AA"`. Это из-за нашего **безусловного `bpc 0x007D14AA` в B**, когда точки уже нет; **не численный сбой FFT/FIR**. После этого полного original B или A ещё не получено.

Исправлен [код capture v1.4](tools/research/stage111z31r_x32dbg_two_mode_capture/README_RU.md): B больше не пытается удалить отсутствующий breakpoint. Отдельный `Fix-Existing-B.ps1` патчит **именно текущую** папку `C:\MVK_CAPTURE\Z31R_20261109_115102_88200486`, создаёт backup и обновляет SHA в `capture_config.json` без вмешательства в original runtime. Пакет `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_4_NO_BPC.zip`, 26 610 байт, SHA256 `4b8009bafc6951c3e88206123ff4bf251a1b7101ca75034c8d8285f1a7b0413b`, выдан отдельно в чат. [Отчёт](docs/research/STAGE111Z31T_B_ENVELOPE_MISSING_BPC_SAFE_RESUME_RU.md), код `6e4a36d649831e25278f1e7cdb525d8a582cc3b4`.

[QA GitHub #42564978974](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42564978974) **2/2 SUCCESS**: Linux **19/19**, Windows **19/19**, настоящий PowerShell5.1 patch smoke для simulated legacy B, backup/config hash/A-unchanged PASS. Оригинальный x32dbg B после v1.4 **ещё не испытан**. Продолжить только с текущей остановки B, затем добрать A и численно сравнить; основной Desktop EXE/Native Go/математика не изменены.


## Stage111Z31S — 09.11.2026: original 14AA достигнут, исправлено прерывание сценария

**Новое REAL-ORIGINAL evidence:** на пользовательском скрине x32dbg `Z31R_READY_OK` (адреса совпали), `INT3 breakpoint at mvkview.007D14AA!` — оригинальный GetSpectrum остановлен **до DC/FIR**. ДАЛЬШЕ `Script is terminated by user`, физических A/B дампов **нет**, original численное full-Y/FIR паритет НЕ доказан. Повторный монолитный сценарий из EIP 14AA закономерно выдал `Z31R_FAIL_STARTUP`; это **не ошибка FFT**.

Подготовлен исправленный **возобновляемый** ZIP **`MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_3_RESUME.zip`** (23670 байт; SHA256 `0ebbed00b5de3996a8fd8c6b36517656c80f4127bfc28800beff82cab85025f6`), выдан в чате. Старый `CAPTURE_BOTH.txt` больше не генерируется: вместо ожидания GUI внутри длительного `scriptexec` два коротких `RESUME_A_FROM_14AA.txt` и `RESUME_B_FROM_14AA.txt` + `ARM_B_ONLY.txt` с условным `bpcond [EBX+8]==0x14`. Если пользователь всё ещё PAUSED/EIP 14AA/code0 — **начать RESUME_A сразу, без F9 и без перезапуска архива**. Изменено только исследовательское средство захвата; функции FFT/FRange/FIR/Qt/Native не менялись.

[Z31S отчёт](docs/research/STAGE111Z31S_X32DBG_REAL_14AA_STOP_RECOVERY_RU.md) · [Исходники v1.3](tools/research/stage111z31r_x32dbg_two_mode_capture/README_RU.md) · [QA GitHub #42563110474](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42563110474) **2/2 SUCCESS**, Linux 17/17, Windows 17/17 + реальный Windows PowerShell 5.1 smoke / SHA контроль. **НЕ заявлять реальный pass x32dbg после 14AA до пользовательского ZIP.** Original full-Y same-BIN и envelope остаются единственными нужными численными доказательствами для спектра.


## Stage111Z31R — единый защищённый original x32dbg захват двух режимов (09.11.2026)

**Уточнение меню 09.11:** оригинальный IDP `_Unit128` подтверждает: `EnvelopeCode=20` подписан в меню **«1окт 16 кГц»** — октавная полоса с центром 16 кГц, не 20 Гц. Промежуточная FIR частота 65536 Гц → финальная выходная Fs 32768 Гц (децимация 2), ранее установленное требование CAPTURE_BOTH было правильным. Для устранения непонятной инструкции подготовлен ZIP **v1.2** `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_2.zip`, SHA256 `fe189ce7020e95e8d883ab4302a6e93385e2049f83721190b3da1033cee6df28`, меняет только названия пунктов меню. Исправлена ошибка кавычек в PowerShell подсказке v1.1; **Windows/Linux CI #42562385095 2/2 SUCCESS** (Windows PS5.1 generator smoke). Версии ZIP v1.1 не использовать; адреса x32dbg/математика/параметры остались прежними.

**ГОТОВ К ПЕРВОМУ ОПЕРАТОРСКОМУ ТЕСТУ; НЕ заявлять original Windows runtime PASS.** Для недостающих original full-Y↔BIN/TSXML и FIR/IQ same-window собран `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE.zip` (21 290 байт, SHA256 `bcd05422fe5718439cce2523dfe3fd2f7dc7a717828d7885d23c961ce5ce0e71`, выдаётся в чате). Все **исходники и тесты** сохранены в [`tools/research/stage111z31r_x32dbg_two_mode_capture/`](tools/research/stage111z31r_x32dbg_two_mode_capture/README_RU.md). Полный [отчёт Stage111Z31R](docs/research/STAGE111Z31R_SAFE_X32DBG_TWO_MODE_CAPTURE_RU.md).

- **Один x32dbg CAPTURE_BOTH**, два прохода: A SpectrumType2 / EnvelopeCode0, затем B тот же архив/ADC4/N/Fs/Type2 и EnvelopeCode20; оператор один раз переключает фильтр. `Prepare-Capture.cmd` создаёт уникальную папку, `RUN_ME.txt` с `scriptexec` preflight и основным скриптом; `Verify-Capture.py` сверяет физические bin/Params, ring wrap, checksum/наличие full Y и одинаковое входное окно (отказ по разному source end/tail).
- Source-derived 6 остановок оригинального `GetSpectrum`: `007D14AA` preDC нормализованный Input + снимок original ring; `007D14B8` postDC/preFIR; `007D153D` postFIR/preFFT; `007D154B` full pre-mode Power; `007D17E7` full post-mode Power + full Y; `007D1900` original physical summary. Локально сверено 6/6 opcode сигнатур приватного IDP, исходный EXE/IDP/BIN/PAS **не коммитились**.
- Учтены ошибки предыдущих V2–V6: system/entry BP вместо GetSpectrum, ложный `mem.valid` V5, ограниченный V6 postFFT-only, неполный `capture.log`, невалидные указатели, разрывы TID/EBP/EBX/Params, недостаток истории, исходный ring wrap и исторические Tag2/3 разных `[EBX+20]`. Предусмотрены fail-closed guards; **не обходить ошибки напрямую**.
- [GitHub Actions QA #42547430857](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42547430857) **2/2 SUCCESS**: Linux 14/14 Python тестов, Windows 14/14 тестов **плюс проверенный реальный генератор PowerShell 5.1**. ZIP проверен CRC. ЭТО НЕ runtime x32dbg и не новое доказательство совпадения original Win32 ↔ MVK BIN; нужны файлы пользовательского захвата.
- Основной Desktop/Native R6.1, `main` и ранее принятые FFT/FRange/FIR/Tag0–3 **не менялись**, основной Windows EXE остаётся прежний подтверждённый [#42004815613](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613).

**Следующее действие:** оператор загружает сохранённый BIN №83/АЦП4 в оригинальную MVKView под x32dbg, запускает `CHECK_READY`, затем один `CAPTURE_BOTH`, передаёт приватный ZIP результата в чат. Только после этого закрывать actual full-Y/FIR same-window; исходный прибор не подключать и не подменять №83 записанным в другое время PCAP.


## GitHub Actions — завершённая очистка 06.11.2026

**Выполнено, не план:** [run #42142569340](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42142569340) **SUCCESS**. До очистки: **621** workflow run; удалено **614/614** старых завершённых запусков; после очистки осталось **7**. Результат подтверждён GitHub REST API и job log, включая `Remaining repository workflow runs ... 7`.

Сохранённые workflow runs (все SUCCESS):
- [#42004815613](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613) — последний принятый Stage111Z31Q Windows EXE, полный Y и Qt N/Fs регрессия. [EXE artifact #13404846459](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613/artifacts/13404846459) **не удалён** и был доступен при постпроверке, исходный EXE SHA256 `1fa972694805b4666743b0d91696f4486dc7d8305391fa3b26d111d4cda677f3`.
- [#42000962349](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42000962349) — Stage31P, оригинальный shared EnvelopeCode / очистка FIR-серий.
- [#41999051774](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41999051774) — Stage31O BIN/TSXML GUI E2E.
- [#40900170911](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40900170911) — контроль прежнего Stage111 desktop.
- [#41282476570](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41282476570) — последний зелёный main/Web.
- [#40632448001](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40632448001) — последний зелёный docs/reconcile.
- [#42142569340](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42142569340) — успешный запуск очистки.

Защита от удаления действующих/незавершённых проверок и перечисленных Stage111 эталонов реализована в `.github/workflows/storage-prune-once.yml` с `actions: write`, без изменения основного `stage111-desktop-offline.yml`. Публичные исходники, коммиты, SHA-отчёты, `main`, Go R6.1, исходные данные и правила расчёта не изменялись. Удаление прошлых Actions **не возвращает ранее израсходованные минуты CI**; старые Job logs и промежуточные артефакты уже недоступны. Дальше — ожидать только реальную пару original full Y + same-BIN/EnvelopeCode; принятую FFT/FRange/FIR математику заново не исследовать.


## Stage111Z31Q — продолжение СПЕКТРА: BIN→полный Y и N/Fs/курсор (05.11.2026)

**Сделан код, оригинальный same-window опыт пока открыт.** Новый локальный инструмент `mvk_compatible/private_same_window_spectrum_compare.py` (commit `4620cb5`) **повторно использует** ранее подтверждённый оригинальный Power/Y reader Stage31A, расчёт `DirectBinSession/OfflineSession.spectrum` и FIR кандидата. До сравнения **всех N/2 Float32 Y** он требует доказательства сопоставимости: операторский SHA исходного Float32 окна, АЦП, Fs, N, точные границы выборки, режим, EnvelopeCode, domain, исходный FRange из Power/Y; всё проверяет fail-closed. Отчёт даёт bitwise/ULP/первый отличающийся бин, но **не** выдаёт операторский SHA за независимую Win32-аутентификацию.

- Синтетические регрессии `test_stage111z31q_same_window_spectrum.py`: все 4 Tag0–3, SHA/канал/Fs/N/window-отказы, честное несовпадение полной кривой и локальная огибающая FIR; commit `c2a3629`.
- Qt регрессия `test_stage111z31q_qt_spectrum_edges.py`: обычные файловые BIN/TSXML, N=8192/65536/262144, Fs=16384/65536, 4 режима, dense↔sparse zoom, точный курсор, averaging1/3, бесследный выход курсора, сохранение всех N/2 Float32, исходного BIN и summary; commit `b955c9c`.
- [CI #42004815613](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613): **ALL 3/3 SUCCESS** на коде `b955c9c117b6ecf149c023dc729086cfcb232d2c`. Linux Core **1454 PASS / 65 SKIP**, Windows Core **1516 PASS / 7 SKIP**, Windows Qt **49 PASS**, Qt DPR=1.5 **46 PASS**. Go R6.1 и PyInstaller EXE построены; PE/SHA256/manifest и внутренняя независимая копия проверены. [Windows EXE artifact #13404846459](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613/artifacts/13404846459) — ZIP **68 563 855 байт**, EXE SHA256 `1fa972694805b4666743b0d91696f4486dc7d8305391fa3b26d111d4cda677f3`, GitHub upload digest ZIP `0cfd5cfb6d051913b00fae5d38aa2d1069ebab3ee62ff20a79687462647ef5c1`. **Проверка повторно скачанного артефакта на отдельном Windows ПК и original Delphi runtime parity НЕ проводились.**
- Отчёт с CLI и форматом доказательного манифеста: [Stage31Q](docs/research/STAGE111Z31Q_FULL_Y_SAME_WINDOW_SPECTRUM_AND_GRAPH_TESTS_RU.md). `Projects.7z` и `mvkview.idp` локально сверены по известным SHA. Приватные PAS/IDP, BIN/TSXML/Y, PCAP не отправлены на GitHub.
- **Открытые именно ORIGINAL-ворота:** на №83/№44 раньше были численные BIN→экран тройки; full оригинальный Y **того же** BIN и raw-window SHA в текущих вложениях отсутствует, поэтому bitwise-сквозная original аттестация не сделана. Original Win32 envelope preFFT/Y **того же окна** также отсутствует, source-derived обратная длина FIR не объявлена оригинальной runtime эквивалентностью. **Не повторять** FFT N262144 golden, 4× Power→Y original Golden, FRange source, Hann/x87, FIR коэффициенты, TQGRSeries и Native R6.1.
- Приоритет не меняется: **СПЕКТР (оставшиеся real input gates) → ВРЕМЕННОЙ СИГНАЛ → РАСЧЁТНЫЕ ДАННЫЕ → СТРАНИЦЫ**. Рабочая ветка `research/stage111-mvkview-desktop-20261029`; `main` не менять.


## Stage111Z31P — новые данные ORIGINAL SOURCE (05.11.2026)

- В приватном `Projects.7z` восстановлен **общий источник выбора кода фильтра 0–31**: `_Unit128:0084587D..0084594B` строит 32 пункта, `0084B274` синхронизирует `bAdcEnvelopeType.Tag` и `bSpecEnvelopeType.Tag`, `00846AB4` очищает обе старые серии, `00847248` обновляет активную страницу. Исходники/IDP не публиковать.
- В коде [commit 647df93](https://github.com/shonentez-afk/MVK-Reader-Web/commit/647df93b6c134d96e968c8df56175e1b85664183) зеркалируются **явные изменения** EnvelopeCode, неактивная страница пересчитывается при открытии, смена на код0 или отказ FIR убирают старую кривую и возвращают обычный FFT, ошибки очищают stale график.
- Тесты [commit 7048e3c](https://github.com/shonentez-afk/MVK-Reader-Web/commit/7048e3c0ba12cd450f8f5a76e018c4729091dd55): синтетические Tag0/1..31, no-filter, insufficient FIR, без оригинальных данных. CI [#42000962349](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42000962349) **на момент обновления выполняется, acceptance НЕ заявлена**.
- Отдельно исходник `_Unit128:00848148` проверяет `FSampleRate=SelectedSampleRate` до GetSpectrum, при несовпадении очищает график. Для неоднородных многоканальных архивов это предмет следующего source-regression gate, не новая победа в 1:1.
- **Stage31O CI уже 3/3 SUCCESS**: [#41999051774](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41999051774); [Windows artifact #13401234601](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41999051774/artifacts/13401234601).
- Подробности: [Stage31P source audit](docs/research/STAGE111Z31P_ORIGINAL_SOURCE_ENVELOPE_MENU_INVALIDATION_RU.md). Не повторять реальные 4×131072 Power/Y/Tag0-3, FFT N262144, FRange, Hann, FIR coefficients и старые BIN №83/44 численные сравнения. Открыты только **same-window original full Y**, original envelope result, дополнительные N/Fs/ADC и практическая приёмка курсора/масштабов. Приоритет: **СПЕКТР → ВРЕМЕННОЙ → РАСЧЁТЫ → СТРАНИЦЫ**.


## Stage111Z31O — реализация P0 архивного Qt E2E (05.11.2026)

- Коммит исправления `906439ba63330eb590a1bd1f7641fda2e7e27135`: при ошибке повторного чтения или расчёта BIN/TSXML `refresh_spec` теперь очищает **старую кривую, полный спектр, summary, курсор, Copy/Save и исследовательские подписи**, не оставляя предыдущий результат как актуальный. Алгоритмы FFT/FRange/Power/Y не изменены.
- Коммит теста `2464265236350b9d69af6d0d04de6eeb7ef13b5e`: `mvk_compatible/tests/test_stage111z31o_direct_bin_gui_e2e.py` открывает **настоящий синтетический файловый** BIN+TSXML через `MainWindow.open_archive`, выполняет `refresh_spec` для всех Tag0–3, сравнивает N/2 и Float32 raw, source-derived плотный min/max→редкий zoom→плотный, bin-based курсор, Copy/Save с явной пометкой некалиброванности, и fail-closed при SHA-изменении BIN без ложной старой кривой. Это **не** x32dbg оригинальный Golden и **не** новый реальный приборный тест.
- Запуск GitHub Actions [#41999051774](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41999051774) автоматически создан для последнего code-коммита; **на момент записи результат CI/EXE ещё не подтверждён**. Предыдущий подтверждённый зелёный EXE остаётся Stage31N, code `a4d00c80...`, run #41988511152, artifact #13397357837.
- **Следующий шаг в рамках СПЕКТРА**: проверить завершение CI, исправить только выявленные E2E отклонения, затем использовать имеющиеся исходные BIN №83/№44 для отсутствующей full-Y same-window сверки **только если доступна исходная оригинальная полная кривая**, и закрывать envelope original runtime по той же паре окон. Без новых повторных FRange/FFT/Tag0–3 исследований. `main` и старый Web без изменений.


**Дата аудита: 05.11.2026.** Этот файл — единая точка входа для следующего этапа. Ветка: `research/stage111-mvkview-desktop-20261029`. Цель — автономный Windows-аналог **MVKView 1.0.47** с встроенным проверенным Go Native R6.1. Ветка `main` содержит прежний Web v0.3.40, её не менять.

**Приоритет по прямому решению пользователя:** расчёты и вывод графиков важнее точного повторения шрифтов. **Порядок:** довести СПЕКТР → ВРЕМЕННОЙ СИГНАЛ → РАСЧЁТНЫЕ ДАННЫЕ → оставшиеся страницы.

## 0. Подтверждённая сборка

- Тестированный код: `a4d00c80f3a70e85fa43d96564b43ea86a0eafe6`. На момент аудита ветка: `88d67140519887402175f5e9e7b8b3f0db46ddca`. GitHub compare подтвердил: **после протестированного кода четыре коммита затронули только документацию**.
- [GitHub Actions #41988511152](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41988511152): **3/3 SUCCESS**; Linux Core **1438 passed / 53 skipped**; Windows Core **1488 passed / 7 skipped**; Windows Qt **49 passed**; Qt при фактически измеренном DPR=1.5 **46 passed**. Go R6.1 build/test, PyInstaller onefile, PE/SHA/manifest — PASS.
- [Windows EXE artifact #13397357837](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41988511152/artifacts/13397357837): ZIP **68 559 023 байта**, EXE SHA256 `21cb15ea1c51a300c5c9f285069d176cee363b66fc692d9ecb679a1eba3b3922`; GitHub срок хранения **до 19.11.2026**.

**Доказательность:** REAL-ORIGINAL = пользовательские original BIN/x32dbg/скрин/числа; REAL-DEVICE = реальный аппаратный Native тест; SOURCE = реконструкция исходного алгоритма/таблиц; CI/SYNTHETIC = автоматический тест нашей реализации, **не** новая оригинальная runtime-пара. Старые оригинальные BIN/PNG не опубликованы и не пересчитаны заново в этом аудите.

## 1. УЖЕ СДЕЛАНО — НЕ НАЧИНАТЬ ЗАНОВО

| Компонент | Что именно принято | Уровень и источник |
|---|---|---|
| FFT GetSpectrum | Оригинальный операторский preFFT→Power, `N=262144`, **131072/131072 Float32 побитово** в одном реальном захвате; история original stream/thread не удостоверена независимо. | REAL-ORIGINAL, [StageZ8](docs/research/STAGE111Z8_FIRST_NONZERO_ORIGINAL_FFT_262144_BITWISE_GOLDEN_RU.md) |
| Tag0–Tag3 | По каждому отдельному оригинальному захвату полные `Power→Y` **131072/131072 Float32 bitwise**, итоговая тройка original summary **3/3 Float32 HEX**. Tag2/Tag3 имеют разные original window metadata — **не утверждать общую временную выборку**. | REAL-ORIGINAL, [Tag0](docs/research/STAGE111Z30C_TAG0_ORIGINAL_LOG_FULL_Y_131072_BITWISE_FOUR_MODES_RU.md), [Tag1](docs/research/STAGE111Z30C_TAG1_POWER_AND_Y_FIRST_FULL_OPERATOR_CAPTURE_RU.md), [Tag2](docs/research/STAGE111Z30C_TAG2_ORIGINAL_INTEGRATION_Y_SUMMARY_131072_BITWISE_RU.md), [Tag3](docs/research/STAGE111Z30C_TAG3_ORIGINAL_DOUBLE_INTEGRATION_Y_SUMMARY_131072_BITWISE_RU.md) |
| FRange | Уже установлены `GetFloatByAddr(0x0E)`, исходный writer/reader, `InternalChannelGain` TSXML, fallback, оригинальная Float32 подготовка `buffer/FRange`, отсутствие двойной калибровки BIN. Original Tag0 `0x43FF4853 = 510.5650329589844`. **Не перепроверять заново происхождение/формулу.** | SOURCE + one original word, [Stage52](docs/research/STAGE52_FRANGE_ORIGIN_RU.md), [61–62](docs/research/STAGE62_ARCHIVE_FRANGE_SOURCE_RU.md), [Z24](docs/research/STAGE111Z24_RECHECK_STAGE52_FRANGE_AND_NATIVE_R6_1_RU.md) |
| Hann/x87 | Полная независимая C/x87 реконструкция periodic Hann **262144/262144** совпала с нашим кандидатом; 4 исходных слова отдельно подтверждены, синтетический C/x87 FFT совпал с Python на 6 размерах. | SOURCE+SYNTHETIC, [Stage31K](docs/research/STAGE111Z31K_SPECTRUM_CALCULATION_AUDIT_RU.md), [31L](docs/research/STAGE111Z31L_X87_FFT_ORACLE_PRIOR_ORIGINAL_GOLDEN_RU.md) |
| Реальный BIN→оригинальные цифры | **Прибор №83 АЦП4 (23.10):** из BIN 37.5944 Гц, 4.157 мм/с, 4.611 мм/с; оригинальный экран 37.59 Гц, 4.176 мм/с, 4.620 мм/с. **Прибор №44 АЦП1:** BIN 9.2902 мм/с, 14.25 Гц, 6.3791 мм/с; экран 9.29 мм/с, 14.5 Гц, 6.37 мм/с. **Сверка УЖЕ была**, но №44 пик отличается на 0.25 Гц; это не побитовое сравнение всех Y-бинов. Операторские исходные файлы/скриншоты здесь не перезапускались. | REAL-ORIGINAL historical, [сводный аудит](docs/research/STAGE111Z31N_REUSE_FIRST_SPECTRUM_VALIDATION_RU.md) |
| Оригинальный и Qt скрин одного спектра | Исходный **Tag0 x32dbg Power/Y** был загружен в Qt напрямую, сравнен с оригинальным screenshot: курсор **3800 Гц/−55.32 дБ**, summary **6.89 / 3800 / 0.7786**; нормализованная геометрия ~0.53/0.21 px. **Это SAME-Power/Y, НЕ пересчёт того же BIN.** Скрин Stage31B с АЦП1/−1.746 дБ — ДРУГОЙ BIN; не принимать его за same-data. | REAL-ORIGINAL SCREEN+Qt, [Z14](docs/research/STAGE111Z14_ORIGINAL_SPECTRUM_SCREENSHOT_PIXEL_REFERENCE_RU.md), [31B](docs/research/STAGE111Z31B_FIRST_QT_SCREENSHOT_1920_VISUAL_AUDIT_RU.md), [31C](docs/research/STAGE111Z31C_WINDOWS_150_PERCENT_DPI_QT_SOURCE_VISUAL_PARITY_RU.md) |
| Источник графика/курсор/шкалы | Source `TQGRSeries`: `DataSize=TRUNC((N/2)/1.28)`; при N262144 Fs65536 видны 102400 бинов, правая граница оси **25600 Гц**, а не Nyquist32768. Min/max per pixel, курсор, исходные 10 горизонтальных и 6+6 вертикальных шкал/6 FFT N восстановлены по оригиналу. Отдельные позиции курсора подтверждены скриншотами. | SOURCE + chosen real screenshots, [31H](docs/research/STAGE111Z31H_TQGRSERIES_SOURCE_PIXEL_COLUMNS_RU.md), [111S](docs/research/STAGE111S_SOURCE_SPECTRUM_SCROLLBARS_RU.md), [111T](docs/research/STAGE111T_VERTICAL_AND_SOURCE_FFT_RU.md) |
| Native Go R6.1 | Прибор №84: **30.0128 сек**, RAW **69 685 884/69 685 884 байт** совпал с независимым PCAP-prefix; **15 725 824/15 725 824** Float32 исходных BIN проверены, 8 ADC+2 TACH, 19 экспортируемых файлов, 0 client→device прикладных байтов. Это проверка **отдельного приёмника**, не новой Qt-интеграции. | REAL-DEVICE, [Stage109](docs/research/STAGE109_R6_1_FIRST_REAL_LIVE_DEV84_ACCEPTANCE_RU.md) |

## 2. РЕАЛИЗОВАНО И ЗЕЛЁНО В CI, НО ОРИГИНАЛЬНЫЙ 1:1 НЕ ДОКАЗАН

| Возможность | Есть в приложении | Точная граница |
|---|---|---|
| Архивы | Read-only Native ZIP, `DirectBinSession` для оригинального BIN+TSXML `RealDataType=Single` (ADC1–8, при наличии групп). Каналы, длина/offset, SHA/метаданные проверяются. | Счётные `Byte` данные обоснованно **не** преобразуются в ускорение. Некоторые исходные TSXML/fallback-условия оригинала и фактические физические единицы не приняты повсеместно |
| Обычный спектр | `refresh_spec`: все N/2 для расчётов, Tag0–3, выбор N/режима/окна, original-derived summary, вывод Copy/Save, шкалы, оригинальная плотная min/max кривая с возвратом всех исходных точек при zoom (Stage31N). | **Последний Stage31N Qt тест инжектирует синтетические `_full_spectrum` и `session=object()`**. Тест полного GUI-пути `DirectBinSession.open→refresh_spec→zoom→cursor→Copy/Save` с новым плотным рендером отдельно пока не сделан |
| Огибающая | Исходные 10 банков FIR×512 по локальному `mvkview.idp`, IF/IQ и cascading decimation, source-derived `/FRange` до FIR, 4 режима после FFT; **6493/6493 Float32** source scalar vs optimized на синтетике с настоящими коэффициентами. | Не сравнен **original Win32 full envelope Y** на том же pre-FIR окне/EnvelopeCode. Профиль оригинальных FIR пользователь загружает локально, в EXE не вшивается |
| Временной сигнал | Вкладка и offline waveform, исходная выборка окон GetSignal latest/sequential, курсор/сегменты, ограниченный live preview реальных 8192 отсчётов через один Go receiver. | Нет оригинального полного GetSignal return Float32 той же записи и подтверждения всех окон/полос |
| DSP показатели / задачи | 24 штатные DSP величины, 43 приборные третьоктавы, датчики, статусы, необработанные TACH-регистры, исследовательские 15 PageStatus modes из AUX/VALUES. При BIN-only отсутствующие AUX не выдумываются. | Не доказаны оригинальные коэффициенты третьоктавных DSP-фильтров, alarm thresholds, TACH RPM/полная физика, не все 15 режимов оригинального UI |
| Live + GUI | Один встроенный Go R6.1, Start/Stop по допуску, live preliminary waveform/spectrum на 8192/ADC, журнал/статусы/финальный ZIP. | Интегрированный **Qt+Go на реальном Windows-приборе ещё не испытан**; live 8192 не равно full original N262144, recovery и long-run остаются открытыми |
| Интерфейс | 3 действующие верхние вкладки **«Задачи», «Временной сигнал», «Спектр»** и несколько рабочих подстраниц задач. Исходные 7 Page* из DFM известны. | Полная оригинальная PageConfig/PageCalib/PageFile/PageStatus UI-функциональность и мастер по всем страницам **НЕ закончены**, по решению пользователя отложены |

## 3. ДЕЙСТВИТЕЛЬНО ОСТАЛОСЬ — по приоритетам

### P0. Спектр: не переписывать уже принятую математику

1. **Единый E2E регрессионный маршрут обычного архива**: на локальном синтетическом BIN+валидном TSXML пройти через настоящее Qt открытие, `refresh_spec`, dense→sparse zoom, курсор/scale/copy/save; проверять неизменность полного N/2 Float32 и приборных частот. **Это выявленный при аудите отсутствующий тест для кода Stage31N, не повторная оригинальная съёмка.**
2. **Сквозная проверка полного Y из реального BIN на одинаковом окне**, не только 3 итоговых цифр. Использовать **уже полученные** дела №83/№44 и существующие `stage83_compare_spectra.py`, `private_getspectrum_*.py`. Если реального полного original Y/CSV по соответствующему BIN нет, честно оставить это data gate, сохранив предыдущую успешную проверку чисел; **не просить переснять старые скрины**.
3. **Огибающая**: сопоставить full original Win32 result post-FIR/pre-Hann или Y с нашим из того же окна с подтверждёнными EnvelopeCode/FRange. FIR и source структурно уже восстановлены, повторно коэффициенты не искать.
4. **Курсор/масштабы/пики/форматы**: функциональные тесты всех 4 режимов, края диапазонов/N/Fs, averaging/precise, переходы dense/sparse, Copy/Save, вторая серия; при необходимости исправлять только конкретное отличие **на числах и графике**, не на Tahoma.
5. Проверить ещё 1–2 **других** реальных N/Fs/канала только при наличии старых доступных записей; не объявлять универсальную побитовую эквивалентность по 4 original эталонам.

### P1. Интеграция и долговременная запись

- После спектра/в рамках полевой приёмки протестировать **один** реальный сеанс встроенного Qt+Go, более долгую запись и штатный Stop/обрыв/сохранение. При доступном одинаковом исходном потоке использовать **уже готовый** [original BIN ↔ Native R6.1](docs/research/STAGE111Z27_ORIGINAL_NATIVE_SAME_RUN_BIN_TSXML_COMPARATOR_RU.md). **Same-hardware-session оригинальный парный BIN ранее отсутствовал**; Stage109 подтверждает собственный приёмник, не оригинальную MVKView byte parity. Не создавать второго TCP-клиента и не подключаться без допуска оператора.

### P2. Только после принятого спектра — GetSignal

- Использовать имеющиеся исходные GetSignal/window/ring/waveform и приватный comparator, дополнить реальный original GetSignal Float32 return того же интервала, фильтры, курсор, экспорт. **Не начинать GetSignal с нуля.**

### P3. Затем приборные расчёты и остальные страницы

- Добрать original DSP/third-octave formula parity, TACH RPM/Alarm, оригинальные PageConfig/PageCalib/Status/File и UI/UX, полевую приёмку. **Не путать DSP 43 третьоктавы с обычным FFT GetSpectrum.**

## 4. Что ЗАПРЕЩЕНО повторять и публиковать

Не делать заново **FFT N262144; Tag0–3 Power→Y; original summary; FRange writer/reader/formula; Hann; 10×512 FIR source; TQGRSeries min/max; курсор Tag0; Native R6.1; существующие бин/CSV-компараторы**. Не возвращаться к старой Web-архитектуре.

Не загружать в GitHub или CI приватные оригинальные PAS/IDP/DFM, user PCAPNG/RAW/BIN/TSXML/Power/Y, original EXE/скриншоты; хранить только отчёты, SHA, исходно-производный код и синтетические тесты.

**Практическое определение «спектр готов»:** все четыре режима воспроизводятся, частоты/СКЗ/пики/единицы правдоподобны и проверяемы на принятых эталонах, при увеличении/уменьшении не пропадают пики, курсор/масштабирование/экспорт работают, архивный E2E тест зелёный, ограничения огибающей и несинхронных исходных данных чётко оговорены. **Полное доказательство для всех возможных входов не обещать.**

### Главные ссылки

[Исторические BIN/скрин сравнения](docs/research/STAGE111Z31N_REUSE_FIRST_SPECTRUM_VALIDATION_RU.md) · [Аудит численного GetSpectrum](docs/research/STAGE111Z31K_SPECTRUM_CALCULATION_AUDIT_RU.md) · [Stage31N исходный рендер обычного архива](docs/research/STAGE111Z31N_ARCHIVE_GRAPH_NUMERICAL_PRIORITIES_RU.md) · [Исторический мастер-план](docs/research/STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md). При конфликте старого OPEN с более поздней оригинальной приёмкой использовать **данную матрицу + конкретный эталонный отчёт**, не исторический заголовок.
