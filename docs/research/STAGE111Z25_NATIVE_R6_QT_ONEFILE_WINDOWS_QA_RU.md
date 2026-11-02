# Stage111Z.25 — Native R6.1 встроен в Windows Qt: финальная проверка CI и артефакта

**Дата:** 02.11.2026. **Репозиторий:** shonentez-afk/MVK-Reader-Web. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Точный протестированный source commit:** `5e299ea9b77c568b9a6431462a5fdbe525da98ca`. Следующие docs-only commits НЕ меняют это ПО.

## 1. Финальный GitHub Actions — CONFIRMED SUCCESS

**Workflow:** [MVKView Compatible - Windows EXE, run 41383158906](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41383158906). Completed, все **3 jobs SUCCESS**.

| Job | Результат |
|---|---|
| Linux - all offline core tests | 948 passed, 3 skipped, 30 subtests passed |
| Windows - offline core and Qt smoke tests | Core: 949 passed, 2 skipped, 30 subtests; Qt: **38 passed** |
| Windows - verified autonomous EXE artifact | Go Native R6.1 `go test ./...` **PASS**, `go vet ./...` **PASS**, `go build` Windows **PASS**, PyInstaller --onefile **PASS**, PE/SHA256 EXE **PASS**, артефакт загружен |

**Готовый артефакт GitHub:** [MVKViewCompatible_Stage111_Windows_Preview](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41383158906/artifacts/13113903664). Artifact ID `13113903664`, ZIP размером **68 400 740 байт**, на момент проверки `expired=false`. GitHub загрузка успешна, zip upload SHA256: `648cbd1ed0d636d6723324c27bfb5c139e11232d44db43c8f33887430d648063`. EXE `MVKViewCompatible_Stage111_PREVIEW.exe` SHA256: **`e1f27e5e2a78257942899c3b9d1c758cf05adcb1d112ae3fa0db46c4a8727e76`**, проверен в CI по фактическому файлу и контрольному манифесту. Внутри GitHub Artifact также лежат `SHA256SUMS.txt`, `BUILD_INFO.txt`, `BUILD_VERIFICATION.json`.

**Состав EXE:** CI тестирует исходники сохранённого Go R6.1 и компилирует `MVK_Native_R6_1_Stage108_Windows_x64.exe`; PyInstaller включает этот Go EXE и его SHA256 manifest в `mvk_native/` внутреннего one-file bundle. Qt при запуске отдельной записи находит внутренний Go helper в `sys._MEIPASS`, проверяет SHA256 и запускает только по явному согласию оператора. Никаких онлайн-загрузок компонента не требуется. Эта гарантия — **build provenance, checksum+offline GUI QA**, а не независимое аппаратное испытание получившегося GUI EXE.

## 2. Что точно входит в этот код

- Одна автономная Windows Qt программа, исходные 3 вкладки («Задачи», «Временной сигнал», «Спектр»), весь текущий оригинальный FFT/GetSignal/DSP-код без изменений.
- Меню и стартовая кнопка `Запись с прибора · Native R6.1`; список IPv4 сетевых карт (БЕЗ приборного TCP), ручной выбор проводного Ethernet, IP МВК, 1–300 с, лимит RAW, отдельная папка, чекбокс допуска и подтверждающий диалог.
- Приём по TCP/10230 осуществляет существующий Go Native R6.1, никогда Qt/FastAPI; на прибор прикладных команд нет. Никаких записей настроек/Modbus/Flash.
- Опциональный локальный `-stop-file` позволяет штатно вызвать context cancellation (Go Finalize и audit) без `kill`/`terminate`.
- После успешной записи Qt off-thread проверяет RAW SHA, статус `EXPORTED`, 8 BIN + 8 TSXML + VALUES/TABLE/TIMELINE, AUX provenance и 19 SHA манифеста, строит ZIP, независимый `OfflineSession` повторно валидирует его и только после этого открывает знакомые вкладки; исходные RAW/BIN не переписываются.
- Тесты отказов: отсутствующий/повреждённый Native EXE, неправильный IPv4, отсутствие approval, tampered BIN, refused Native export, устаревшая stop-file, GUI без прибора.

**Зависимость от исходной аппаратной приёмки:** Stage109 уже проверил Go R6.1 на реальном приборе №84 в 30-с тесте. Но **конкретная обновлённая one-file GUI/Go сборка Stage111Z.25 ещё не тестировалась на физическом МВК**. Не делать ложный перенос гарантии Stage109 на новые GUI/stop interactions.

## 3. Ограничения до «полного восстановления»

- Live-тракт уже можно **управлять из Qt**, но пока нет обновления трёх графиков по мере поступления кадров: после завершения и проверки открывается архив.
- Полный оригинальный BIN/TSXML byte-exact parity для одной общей записи TCP + original MVKView не подтверждён; `FRange` live source давно установлен Stage52, не искать заново.
- Для 300-с сеансов Native пишет весь RAW/калиброванные файлы, но Qt offline viewer сейчас ограничивает BIN 10 млн float32 сэмплов на канал; длинные измерения могут НЕ открываться автоматически (RAW и native export сохраняются). Это отдельно закрыть на Z.32 / worker/caching.
- Переподключение при отказе сети, источник TACH sidecar и все оригинальные DSP/Calibration UI детали, full FFT bitwise и GDI pixel parity остаются по [мастер-плану](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).
- GitHub Windows tests — headless/offscreen, не замена осмотра рабочей Windows программы с реальным монитором и оригинальной MVKView.

## 4. Дальше без потери работы

Приоритет Z.26: контролируемая проверка на пользовательском Windows ПК **сначала офлайн**, сверка видимого GUI/внутреннего Go hash/получения ZIP на локальном synthetic/replay, затем только с отдельным разрешением поля Live. После этого текущие показания + архив/прогресс/качество без второго socket клиента. Параллельно Z.27 same-run original BIN parity, Z.28–32 по мастер-плану. Stable main и Web v0.3.40 не изменены; приватные источники оригинала и реальные измерения не опубликованы.

**Обнаруженный факт при ревизии коммитов:** между предыдущей точкой `303ea16c` и протестированным source `5e299ea9` изменены только workflow, документация, `mvk_compatible/`, и Go `tools/research/native_tcp10230_stage108_live_recording_r6_1/source/` — никаких оригинальных IDP/PAS/EXE/BIN/RAW/PCAPNG.
