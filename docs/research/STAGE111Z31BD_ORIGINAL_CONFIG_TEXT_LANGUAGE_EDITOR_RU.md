# Stage111Z31BD — оригинальные Config / Channels / Alarms / Tmvkeditform / TLanguage

Дата: 11.11.2026; ветка research/stage111-mvkview-desktop-20261029.
База: Stage111Z31BC, source 6bd4289e0a681afe8825c87b52d9b464279f44ad, CI #42967629750 SUCCESS.

## 1. Что точно найдено в пользовательском оригинальном IDR

Проверены приватные Projects.7z и декомпилированные _Unit114.pas, _Unit115.pas, _Unit125.pas, _Unit128.pas и данные трёх DFM. Приватные файлы, PAS, IDP, BIN, изображения, реальные конфигурации и ресурсы не загружены в GitHub.

- _Unit115.pas 007D01E8..007D0301: SaveValuesToFile пишет строку +0xNNNN (AddrOffset), затем 0xNNNN FmtChar:literal ;Designation Title. GetAddrActual отдаёт относительный адрес, смещение не добавляется дважды.
- _Unit114.pas 007B28F8..007B2994 печатает 0x + 4 hex-цифры, 007B24F0 читает до восьми hex-цифр, с необязательным 0x.
- _Unit115.pas 007CFD44..007CFFAF: ; комментарий, + устанавливает смещение, @ подключает локальный файл со смещением родителя; остальные строки передают hex-address + FmtChar:literal в InputValueRaw.
- _Unit115.pas 007CFB50..007CFC96: оригинальный InputValueRaw записывает локальный регистровый буфер, но в нашей реализации НЕ вызывается.
- _Unit125.pas 00803FB4 и Stage66: config ADC N=0..7 начинается с 0x0100+N*0x0100, восемь alarm slots j=0..7: base+0x60+j*0x10. Восемь полей offset +0,+2,+4,+6,+8,+A,+C,+E: ID параметра, жёлтый и красный пороги, задержки повышения/понижения, гистерезисы, максимум шкалы.
- Отдельная исходная запись статуса: 0x2000+N*0x200+0x130+j*8. Итого 64 контрольных записи, 512 конфигурационных полей.
- _Unit128.pas 00849038/008490A8/008491C4 открывают Tmvkeditform по выделенной ячейке; 00840318 вызывает только локальный TMvkCellList.InputValue. Upload — отдельный обработчик 0084A5A8, НЕ равный изменению ячейки. Mode4/5 отличается от обычной конфигурации каналов; tabConfigBasic не является третьей исходной вкладкой.

## 2. Реализованный автономный Core

Новый mvk_compatible/core/original_config_readonly.py:

- Читает локальный оригинальный текст: +0xNNNN, @relative.txt, 0xNNNN F:literal ;comment; применяет inherited offset, не приписывает исходнику JSON или неизвестную структуру.
- Строго проверяет длины, формат, адреса (чётные, в пределах 16 бит), уникальность, циклы, symlink, traversal, файловые include, число строк, вложенность, SHA256; UTF-8, UTF-16LE BOM или CP1251.
- @include доступен только для простого имени файла в той же папке: другие оригинально возможные ссылки намеренно НЕ поддерживаются без разрешения и доказанной безопасности.
- Выдаёт 8 ADC × 8 slots × 8 config fields и все 64 RAW status register addresses. При отсутствии локального источника каждая строка UNKNOWN (не норма и не ноль); загруженное FmtChar:literal сохраняется без догадок о типе Float32 или селекторе прибора.
- Отдельный отчёт provenance указывает все локальные SHA256 без абсолютных путей. Ни загруженный файл, ни DefaultConfig.txt не объявляются текущей проверенной настройкой реального прибора. Network/device calls отсутствуют.

Новый mvk_compatible/core/original_language_source.py:

- 191 уникальный исходный ключ TLanguage.localize восстановлен из фактических callsites в трёх основных IDR-модулях, а НЕ из предположений о русском интерфейсе.
- Русские пояснения используются как маркированные fallback подписи. original_translation_verified=False для ВСЕХ элементов; отсутствуют сами оригинальные runtime-файлы переводов.

## 3. Подключение Qt

- original_shell.py сохраняет ровно две оригинальные вкладки tcConfig: tabConfigChannels и tabConfigAlarms. Соседняя tabConfigBasic в исследовательском Channel mode скрыта; третья не придумана.
- Новый desktop/original_config_readonly_ui.py показывает исходные восемь АЦП, 64 alarm slots, восемь полей каждого и реальный RAW адрес статуса; значения существуют только после проверки местного файла.
- Единственная включённая original 48×48 кнопка bConfigLoad читает локальный text config с явным файловым диалогом. В случае отклонения другого файла старая конфигурация очищается. bConfigSave, Reset, Upload, Download и калибровка остаются отключены.
- Исходная форма desktop/original_value_edit_dialog.py поддерживает read_only=True: показывает source key, RAW значение и config адрес, но запрещает OK/InputValue и какие-либо изменения.
- Ни один device handler не разблокирован. Статический факт source callback ≠ доказанный паритет original runtime.

## 4. Проверки и ограничения

test_stage111z31bd_original_config_source.py: 512 source config addresses, 64 status slots, точная интерпретация hex/offset/@include, отсутствие source file означает UNKNOWN, provenance, входная валидация, 191 TLanguage keys.

test_stage111z31bd_qt_config_and_editor.py: настоящий Qt PageConfig, две исходные вкладки и 64 slot rows, локальная загрузка text, Tmvkeditform только просмотра, запрещённые кнопки, сброс после ошибочного источника. Qt-тест включён в Windows DPI150 job.

Численные FIR/FFT/LOG, доказанный Code20/LOG0 0 ULP на одном физическом окне, Native R6.1 и ранее принятый Flow File→ADC→Spectrum→Status не изменялись.

**Новый CI Stage111Z31BD: PENDING, нельзя объявлять PASS до всех заданий GitHub Actions.**

Это НЕ полное восстановление Config IP/Calibration, не настоящий живой статус порогов, не подтверждённый текст original TLanguage и не общая 1:1 приёмка трёх форм. Оригинальная MVKView и x32dbg/F9 не запускались, Upload/Reset/Calib не исполнялись.

## 5. Следующий крупный этап

Исходные конструкторы и точная семантика ConfigIP/ConfigCalib/ConfigADC, проверка типов TMvkCellList/AdvancedCell и безопасный отображающий Core без прибора; локальные TLanguage-переводы только при получении подлинного источника; затем прямой read-only Windows parity harness с двумя установленными приложениями и выверенными GUI сценариями.
