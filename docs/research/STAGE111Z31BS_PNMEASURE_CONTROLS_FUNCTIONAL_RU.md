# Stage111Z31BS — восстановление глобальной pnMeasureControls: оригинальные параметры и реальные безопасные действия

**ПРИЁМКА 12.11.2026:** исходный SHA `192ae865e43756bbc266340dacabbe5d02c3552c`. [GitHub Actions #43187577303](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43187577303) — **3/3 SUCCESS**, включая Windows Core/Qt DPI150 и автономный EXE Native R6.1. [Готовый EXE #13929896743](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43187577303/artifacts/13929896743) до 26.11.2026; [синтетические Qt screenshots #13929522299](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43187577303/artifacts/13929522299) до 19.11.2026. Точные исходные геометрии пяти кнопок и 162px кнопок PageSpectrum теперь проходят Windows Qt/150% тесты. Нет доказательства живого Win32 TMVKThread / исходного SetRate / original CSV byte parity / пиксельного 1:1.

## Источник

Подтверждено по приватным файлам пользователя Projects.7z (Projects/mvkform.dfm, Projects/_Unit128.pas). Исходники не публикуются. В исходном DFM pnMeasure имеет Height=53, Align=alBottom, BorderWidth=6, Visible=False при проектировании; дочерняя pnMeasureControls расположена Left=6 Top=6, Width=843, Height=41. Пять TButton по 160×41 имеют Left=6,172,338,504,670 и TabOrder=0..4: bFreezeUpdate, bSampleRate, bWriteTable, bWriteAdc (Tag=3), bWriteValues (Tag=8). Источник также содержит lbStatus и imStatusGood шириной 33.

## Фактически проверенная логика оригинального PAS

- _Unit128:0084DEA4 bFreezeUpdateClick переключает TMVKThread.FreezeUpdate (смещение +0x400CD), если поток существует.
- _Unit128:0084DEC4 mRate1Click берёт Tag выбранного пункта как SelectedSampleRate, вызывает TMVKThread.SetRate, меняет подпись кнопки и перерисовывает АЦП/спектр.
- _Unit128:008457F1..0084587B формирует **ровно пять** элементов popSampleRate из массива gvar_008D2F7C. Их фактические пять DWORD **ещё не прочитаны достоверно**, нельзя угадывать значения.
- _Unit128:0084E020 bWriteTableClick пишет файл TABLE-yyyy-mm-dd--hh-nn-ss.csv в каталог edLibraryPath; дословная матрица/сериализация оригинальной версии не аттестованы.
- _Unit128:0084E914 bWriteAdcClick переключает TMVKThread.WriteData (+0x400CE) и переносит десять флагов исходных каналов.
- _Unit128:0084E988 bWriteValuesClick переключает TMVKThread.WriteValues (+0x400CF), использует флаги SPEC, измерений АЦП, полос, тахометров и десяти исходных каналов. Текущий Native R6.1 не реализует эти управляющие флаги оригинального потока.

## Новый функциональный пакет ядра

В автономный модуль mvk_compatible/core/original_measure_controls.py вынесены:
- Подтверждённая геометрия, Tag и порядок кнопок, пять исходных динамических пунктов без выдуманных частот.
- Иммутабельный OriginalMeasureState: отдельные idle/offline/live, реальная частота из проверенного BIN/ZIP/Native LivePreview, привязка к session_id и отказ при чужом live-окне, отдельное состояние заморозки только экрана.
- Настоящий export_verified_table_csv: 24 измеренных VALUE и 43 BAND для каждого из восьми АЦП текущего проверенного Native R6.1 VALUES-тика; при выбранных флагах PageFile отбор реально подтверждённых VALUE/BAND/SPEC. Отбрасывает NaN/Inf, отсутствующие AUX/VALUES в Direct BIN, старые или подменённые ZIP, небезопасное имя файла или перезапись. Сохраняет UTF-8-SIG CSV с точным readback и SHA. Не выполняет FFT, не рассчитывает фальшивые приборные показатели и не раскрывает пользовательский файл в отчёте.
- Безопасность: никакой TCP/10230, Modbus, WriteData, WriteValues, SetRate, калибровочных команд, скрытого изменения Native R6.1 или остановки реального RAW.

## Новый видимый функционал Qt

В desktop/original_measure_controls_ui.py создан настоящий pnMeasure со всеми пятью исходными именами/размерами кнопок и встроен под семью исходными страницами через desktop/original_shell.py. В desktop/main_window.py синхронизированы жизненные циклы Native R6.1 и офлайн-источника.
- Idle: панель скрыта как original design-time Visible=False.
- Offline Native ZIP: доступен bWriteTable (полная проверенная таблица), bWriteValues (только выбранные подтверждённые поля PageFile), bWriteAdc (локальный экспорт выбранных BIN/TSXML уже реализованным PageFile). Всё это выполняется реально и безопасно. Панель явно подписана ОФЛАЙН, что не выдаётся за исходный connected runtime.
- Offline DirectBIN: только выбранный RAW/TSXML, без вымышленных Native VALUES или TACH.
- Live Native R6.1: bFreezeUpdate реально замораживает только отрисовку preview, при этом Native RAW запись продолжает работу; при возобновлении перерисовывается свежий проверенный пакет. Ошибочный/устаревший пакет очищает график даже во время freeze. bSampleRate показывает исключительно фактическую Fs проверенного preview; вызов SetRate не осуществляется. Исходные приборные WriteAdc/WriteValues/TABLE заблокированы во время live, поскольку они НЕ являются флагами Native R6.1.
- Реальный Native R6.1 запускается только через существующий NativeCaptureDialog с отдельным операторским разрешением. Новая панель не инициирует автоматического соединения.

## QA

Новые Core-тесты проверяют DFM coordinates/Tag/TabOrder, immutable preview session и freeze, таблицу 8×67, source selected 1×3, независимое readback CSV, SHA, отказ при подмене архива, DirectBIN/нет DSP, перезапись.

Новые Windows Qt/E2E/DPI150 проверяют исходные пять кнопок в настоящем pnMeasure, скрытие при idle, активность в offline/live, проверенную Fs, freeze/receive/thaw через синтетический LivePreview без QProcess/сокета, полный TABLE экспорт, выбор ADC и VALUE/BAND/SPEC из PageFile, безопасный экспорт исходных файлов и очистку при закрытии. Скриншоты из CI содержат только синтетические данные.

## Честные ограничения и следующий функциональный пакет

Полноценные исходные TMVKThread.SetRate/WriteData/WriteValues, точные пять частот из gvar_008D2F7C, оригинальный Win32 TABLE CSV байт-в-байт и физическая калибровка ещё не восстановлены и не проверены. Нельзя объявлять эти функции завершёнными на основании UI. Следующий крупный функциональный пакет: PageCalib — исходная схема, журнал, безопасные офлайн-расчёты и экспорт с явным запретом непроверенной калибровки прибора; далее PageStatus и недостающие обработчики PageStart/ADC. Никаких новых отдельных циклов сравнения FFT/PNG.
