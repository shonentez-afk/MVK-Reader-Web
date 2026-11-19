## Итоговая программная приёмка 19.11.2026 — завершена

- **Кодовый SHA:** `7bfd13775ebeb0e2d99880e309345f0ca704cb66`.
- **GitHub Actions [#44489702966](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44489702966): 5/5 SUCCESS**, все задания завершены.
- Linux original Go RX/export: PASS; Python Core: **2519 passed, 141 skipped**, 30 subtests PASS.
- Windows Core: **2762 passed, 7 skipped**, 30 subtests PASS; отдельные группы Qt: **59, 50 и 194 passed**.
- Windows native QPA/font: PASS; автономный PyInstaller EXE: PASS.
- [Windows preview ZIP — `MVKViewCompatible_Stage111_Windows_Preview`, 69 468 967 байт](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44489702966/artifacts/14513555390).
- Исходный аппаратный Win32 Delphi 1:1 всё ещё НЕ подтверждён. Этот PASS относится исключительно к программной/синтетической приёмке.

# MVKView 1.0.47 — единый пакет LIVE PARAM → 15 вкладок PageStatus (19.11.2026)

**Ветка:** research/stage111-mvkview-desktop-20261029.
**Рабочий код:** 7aa4979 (Go) + fe69ecf (Python/Qt) + d2bfdfc (интеграционные тесты) + 0d2af33 (фикстура) + 2a8efc3 / 7bfd137 (fail-closed).
**Проверка:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44489702966 (проверять фактический результат; никаких PASS заранее).
**Предыдущий полностью успешный источник:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44485471309 — 5/5 PASS.

## Изученные приватные источники

Три источника проекта проверены совместно, локально и НЕ публиковались:

1. /mnt/data/Projects.7z: _Unit114.pas, _Unit115.pas, _Unit125.pas, _Unit128.pas, mvkform.dfm — каждый проверен на совпадение размера и SHA-256 с sqlite.source_files (5/5); оригинальные TMvkCellList.Add / GetValueText, constructor TACH, 15-mode dispatcher, Live FreezeUpdate.
2. /mnt/data/mvk_idr(1).sqlite: PRAGMA quick_check=ok; исходные функции 00804A30, 00805178, 008053B8 и event routes 008475F5, 0084779C, 008479FD, 00847D58.
3. /mnt/data/mvkview.idp: исходные типы/поля TMVKThread, TMvkCellList, TMvkChannelStorage, GetValueText и структурная привязка. Исходные банковые и FIR байты не извлекались в публичные файлы.

## Реализовано одним связанным пакетом

**Разрыв ДО:** Go из одного исходного TCP/10230 поддерживал 16Ki words RegisterImage, но наружу в MVK_NATIVE_LIVE_STATUS.json выводил главным образом 15 system fields и 14 internal StatusCells. На PageStatus tcStatus[1..14] Qt показывал UNKNOWN, хотя прибор мог уже передавать реальные PARAM.

**Теперь:**
- Новый Go sidecar source_live_page_status_banks (схема MVK_SOURCE_LIVE_PAGESTATUS_RAW_BANKS_V1) из *того же* Monitor.image, **без второго TCP**, без чтения из архивных BIN и без собственного подсчёта FFT.
- Сохраняются индивидуальные valid для обоих 16-битных слов каждого DWORD; нет valid → null, никакого нуля по умолчанию.
- 8 АЦП: 43 THIRD OCTAVE Float32 по +0x002+2*i; 24 RMS +0x060+2*i; 24 PEAK +0x0A0+2*i; 24 PEAK-PEAK +0x0E0+2*i; sensor ResultStatus +0x120; 8 блоков контроля raw Float32 +0x130+8*j, raw state/alert shared DWORD +0x132+8*j. База ADCn = 0x2000+0x200*(n-1).
- 2 TACH: базы 0x3000/0x3100, DWORD поля +0,+2,+4,+6,+8; +0xFE не рисуется как свежий импульс по старому full snapshot. Исходные единицы отдельных полей не трактуются как обороты.
- При исходном FreezeUpdate данные всё ещё принимаются в RAW, **но не обновляют** RegisterImage и LIVE PageStatus. Отсутствие нового PARAM не подделывает новые значения; второй реальный TCP сегмент сбрасывает RegisterImage.
- Python native_r6_live_status валидирует ВСЕ 8+2 банка, строгую схему, число элементов, размеры raw uint32 LE, исходный адрес каждого канала, accepted PARAM counter <= received PARAM, номер TCP сеанса, непризнанный Delphi GetValueText parity. Неизвестная структура с ошибкой отключает статус.
- OriginalRootShell.refresh_status переключает оригинальные ЧЕТЫРЕ TStringGrid физические QWidget и chResult. Mode0 — прежние реальные системные 15 регистров (не менялись); mode1 — 8×3 контрольных полей; modes2/3/4 — 24 позиции по 8 АЦП; modes5..12 — 43 третьоктавные полосы каждого из 8 АЦП, график разрешён ТОЛЬКО если ВСЕ 43 значения присутствуют и конечны; modes13..14 — 6 позиций TACH с последним +FE UNKNOWN. Информация на каждом экране помечена **RAW** и точным source-регистром.
- Системная ошибка Stage3, data-integrity failure, потеря актуального приёма и Stop очищают аттестованную LIVE-проекцию; чужой сеанс не может восстановить старые графики.
- Старые Go RX/Qt тесты сохраняются. Новые Go тесты проверяют реальные синтетические application PARAM, половинный DWORD, Freeze и reconnect; Python проверяет правильные/повреждённые сырые поля, все 14 non-system modes, NaN/Inf в третьоктаве и fail-closed. Qt переключает реальные таблицы и блокирует stale после разрыва.

**Привязка к оригиналу:** это восстановление исходного **пути данных до интерфейса**, но не доказательство идентичного display-форматирования Win32 TLanguage/TMvkCellList.GetValueText. В нём ещё есть сортировка, локализация и vendor-specific преобразования; поэтому значения помечены RAW, а не подделаны как «родной текст».

## Что действительно ещё не восстановлено

1. **GetValueText и control/alarm:** истинное форматирование и локализация всех 15 таблиц, интерпретация AlarmState/AlarmAlert без RAW, исходные поля порогов/конфигурации.
2. **Временная привязка:** исходные device ticks/Win32 datetime каждого поля, выборы по версии / timing UI. Текущий sidecar — последнее принятое значение RegisterImage, а не timestamp каждого DWORD.
3. **Исходная запись:** настоящий WriteTable TABLE-*.csv и WriteValues CSV по источникам 0x3100, бинарный writer/TSXML точный по времени и формату; Qt LIVE bWriteTable пока честно отключена, локальный исходный RAW и 0x3100 event/audit доступны.
4. **GetSignal/GetSpectrum:** алгоритмически близки и source SHA окон проверены, но побитовое x87 FIR/Hann/FFT/Power/Y, оригинальные курсоры и LIVE Copy/Save ещё не аттестованы.
5. **Физическое E2E:** настоящий MVK01 + оригинальный Win32 MVKView 1.0.47 на одном потоке (SetRate/ACK/DENIED/ReadTimeout/Stop/Freeze/reconnect, TIMESTAMP/регистр/CSV/огибающая). Только оператор может разрешать реальную передачу команды.

Флаг original_delphi_compatibility_verified=false остаётся обязательным.

## Контроль запретов

main не изменён. Ни одного реального сетевого подключения; никаких Flash/IP/Reboot/Task3/4/5. Приватные PAS/DFM/IDP/SQLite/PCAP/RAW/FIR не загружены в публичный GitHub или CI. Новое telemetry — локальное в папке одного Go run, bounded, validated, не содержит исходных файлов/пути или приватную модель.
