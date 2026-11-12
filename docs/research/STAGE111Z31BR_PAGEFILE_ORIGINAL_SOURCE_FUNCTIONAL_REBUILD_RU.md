# Stage111Z31BR — реальное восстановление PageFile: исходные списки и параметры, рабочий локальный экспорт

**Требование владельца:** больше не тратить этапы на сравнение Power/Y/PNG до восстановления основных функций всех трёх форм и семи страниц. Работать только блоками автономное Core + оригинальная видимая Qt-страница + сквозные Windows тесты.

## Что подтверждено непосредственно по приватному оригиналу

Прочитаны оригинальные DFM/PAS, предоставленные пользователем: Projects.7z/Projects/mvkform.dfm и Projects/_Unit128.pas. Они не включаются в репозиторий и CI. MVKView IDP использовался в более ранних этапах для исходных меток и таблиц; здесь независимым основанием является оригинальная структура PageFile и исходный код обработчиков.

В DFM PageFile:
- splFile.Left=369, Width=8, Height=766; tcFileChannels.Width=369, один исходный таб, TabHeight=36, cbFileChannels — исходный TJvCheckListBox, ItemHeight=20.
- tcFileActions.Left=377, Width=615, TabHeight=36, **два исходных режима**, а не «Данные / Источник офлайн»: в режиме индекс 0 отображаются cbFileSpec (Width=256) и cbFileValues (Width=343), между ними splFileValues.Width=8.
- При переключении tcFileActions=1 исходная _Unit128:0084845C показывает pnFileAdc (Left=4, Top=42, Height=207), скрывает cbFileSpec, cbFileValues и splFileValues.
- pnFileAdc: cbFileWriteXml y=16 Checked=True; cbFileFolderPrefix y=56 Checked=True и edFolderPrefix (176,79,225,24); cbFileMvkName y=120 Checked=True и edFileMvkName (176,143,225,24); lbFilePrefix / edFilePrefix design-time Visible=False. Исходные обработчики _Unit128:0084C95C / 0084C980 меняют enabled соответствующих редактируемых строк.
- Исходный _Unit128:00844CE3..00844CF8 заполняет **10** каналов. _Unit128:0084E914 (bWriteAdcClick) передаёт 10 check flags в TMVKThread.WriteData. _Unit128:0084E988 (bWriteValuesClick) читает динамические выборы SPEC, ResultAdcCells, ResultAdcBandCells и ResultTachCellList. По уже проверенному источнику Native R6.1: 24 значения АЦП, 43 третьоктавных полосы; статический конструктор оригинальных TACH содержит 6 позиций. Формула для VALUES 24+43+6=73, однако **TACH RAW в текущем офлайн BIN не аттестован**.
- Из _Unit128:0084EDE0..0084EE9F подтверждены настройки Device\CustomName / Device\UseCustomName / Library\UseTsxml / Library\UseFolderPrefix / Library\FolderPrefix. Исходный default Library\FolderPrefix = "RunUp"dd-mm-yyyy hh-nn-ss. Интерфейсное значение Checked=True взято из оригинального design-time DFM, не утверждается, что это всегда runtime после загрузки настроек конкретного ПК.

## Исправлено одновременно в Core и Qt

### Core

Новый независимый core/original_pagefile_recording.py:
- Immutable OriginalPageFileSelection точно соответствует 10+43+73 оригинальным checkbox slots и запрещает выбирать отсутствующий ADC, отсутствующие DSP в прямом BIN и неподтверждённые TACH RAW.
- OriginalFileNameOptions соответствует исходным cbFileWriteXml, cbFileFolderPrefix, cbFileMvkName и исходной строке шаблона. Смена Checkbox управляет доступностью поля в реальном Qt. В шаблон подставляется **UTC ВРЕМЯ ЛОКАЛЬНОГО ЭКСПОРТА**, не время прибора — это явно отмечено.
- export_selected_original_pagefile выполняет реальный безопасный локальный результат: при выбранных АЦП копирует побайтно исходные BIN/TSXML (и из Native R6.1 ZIP, и из DirectBinSession); повторно проверяет SHA256 исходных файлов; из проверенного DSP/TACH выбранного тика собирает CSV только реально выбранных 24 значений/43 полос без вымышленных физических показателей. Добавляет JSON с source names/selection/hash и фактом, что original TMVKThread НЕ включался.
- Создаёт строго **НОВУЮ** папку через явный выбор пользователем, отказывается перезаписывать существующую, ограничивает размер источников и удаляет только вновь созданную папку при ошибке. Оригинальный RAW/BIN/TSXML/ZIP остаётся неизменным.

