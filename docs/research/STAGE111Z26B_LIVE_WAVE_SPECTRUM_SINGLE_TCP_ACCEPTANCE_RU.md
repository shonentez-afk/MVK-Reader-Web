# Stage111Z.26B — живой временной сигнал и спектр через единственный Native R6.1

Дата: **02.11.2026**. Рабочая ветка: research/stage111-mvkview-desktop-20261029.
**Точный протестированный source SHA: 99c7d31acbb3df8b3c5845b51451cc5f858a411a.**
Статус: **CODE IMPLEMENTED + OFFLINE WINDOWS/CI VERIFIED. НОВОЙ АППАРАТНОЙ ПРИЁМКИ НЕТ.**

## 1. Что существовало и сохранено

- Stage52: live writer FRange _Unit125:00808653 / getter 00806964, GetFloatByAddr(0x0E). Stage61/62 — архивная ветка; Stage51/Z23 — общий BIN buffer/scaling. Ничего не исследовать повторно без нового противоречия.
- Stage108–109: аппаратно испытанный Native Go R6.1, **единственный receive-only TCP/10230** клиент, 8 ADC+2 TACH, RAW, потоковая запись 8 калиброванных Float32 BIN.partial, replay/SHA и атомарный BIN/TSXML/VALUES/TABLE. Испытание на МВК01 №84 от 29.10.2026 — относится к предыдущей версии Native, а не к нынешней GUI.
- Stage111Z25: Go recorder встроен в единый Windows Qt EXE, разрешение оператора, ручной Ethernet, stop-file, проверенный ZIP.
- Stage111Z26A: 8 ADC+2 TACH live counters/quality, настоящие статусы AUX, без дополнительного TCP.
- Ранее восстановленные GetSignal/GetSpectrum/FFT, original golden Stage111Z8/Z10, main и старая Web v0.3.40 **не изменены**.

## 2. Что реализовано сейчас

**Один Go-приёмник / оригинальный BIN без изменений:**
- Файл tools/research/native_tcp10230_stage108_live_recording_r6_1/source/live_preview.go реализует опциональное ограниченное кольцо из **8192 уже откалиброванных Float32 на АЦП** (8 каналов, максимум 256 КиБ). Копирование выполняется **после успешной записи тех же bytesOut в существующий LiveBinSpool**. Это не повторная калибровка и не второй декодер.
- Примерно раз в 750 мс публикуется локальный атомарный MVK_NATIVE_LIVE_PREVIEW.zip. Внутри MANIFEST.json с идентификатором сеанса, UTC, счётчиками RAW/кадров, фактическими sample index/rate, SHA256 Float32-фрагментов ADC1..8, обязательными признаками CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32, calibration_already_applied=true и provisional_not_audited=true. Во финальный BIN/TSXML или диагностический исходный архив preview **не подмешивается**.
- В обычном запуске Native без live-status=true не существует preview-файлов. Повторные локальные ошибки записи preview, включая краткую блокировку ZIP в Windows, не останавливают RAW/BIN и учитываются отдельно. После 5 последовательных ошибок preview отключается; исходный приём продолжается.

**Проверенный локальный Python-потребитель:**
- mvk_compatible/core/native_r6_live_preview.py принимает только маленький атомарный ZIP из того же разрешённого каталога сеанса: ограничение размеров, фиксированные имена, no symlink, 8 ADC, Float32 finite, SHA256, index/rate, UTC/stale, сопоставление счётчиков с живым приёмным статусом. При неверном источнике, примеси каналов, изменённом payload, capture_only, ошибочных кадрах и stale status **графики очищаются**.
- provisional_waveform повторно использует существующий waveform_for_zip/IDR GetSignal-кандидат. Ось времени — индекс ADC/Fs, не часы ПК.
- provisional_spectrum повторно использует **существующий** spectrum_for_zip с IDR float32 FFT и четырьмя режимами, input_domain=calibrated_bin, f_range=1.0 (BIN уже откалиброван). До 8192 реальных отсчётов, **без zero padding**; при Fs=65536 разрешение 8 Гц, полноценные 65536/262144 точки пока НЕ поддерживаются в preview.

