# Stage111Z.27 — побайтовая сверка оригинальной MVKView и Native R6.1

**Дата:** 02.11.2026. **Проверенный код:** 554f1eb5bb8901d1c68f0ed7f0c655df6424d0ea.
**Итог Stage27A:** инструмент сравнения реализован, offline CI и Windows EXE PASS.
**Stage27B:** РЕАЛЬНАЯ оригинальная SAME-RUN BIN/TSXML byte parity **OPEN**, потому что оригинальная и Native пара одной аппаратной сессии не доступна в этой среде. Синтетические тесты не заменяют её.

## Источники, которые НЕ потеряны

- Stage52: оригинальный live writer FRange _Unit125:00808653 и источник GetFloatByAddr(0x0E), Stage51/Z23 BIN buffer, Stage61–62 оригинальный архивный loader.
- Stage111Z21: исходный _Unit125.pas:00806FF8 — DataLength штатного TSXML в БАЙТАХ; 0080703B — DataOffset=0; оригинальный ADC RealDataType=Single, отдельные Byte/Count — счётные, не Float32 ускорение; InternalChannelGain — метаданные, не команда повторной калибровки.
- Stage108/109: Native R6.1 с единственным receive-only TCP/10230 и уже проверенными RAW→BIN, Stage26B — live waveform/FFT через тот же Go приёмник. Существующие FFT goldens не изменяли.
- Локальный Projects.7z содержит исходные Pascal/DFM. Он не содержит оригинальные BIN/TSXML именно той же реальной Native записи. Временные частные копии оригинальных единиц для статической проверки удалены. Оригинальные файлы не загружались в репозиторий или CI.

## Реализация

- Core: mvk_compatible/core/original_native_parity.py — строгий локальный импорт original ADC BIN+TSXML (стандартная группа ADC1–8 или один явно декларированный канал) и SHA-verified завершённого Native ZIP. Другие приборы/неверные CRC/SHA/число каналов/RealDataType Byte как ускорение отклоняются.
- Для каждого ADC сравниваются РЕАЛЬНЫЕ биты IEEE754 Single (включая различие +0 и -0), полная длина, число отличающихся отсчётов и первые несовпадающие индексы/битовые слова. Независимо проверяются фактический Native BIN SHA из EXPORT_AUDIT, original BIN/TSXML SHA, байтовый TSXML, частота, DataLength, DataOffset, ChannelNumber, units, исходный InternalChannelGain и Native gain.
- Дополнительный bounded поиск битового сдвига и отношение чисел — ТОЛЬКО диагностические гипотезы, без авто-выравнивания и перемасштабирования. Данные исходного BIN/NATIVE не меняются.
- **Ключевая граница:** оригинальный TSXML не содержит SHA исходного TCP RAW и original first ADC sample_index. Даже если все восемь BIN совпадут, результат маркируется OBSERVED_BIN_EQUAL_BUT_SAME_RUN_NOT_ATTESTED. Отдельное доказательство общего потока требуется до объявления оригинального паритета.
- CLI: mvk_compatible/original_native_parity_cli.py — печатает агрегированный результат или сохраняет локальный JSON без перезаписи (выбор --report). Код 0 = инструмент успешно выполнил сравнение, НЕ оригинал принят; --require-bin-equal + различие = 3, ошибки входов = 2.
- Windows Qt: «Файл → Сверить оригинальный BIN с Native R6.1…»; используются существующая Native-сессия или два локальных файла, показываются результаты восьми каналов и предупреждение о неподтверждённом same-run. Во время активной записи сравнение запрещено.

Пример запуска на собственном компьютере (путь к исходному BIN из оригинала, рядом .bin.tsxml):

    python -m mvk_compatible.original_native_parity_cli "D:\Original\MVK00000084-ADC1-2026-11-02--13-00-00.bin" "D:\Native\MVK_NATIVE_R6_1_QT_VERIFIED.zip" --report "D:\Z27_COMPARE_LOCAL.json" --require-bin-equal

Ни RAW, ни BIN, ни оригинальный IDP/EXE/DFM/PAS не загружать в GitHub. Отчёт с фактическими измерениями оставлять приватным.

## Фактические результаты автоматической проверки

[GitHub Actions #41399673695](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41399673695): **все три задания SUCCESS**.

- Linux Core: **992 passed**, 3 skipped, 30 subtests.
- Windows Core: **993 passed**, 2 skipped, 30 subtests.
- Windows Qt: **44 passed**, включая сравнение через меню и защиту от действия во время LIVE.
- Go Native R6.1 test/vet/build: **PASS**; PyInstaller one-file Windows EXE со встроенным Go: **PASS**, PE/BUILD_INFO/SHA256 PASS.

[Windows Artifact id 13121007863](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41399673695/artifacts/13121007863), имя MVKViewCompatible_Stage111_Windows_Preview, ZIP **68 441 910 байт**, на 02.11.2026 expired=false.

- **SHA256 Windows EXE:** c766267c8b26cd1f5cb30c750525b3a49e4283d70a9af783d0688e4cace8c7ee
- **SHA256 загруженного artifact ZIP:** 5a7b787e43195662b8737ba5a34ef346f0651bdeb793031ee2b879fae0249a15
- **Точный протестированный commit:** 554f1eb5bb8901d1c68f0ed7f0c655df6424d0ea. Документационные коммиты после него не являются новой binary-сборкой.

## Продолжение — что не закрыто

**Stage27B DATA GATE: OPEN.** Для действительной аттестации нужна оригинальная пара 8 ADC BIN+TSXML И Native R6.1 BIN/TSXML из идентичного реального потока с независимым доказательством идентичности: RAW/PCAP, границы сэмплов, оригинальный FRange в runtime и источник времени. Только совпавший serial, близкие часы ПК или одинаковая частота ещё не доказывают одну сессию. Нельзя самовольно делать второй TCP Connect к промышленному прибору.

При отсутствии реальной парной записи НЕ повторять Stage52 или останавливать весь проект: следующий независимый этап **Stage111Z28 — полное восстановление приборных DSP/VALUES/AUX/TACH/статусов**; далее Z29 GetSignal/огибающая, Z30 полный original FFT, Z31 UI/UX 1:1, Z32 долгие записи/архив/ошибки. Все этапы в [общем мастер-плане](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).