Это настоящий офлайн-экспорт выбранного исходного измерения, **не оригинальный файловый формат TMVKThread и не live запись прибора**. Исходный Native R6.1 приёмник оставлен неизменным, чтобы не выдавать выбор офлайн-параметров за аппаратные фильтры.

### Видимый Qt

В desktop/original_shell.py:
- Исходный PageFile восстановлен с 1× tcFileChannels и ровно 2× tcFileActions, оригинальным splFile, splFileValues и pnFileAdc=207, видимым только во втором режиме.
- Отдельная метаинформация вынесена из второго оригинального tab в необязательный раскрываемый блок. Существующие реальные навигационные кнопки и тики VALUES сохранены.
- cbFileChannels реально отображает все десять исходных позиций; 8 проверенных АЦП доступны, отсутствующие/неподтверждённые TACH явно помечены и недоступны. Выделение активного АЦП для графиков независимо от галочки экспорта.
- cbFileSpec и cbFileValues теперь CHECKLIST, а не plain read-only списки; на настоящем Native R6.1 ZIP 43 SPEC и 73 VALUES (24+43+6), последние 6 недоступны до подтверждения оригинальной TACH записи; DirectBIN честно показывает отсутствие приборных DSP.
- При смене АЦП/VALUES tick source-authoritative check flags не теряются и не подменяются данными другого измерения. Все поля/переключатели pnFileAdc функциональны и используются real export.
- Дополнительное безопасное действие «Сохранить выбранное локально…» работает прямо из PageFile. Оно подписано как **офлайн-операция** и не подменяет исходные bWriteAdc/bWriteValues, которые переключали TMVKThread.WriteData/WriteValues.

### Что ещё не утверждается

Оригинальная подключённая запись, WriteData/WriteValues, точное имя и байтовый формат Native MVKView исходной Windows, изменение настроек прибора, RS/Modbus-команды, source самопроверка динамических TACH flags и оригинальное форматирование locale не завершены. Нельзя объявлять полный clone. Это восстановление оригинальной структуры/параметров и реальной offline-функции.

## Приёмка

Новые Core и Windows Qt synthetic E2E:
- original DFM identity/geometry/checkbox defaults и два режима right tabs (1-index0 results, 1-index1 pnFileAdc).
- 10 source channel flags, 43 SPEC, 73 VALUES, запрет отсутствующего TACH, сохранение 7 или 8 ADC, source tick/channel immutable semantics, отдельная доступность имени и префикса.
- Native R6.1 ZIP: actual byte-equivalent BIN + TSXML, доказанный SHA256 по аудит-манифесту, выбранные rows CSV и JSON, никакие device IO.
- Direct BIN: сохранение BIN/TSXML и независимый re-open, запрет synthetic DSP.
- Защита путей, перезаписи, изменившегося источника, границы и корректный rollback.
- Windows/DPI150 скриншоты двух режимов PageFile; пользовательские исходные данные в CI не попадают.

После фактической полной GitHub Actions приёмки записать source SHA, CI ссылку, EXE и скриншоты в START_NEW_CHAT_RU.md и CURRENT_STATUS_RU.md.

## Следующий функциональный пакет

В исходном DFM есть глобальная pnMeasureControls с bWriteAdc, bWriteValues, bWriteTable, bSampleRate, bFreezeUpdate (160x41). Требуется отдельно построить source-authenticated GUI state machine для живой записи, сопоставить оригинальные флаги TMVKThread с Native R6.1 без рисков для прибора и подтвердить реальные TACH/VALUES формат и запись. После этого другие недоделанные PageStatus/PageCalib/PageStart, а не очередное сравнение одного FFT.
