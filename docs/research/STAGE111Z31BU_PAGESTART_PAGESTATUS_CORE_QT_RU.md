# Stage111Z31BU — PageStart + PageStatus, единое восстановление ядра и интерфейса

**ПРИЁМКА 12.11.2026:** source SHA `18ce4a67f769b86b45e114da18cbcc88cf4d53af`, [GitHub Actions #43201184322](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43201184322) — **3/3 SUCCESS**, Linux Core, Windows Core+Qt DPI150 и автономный Native R6.1 Windows EXE. [Windows EXE #13934824675](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43201184322/artifacts/13934824675) (68 877 196 байт, до 26.11.2026); [синтетические Qt скриншоты #13935836377](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43201184322/artifacts/13935836377) (624 746 байт, до 19.11.2026). Параметры DFM/PAS подтверждены по операторским приватным исходникам, Qt functional E2E — на синтетических данных; это не 1:1 исходная Win32 runtime или приборная аттестация.

**Основание:** приватные файлы владельца Projects.7z/Projects/mvkform.dfm и _Unit128.pas изучены локально. Ни один оригинальный DFM/PAS/IDP/BIN или битмап не публикуется.

## PageStart — подтверждённый оригинал

Пять исходных command-link кнопок (координаты Delphi 96 DPI): bTaskConnect (29,19,301,86) TabOrder0, bTaskConfigCh (370,19,458,86) TabOrder1, bTaskView (29,105,301,86) TabOrder6, bTaskConfigIP (370,105,458,86) TabOrder2, bTaskConfigCalib (370,193,458,86) TabOrder3, Visible=False. PAS _Unit128:00848E78/00848E60/00848E84/00848E6C/00848D78 переводят соответственно в source Mode2/6/1/4/5 (для Calib предварительный WindowMan.UserQuery). Исходные поля: edIpAddr (157,208,173,24), design-time Text=192.168.0.30, edLibraryPath (29,276,301,24), Text='*', DirectInput=False. Исходный _Unit128:00848E90 только нормализует выбранную локальную папку, не читает прибор.

**Реализация:** новый автономный Core original_start_workbench.py проверяет IPv4 без проб к сети, требует явный выбор локальной папки, обеспечивает безопасный ограниченный список настоящих ZIP/BIN/TSXML с запретом симлинков/выхода из папки и разрешает только существующие файлы. Видимый original_start_ui.py возвращает исходные прямоугольники, поля edIpAddr/edLibraryPath, команды перехода в реальные PageConfig Mode4/6, PageFile Mode1 и показ существующего NativeCaptureDialog по Mode2. Диалог по-прежнему требует ручного подтверждения оператора/Ethernet/нажатия «Начать запись»; никакой кнопке PageStart не переданы сетевые команды. Исходно скрытый bTaskConfigCalib остаётся скрытым. Дополнительный список «локальная библиотека» ясно помечен неоригинальным элементом, зато действительно открывает проверенную запись через MainWindow.open_archive и все исходные экраны.

## PageStatus — подтверждённый оригинал

Delphi DFM tcStatus имеет 2 design-time подписи и **15 runtime режимов**. В оригинале четыре разных TStringGrid, а не одна: tabStatus, tabAlarmResult, tabAllResult, tabResult. Исходные PAS обработчики:
- _Unit128:0084761A — Mode0, tabStatus, системная таблица.
- _Unit128:008476B7 — Mode1, tabAlarmResult, восемь ADC × Alarm slots, не объявлять UNKNOWN «Нормой».
- _Unit128:0084779C — Mode2..4, tabAllResult, исходные 3 банка ADC.
- _Unit128:008479FD — Mode5..12, tabResult + chResult/SpecSeries, 43 третьоктавные полосы каждого из 8 ADC.
- _Unit128:00847D58 — Mode13..14, tabResult, два TACH.
- _Unit128:0084AA20 — chResultMouseMove: CalcPosPoint → ROUND → индекс 0..42; частота из исходной 43×Float32 IDP таблицы gvar_008D2F90 и текущий реальный Y.
- Геометрия: chResult (4,42,400,720), splResult (404,42,8,720), MinSize=320.

**Реализация:** новый Core original_status_workbench.py создаёт source-bound status projection, точный выбор одного из четырёх исходных grid объектов, проверяет one-session one-tick SHA, отображает график только при 43 подтверждённых полосах, возвращает номинальную частоту из восстановленных 43 Float32 и значение реально выбранного столбца. Вместо выдуманных данных отдельный BIN без AUX/VALUES показывает UNKNOWN; peak, RPM, Alarm не пересчитываются из RMS. Реальный дополнительный локальный Save As CSV, только из проверенного Native ZIP, запрещает перезапись и выдуманный DSP, перечитывает содержимое и проверяет SHA источника. Этот экспорт прямо помечен как дополнительная совместимая функция, исходной bStatusSave в DFM нет.

Qt original_shell.py теперь имеет четыре реальные QTableWidget с исходными именами, переключает их по 15 runtime режимам, очищает неактивные таблицы от старого сеанса и выводит chart/cursor только для 43 полос; старый UI с одной общей таблицей устранён. Взаимосвязь Source MainWindow/ADC/tick/legacy-модов и общая проверка OfflineMeasurementFlow сохранены.

## Приёмка

Новые Core+Windows Qt/DPI150 тесты проверяют точные исходные координаты кнопок, исходный IP/folder input, Mode1/2/4/5/6 без фонового TCP, чтение локального ZIP через PageStart, видимое переключение четырёх таблиц и 15 режимов, 43 полосы/Float32 частоты, реальный CSV/reread/SHA, отсутствие DSP/Alarm в Direct BIN, отказ для изменённого ZIP и невозможность переписать исходный файл. Синтетические скриншоты в CI не содержат приватных оригиналов.

## Открытые ограничения

Не принята 1:1 визуальная Win32 GDI/bitmap/локализация, динамическое поведение оригинального приборного TMVKThread, физическая калибровка и реальная live аттестация исходных Alarm/TACH без отдельного полного источника регистров. Эти неподтверждённые функции остаются выключенными. Следующий приоритет: восстановление оставшихся реальных обработчиков PageAdc/PageSpectrum и комплексный сценарий работы всех 7 страниц/3 форм, Core+Qt единым пакетом, без новой серии микросравнений спектра.