**Qt, те же три оригинальные вкладки:**
- native_capture_dialog.py публикует captureStarted / previewReady / previewInvalid / captureEnded, используя только свой QTimer чтения локальных файлов, никакого дополнительного TCP или Modbus.
- main_window.py переиспользует существующие «Временной сигнал» и «Спектр» с явно подписанным LIVE PREVIEW и выбором АЦП1–8; четыре старых спектральных режима. Измерения и Copy/Save/Delphi курсоры НЕ выдаются за оригинал. Настройки архивного окна/FRange блокируются в live. Старые DSP/VALUES/AUX таблицы очищаются, чтобы не показывать предыдущий сеанс.
- При отказе Native/порче preview отображение очищается, старый подтверждённый архив возвращается. При успешной записи только после прежнего полного SHA-аудита новый ZIP открывается штатным OfflineSession. Сырые RAW/BIN не меняются.

## 3. Проверка (первичные факты GitHub)

**[GitHub Actions #41387495031](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41387495031)** — **ВСЕ 3 JOB SUCCESS**, исходники на SHA 99c7d31acbb3df8b3c5845b51451cc5f858a411a.

| Задание | Результат |
|---|---|
| Linux Core | **982 passed**, 3 skipped, 30 subtests |
| Windows Core | **983 passed**, 2 skipped, 30 subtests |
| Windows Qt | **42 passed**, включая provisional/restore/quality smoke |
| Native Go test / vet / build | **PASS**, уже существующий Go-приёмник |
| PyInstaller Windows one-file и PE/SHA/BUILD_INFO | **PASS**, Go EXE встроен |

**[Windows Artifact MVKViewCompatible_Stage111_Windows_Preview, ID 13116217090](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41387495031/artifacts/13116217090)**, архив ZIP **68 496 722 байта** (на 02.11.2026 expired=false), содержит GUI EXE, SHA256SUMS.txt, BUILD_INFO.txt, BUILD_VERIFICATION.json.

- **SHA256 реального Windows EXE:** 3b3e25263377d243573e5487a5027a1fae8cc2ffa376da9922db1fa358591487
- **SHA256 загруженного artifact ZIP:** 974ce49c0ab05857b95ed3d47ee6a69075816510b74bb912ebce9ad18d2ce05a
- **Source SHA** 99c7d31acbb3df8b3c5845b51451cc5f858a411a; следующие коммиты с документацией не являются новой собранной программой.

**ОГРАНИЧЕНИЕ:** это автоматическая офлайн-приёмка с синтетическими тестами, НЕ новое аппаратное испытание Windows GUI+Go на МВК. SHA preview — проверка целостности локального файла, НЕ подмена оригинального Delphi паритета.

## 4. Следующие действия по полной дорожной карте

1. **Перед подключением к прибору:** отдельный разрешённый Windows smoke/offline replay реального сохранённого RAW; проверить status/preview counters, file sharing, 8 ADC+2 TACH, safety stop, сохранение SHA RAW/BIN и что Go остаётся единственным TCP клиентом. Новую физическую сессию проводить только по допуску.
2. **Stage111Z27 (P0):** same-run независимое сравнение оригинального MVKView BIN/TSXML и Native BIN/TSXML, байт-в-байт, с исходным FRange, sample indices и time semantics. Не подставлять synthetic как оригинальные данные.
3. **Z26C / Z29–30:** расширить ограниченное live окно под исходные длинные FFT N с контролем CPU/I/O, GetSignal ring, курсоры и исходный TQGrapher, FIR/огибающая только при верифицированном локальном профиле; численный и UI 1:1 parity.
4. **Z28 / Z31 / Z32:** полные приборные DSP/TACH/status, закрытие UI/UX backlog и long run/reconnect/archive согласно мастер-плану.

Не переписывать Stage52 FRange, Stage108–109 Native, original FFT golden, stable main. Приватные оригинальные PAS/DFM/IDP/EXE/RAW/BIN/PCAPNG в GitHub не коммитить. Основная дорожная карта: [STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).
