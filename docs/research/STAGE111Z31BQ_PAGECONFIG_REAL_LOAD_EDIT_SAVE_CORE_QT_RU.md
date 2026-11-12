# Stage111Z31BQ — реальное восстановление PageConfig: Load / Edit / Save

**ПРИЁМКА:** исходный SHA `1d07f18272ed74643c44e7949a31fb591a779859`, [GitHub Actions #43177032123](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43177032123) — **3/3 SUCCESS** (Linux Core, Windows Core+Qt/DPI150, one-file Windows EXE Native R6.1). [EXE #13924757748](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43177032123/artifacts/13924757748) до 26.11.2026, [synthetic Qt #13924309197](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43177032123/artifacts/13924309197) до 19.11.2026. Подтверждена локальная Load/Edit/Save/reload, не аппаратная запись и не исходная Delphi Win32 абсолютная совместимость. Тесты используют подлинные IDP FmtChar вместо старых условных D/F.


## Приоритет

После Stage BM–BO пользователь потребовал прекратить отдельные сравнения и перейти к реальному восстановлению оригинальных окон и команд. Этот пакет расширяет рабочую функциональность PageConfig и второй оригинальной формы mvkeditform; ни одна новая функция сравнения спектра не добавляется.

## Основание в приватном оригинале

Проанализированы оригинальные Projects.7z и mvkview.idp; ни один приватный файл не помещён в GitHub. Оригинальная _Unit128:00849970 (bConfigLoadClick) вызывает TMvkCellList.LoadValuesFromFile; _Unit128:0084A0F8 (bConfigSaveClick) вызывает TMvkCellList.SaveValuesToFile. Реализация находится в _Unit115:007CFD44 (чтение исходного +0xNNNN/@filename/FormatChar), 007CF624 (InputValue), 007CFB50 (InputValueRaw), 007D01E8 (строка +offset и адрес FormatChar:literal с возможным комментарием). Вторая форма mvkeditform.dfm содержит edVal, cbVal, bOk и bCancel.

Ранее источник в Qt поддерживал только read-only Load, список 8 ADC, 64 Alarm, 15 IP полей, 10 Calib полей; сохранение и редактирование реального файла были выключены.

## Один функциональный пакет, Core и Qt

Core original_config_local_workflow.py:
- Загружает строго ограниченный локальный исходный текст через существующий оригинальный конфигурационный loader с SHA, поддержкой смещений и bounded include.
- Имеет отдельный immutable workspace с проверенными изменениями IP/Calib/8 ADC и только уже существующих полей Alarm с исходным FmtChar. Нет придуманных Alarm типов или порогов.
- Проверяет диапазоны Float32/Int/IPv4, исходные типы и защиту области пароля; запрещает перекрывающие исправления разных регистров, не раскрывает ввод/секреты в отчётах.
- По явному Save As создаёт только НОВЫЙ локальный .txt/.cfg/.conf в исходной грамматике с +0x0000 и абсолютными адресами; вложенные include разворачиваются; исходные файлы не меняются. Перед сохранением проверяются SHA источника и include; после сохранения содержимое независимо открывается оригинальным текстовым парсером и все RAW-поля сравниваются. Если проверка провалена, удаляется только вновь созданный файл.
- Не содержит никакого устройства, сети, загрузки в прибор, калибровки или живой конфигурации.

Qt:
- Оригинальные bConfigLoad и bConfigSave теперь выполняют локальную загрузку и сохранение файла. Вторая кнопка активируется после успешного Load.
- Реальный Tmvkeditform теперь может принимать локальный валидированный ввод в Mode4 IP и Mode5 Calib. Видимые таблицы обновляются сразу при изменении workspace.
- Режим 6 сохраняет ровно два исходных таба tcConfig и 8-канальную DFM-сетку; дополнительно показывает 11 исходных полей выбранного ADC и позволяет менять их через форму mvkeditform.
- В 64 исходных Alarm слотах редактируются только существующие, source-typed RAW-поля. Неизвестные приборные значения остаются UNKNOWN.
- Отдельная команда отмены локальных изменений не подменяет оригинальный bConfigReset (команду аппаратного сброса).

## Приёмка и пределы

В CI: Core synthetic source/includes, save-roundtrip, bound/error/protected/secret checks, original file SHA intact, disk overwrites refused, discard and stale include protection. Windows Qt DPI150: настоящая форма, исходные кнопки, изменение Mode4/5/6 и Alarm, запись и повторное открытие нового файла. Новые Windows QA скриншоты только синтетические.

Original device Download/Upload/Reset, физическая калибровка, исходные binary checksums и Delphi Unicode codepage parity не приняты; приборные команды остаются выключенными. Никаких утверждений об оригинальном Win32 runtime 1:1 нет.

## Следующее крупное восстановление

После CI сохранить проверенный source SHA и EXE в START_NEW_CHAT_RU.md и CURRENT_STATUS_RU.md. Далее идти в функциональное восстановление PageFile с его 8+2 каналами, SPEC/VALUES и записью/выбором имён по исходному PAS/DFM, со сквозным Core+Qt E2E и отдельным разрешением лишь для безопасных офлайн-операций. НЕ возвращаться к микрошагам сравнения спектров.
