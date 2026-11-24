# Stage111Z31EC — исходные WriteData/WriteValues: таймеры, Stop, финализация

Дата 24.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.
Кодовый SHA `26fa280233b98a9f77bbf64e195cc2c57da3445b`.

## Предыдущая принятая сборка EB

[Actions #45307882905](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45307882905), SHA a6a5f744d4a2b60df8ce921abc6372431511c04e: **5/5 SUCCESS**. Linux Core 2702 PASS/149 skip, Windows Core 2951 PASS/15 skip/30 subtests, Qt 60+51+195 PASS, Go RX/export PASS, native QPA PASS, EXE PASS.
[Windows ZIP artifact 14881884515](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45307882905/artifacts/14881884515), 69 569 491 байт, проверен неистёкшим на момент отчёта. Эта сборка включает EA/DZ и EB, но НЕ код EC.

## Повторная локальная проверка трёх источников

Из /mnt/data/Projects.7z через libarchive извлечены _Unit128.pas, _Unit125.pas, mvkform.dfm только в /tmp/mvk-source-local. SQLite /mnt/data/mvk_idr(1).sqlite: functions/events/components; адреса 008486F4, 0084E914, 0084E988, 00809414, 00847040. SHA256 /mnt/data/mvkview.idp совпадает с эталоном: 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438. Приватные исходники не публиковались.

- 0084E92B..0084E93C: Now -> WriteDataTime (+404E0); 0084E9A8..0084E9B9: Now -> WriteValuesTime (+404E8).
- 008488F3..00848938 и 00848A56..00848A9B: Now минус соответствующий TDateTime, формат hh:nn:ss, подпись выключения соответствующей записи.
- 008096AD..008096C4 и 00809974..0080998D: при фактическом открытии TFileStream исходный поток повторно сохраняет Now в соответствующем поле. Поэтому время операторского запроса и время открытия оригинального файла различаются. Qt показывает только проверяемый собственный таймер запроса, а не выдаёт его за Delphi open timestamp.
- 00809414..008099CF: закрытие writer-ов и stage=2; 008089A8: forced close на выходе Task2.
- 00809483..00809511: при checkbox folder prefix форматирует выбранную строку времени, формирует каталог; иначе OutputPath.
- 0080954A..008095ED: BIN = каталог + преобразованный edFilePrefix/результат 008069EC + '-' + исходное имя канала + '-' + yyyy-mm-dd--hh-nn-ss + '.bin'. 00809857..008098DB: VALUES = OutputPath + преобразованный edFilePrefix + 'VALUES-' + yyyy-mm-dd--hh-nn-ss + '.csv'. Скрытый edFilePrefix подтверждён DFM. Не считать эти строки окончательной аттестацией всех подстановок, преобразования 007B1FA4, имени прибора или локального Win32 времени. Реальные Go filenames НЕ переименовывались.

## Реальные изменения EC

1. original_live_write_stages.py: begin_finalization фиксирует единую UTC-границу один раз и прекращает operator marks; observe не принимает поздние счётчики. Два независимых elapsed_receipt, hh:mm:ss, time_basis=OPERATOR_REQUEST_UTC_NOT_DELPHI_FILE_OPEN, false Delphi parity. finish закрывает оставшиеся активные интервалы внутренней функцией без нового клика; граница полей provisional и подлежит замене финальным SHA-bound Go audit. Ошибочная mark proof не вызывает повторного открытия. Исправлен MAX_WINDOWS: учитываются закрытые И активные записи.
2. native_capture_dialog.py: новый captureFinalizing сигнал при запросе штатной остановки и выходе Go процесса ДО последнего poll и асинхронного ExportPackWorker. Не добавляет нового TCP/команд прибору.
3. main_window.py: единое условие _live_capture_stopping независимо от операторского намерения выхода. При verified VERIFYING/COMPLETED или captureFinalizing закрываются LIVE views/command gates; PageFile locks; late status и missing terminal status не сбрасывают зафиксированные pending intervals. Stop intent остаётся отдельным для capture_completion_policy. Freeze/SetRate/новая запись/запоздалые окна не разрешены. Оба pending receipts плана и ledger потребляются ДО открытия результата, чтобы отказ открытия не оставлял прежнюю запись для будущего архива.
4. original_shell.py / original_measure_controls_ui.py: общая блокировка на финализации; 20ms dispatcher показывает таймеры двух writer-ов. Неизменный caption не перерисовывается. Подпись оператора сохраняет название выключения записи и отдельную строку времени.
5. Добавлены 3 Core теста (независимые часы, неизменный stop boundary, общий лимит активных и закрытых интервалов, failed marks) и один Qt lifecycle test (VERIFYING, блокировки, late events, pending ledger). Тесты synthetic, не физическое устройство.

## Проверка

[Actions #45324239390](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45324239390) соответствует SHA EC; на момент создания отчёта выполняется. Проверить реальный итог Windows/Linux/Go/EXE, не объявлять PASS заранее. Последняя зелёная сборка EB указана выше.

## Следующий крупный блок

1. Проверить CI EC и устранить фактические регрессии, затем сверить source file names (008069EC/007B1FA4 и channel names) с подлинными BIN/TSXML/VALUES из одной сессии; не менять безопасные имена Go и SHA-привязку без доказательства. Точное время фактического открытия Delphi остаётся открытым.
2. Проверить PageStatus third-octave scale, единицы/курсор и оставшиеся режимы PageConfig/Calib, включая конфигурационное владение, отдельный Task0 и безопасную локальную калибровку. Не включать физические записи конфигурации/генератор без независимой проверки и отдельного разрешения.
3. Финальная физическая приёмка IP -> Измерить -> Task2 -> same-RX -> GetSignal/GetSpectrum -> WriteData/WriteValues -> Stop и x87/FRange/GDI/byte parity с оригинальным MVKView 1.0.47 НЕ выполнена. main, Go RX/DSP и приватные файлы не изменялись.
