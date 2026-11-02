# Stage111Z.28A — исходные системный DSP и два TACH по VALUES-тикам

Дата 02.11.2026. Рабочая ветка research/stage111-mvkview-desktop-20261029.
ПРОТЕСТИРОВАННЫЙ SOURCE SHA: fe55c987f85340338da4f38d41e7a6098cd28ed9.
Статус: CODE + Windows CI + ONE-FILE EXE VERIFIED. Полное оригинальное PageStatus/TACH parity НЕ проверено.

## 1. Сохранённая рабочая база

- Stage108–109 Native Go R6.1: единственный receive-only TCP/10230, 8 ADC, 2 TACH, RAW, live BIN spool, TSXML, VALUES/TABLE, SHA и архив. Его исторический hardware PASS на МВК №84 не переносить на новый EXE.
- Stage52 оригинальный FRange, Stage51/Z23 shared BIN, Stage61/62 TSXML loader, Stage111Z8/Z10 FFT goldens, Stage26B live waveform+FFT, Stage27A original BIN comparator НЕ переписаны.
- Изначально 43 реальные третьоктавы и 24 RMS/ПИК/ПИК-ПИК на ADC уже поступали из AUX4700. Нет повода повторять их DSP-расчёт.

## 2. Реализация — без второго сетевого соединения и без изменения RAW/BIN

- Go source/dsp_tach_timeline.go и маленькая правка exporter.go: TIMELINE.json расширен исходными DWORD DSP status по register word 0x1020, TACH1/2 register bank 0x3000/0x3100. С каждого проверенного VALUES 76B тика сохраняются 2 Float32 words по смещениям +0,+2 и 3 UInt32 по +4,+6,+8 на каждую TACH-банку, raw DSP status hex, исходные номера AUX/VALUES кадров и UTC время приёмного ПК.
- В существующем манифесте по-прежнему 19 файлов: 8 BIN + 8 TSXML + VALUES + TABLE + TIMELINE. SHA256 TIMELINE теперь контролирует также TACH/DSP сведения. Калиброванные BIN и оригинальный TCP RAW не менялись.
- Явные source flags: READ_ONLY_REGISTER_IMAGE_AT_VALUES_76B_TICK, HOST_RECEIVE_CLOCK_NOT_DSP_SYNCHRONIZED, tach_units_and_rpm_verified=false. Ни RPM, ни физическая частота TACH не выводятся из непринятой карты регистров.
- Python core/dsp_tach_timeline.py проверяет SHA, schema, frame order, UTC, число ticks, адреса, Uint32/Float32 и неизвестные типы. Старые архивы без полей дают UNKNOWN, а противоречивый ZIP отклоняется.
- core/offline_export.py возвращает выбранный dsp_tach tick рядом с существующими real AUX/VALUES. Проверяет nonfinite/повреждённые исходные peak, peak-to-peak и RMS, показывает сырые status_raw/status_hex и bit flags not_ready fs16/fs64/fs512; 0x00000400 не объявляется OK.
- Qt: новая внутренняя страница «Задачи → TACH / системный DSP» (не новая верхняя вкладка), текущие два тахоканала × пять исходных слов, raw system DSP, UTC/кадры/примечание о неизвестных RPM; в «Диагностика» исходные датчиковые биты. Смена tick, архива и LIVE очищает устаревшие значения.
- Source inspection private mvkform.dfm: оригинал имеет PageStatus/tcStatus/tabStatus/tabResult/tabAllResult/chResult. Полного совпадения с этой страницей по UI/UX/pixel нет.

## 3. Подтверждённый CI/Windows артефакт

[GitHub Actions #41401500558](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41401500558): ВСЕ 3 JOB SUCCESS.
- Linux offline core: 1008 passed, 3 skipped, 30 subtests.
- Windows core: 1009 passed, 2 skipped, 30 subtests.
- Windows Qt: 46 passed.
- Go Native R6.1 test/vet/Windows build PASS; PyInstaller one-file PE/SHA/BUILD_INFO PASS.
- [Artifact 13121935945](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41401500558/artifacts/13121935945) MVKViewCompatible_Stage111_Windows_Preview, ZIP 68 453 372 байта, expired=false на 02.11.2026.
- EXE SHA256: d1d94df02bdd239cfe5e1b700aa619adf5df565359ac7fda44d6a583e86010a2
- Artifact ZIP SHA256: 4c4b243db6d67f42f388fc13b1774be076ae24e337bf78f54c99c55cdc093810
- Проверенный source commit fe55c987f85340338da4f38d41e7a6098cd28ed9. Последующие docs-only коммиты НЕ означают новый проверенный EXE.

## 4. Что остаётся OPEN и дальнейший порядок

Stage111Z28A CODE/CI GATE CLOSED. Stage111Z28B ORIGINAL SOURCE/RUNTIME PARITY OPEN: 1) точные значения двух Float32 и трёх UInt32 регистров TACH, Hz/RPM/состояния; 2) оригинальные контрольные зоны, тревоги, полная PageStatus и отображение исходных tabStatus/tabResult/tabAllResult/chResult; 3) парные real screenshots оригинала и Qt; 4) новая аппаратная приёмка данного Windows GUI+Go на МВК.
Stage27B same-run original BIN/TSXML ↔ Native RAW parity всё ещё OPEN. Далее Stage29 оригинальный GetSignal/огибающая, Stage30 full FFT, Stage31 UI/UX, Stage32 long-run/архив. Не начинать заново Stage52/Native/FFT. Приватные оригинальные PAS/DFM/IDP/EXE/PCAP/RAW/BIN в GitHub не публиковать.

[Полный мастер-план](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).
