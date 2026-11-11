# Stage111Z31BH — оригинальные InputValue, SetBounds, InputValueRaw и локальный черновик

Дата: 11 ноября 2026 года. Ветка: research/stage111-mvkview-desktop-20261029. Принятая исходная база: Stage111Z31BG, source e297e3627bf5c2893e4013583dd6603abfa2b490, [CI #42998754355](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42998754355) — Linux Core, Windows Qt150 и standalone EXE PASS. **Stage BH полностью принят по CI:** exact source 9d5f6b3ec5503d52753ed7e6041609ea33996278; [Actions #43002778865](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43002778865) SUCCESS 3/3. Original Windows runtime parity всё ещё отсутствует.

## Статическое подтверждение по пользовательским приватным исходникам

Исходный Projects.7z SHA256: 3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363; mvkview.idp SHA256: 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438. Исследовались _Unit115.pas и _Unit114.pas локально. Оригинальные PAS, DFM, IDP, BIN, PNG и исходные ресурсы не отправляются в GitHub.

- _Unit115:007CF624 — InputValue(CellIndex, Value:string), 007CFA2C — перегрузка AdvancedCellID:Cardinal, 007CFB50 — InputValueRaw(ValueWithFmt, Addr); 007D0474 — SetBounds; 007D0564 — SetProtection; 007CEC30 — проверка индекса.
- 007CED60 — исходная таблица текстового ввода из 30 case, ОТЛИЧАЕТСЯ от таблицы визуального GetValueText: 1,2,3,0,0,0,5,5,7,7,11,7,4,8,8,6,9,9,9,9,9,9,9,9,10,10,10,10,11,11. SHA256 байтов этой таблицы: 2e81b332909a4f65930cc193175ac5fdfc915d06c25821e0311733b9a5f9bccf.
- 007CF68D и 007D04A5: SetBounds применим к type 0,1,2,5,10,16..29. Проверяется максимум (ctTooBig), затем минимум (ctTooSmall). Тип 0 Float32, тип 1 Int32, иные поддерживаемые — DWORD unsigned.
- 007CFA87..007CFAC4: для AdvancedCellID оригинал проверяет protected, наличие списка и type10, затем записывает DWORD. У него НЕТ обязательной проверки принадлежности ID существующему списку.
- InputValueRaw отличается от двух других путей: проверяет адрес и наличие «:» как второго символа, затем по FmtChar ищет ПЕРВОЕ совпадение в типах; диапазоны и protected отдельно не проверяются. Повторные символы h и b — именно первый index; нельзя сопоставлять их с последним отображаемым типом.
- _Unit114:007B24F0 — HEX до 8 цифр, префикс 0x необязателен; 007B2688 — строка 0/1/space до 32; 007B2AA0 — IPv4 по четырём октетам; 007B2C60 — маска с непрерывной последовательностью старших единиц (0 и 0xFFFFFFFF отвергаются); 007B2E0C/007B2E8C — разные правила копирования ANSI в фиксированную память.

## Код и безопасность

Создан автономный модуль mvk_compatible/core/original_config_input_draft.py. SourceInputRejected возвращает ключ локализации без печати пользовательских паролей. LocalConfigDraft.from_local_image работает ТОЛЬКО с явным LocalRegisterImage и создаёт immutable preview; оригинальные байты остаются неизменными. Методы preview_text, preview_advanced_id и preview_raw_format используют отдельные источниковые цепочки; as_local_image возвращает новую копию, summary сообщает длины и хеши, но никаких device writes или сохранения в файл.

Реализованы source-constrained текстовые конверсии Float32, Int32, signed-to-DWORD, IP, проверка netmask, HEX, ограниченный печатный ASCII как безопасное подмножество ANSI, битовые строки и source AdvancedID. Неизвестный исходный Windows codepage, исходные Delphi FormatSettings/StrToFloat в полном объёме и физические protection bits НЕ выдумываются. Для InputValueRaw исходный bypass НЕ открывает доступ к прибору и намеренно блокирует ЛЮБОЕ байтовое пересечение с password range 0x0060..0x007F (в том числе raw-поля, начинающиеся ранее) в диагностическом черновике.

В Qt original_config_readonly_ui.py добавлен отдельный контекстный пункт на колонке RAW Mode4/5: «Проверить значение локально (без изменения)». Это дополнительный проверочный путь, не оригинальная DFM-кнопка, и никак не изменяет текущую конфигурацию. Результат отображает локальная TWindowManForm. Оригинальный mvkeditform по двойному щелчку остаётся read-only, bConfigSave/Upload/Download/Reset и Calib отключены.

Тесты: mvk_compatible/tests/test_stage111z31bh_source_input_draft.py, test_stage111z31bh_qt_local_validation.py. В том числе точная table SHA256, bounds/min/max, IPv4, маска, byte ordering, password/redaction, first-match raw format, immutable snapshots и все запрещённые приборные действия. Отдельный Qt-тест добавлен в Windows DPI150 workflow.

## Границы и следующий крупный блок

SOURCE-TESTS и Windows CI — не оригинальная Win32 runtime 1:1 приёмка. На исходном Type12 отображение и input используют разные helpers: подменять оригинал «логичным» алгоритмом нельзя. Не подтверждены все локализованные строки, полные Delphi Float32 formatter, исходный код сохранения конфигурации, физическая калибровка, аппаратный TCP/EEPROM upload и все 62 исходных обработчика. Оригинал/x32dbg/F9/приборные записи не запускались.

Следующий пакет: законченный LoadValuesFromFile → InputValueRaw → SaveValuesToFile в Core, по source-вызовам, с сохранением includes/offset/comments и строгим тестом на приватных данных; затем парная read-only автоматическая Win32 приёмка «один файл, одинаковый канал/режим». Аппаратные команды — только после отдельной безопасной стендовой приёмки.


## Приёмка по реальному CI

Проверенный source SHA: 9d5f6b3ec5503d52753ed7e6041609ea33996278. [GitHub Actions #43002778865](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43002778865): **SUCCESS** (Linux Core, Windows Core/Qt DPI150, verified standalone Windows EXE + Native R6.1). [Артефакт #13847052402](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43002778865/artifacts/13847052402) 68 706 042 байта, expires 2026-11-25T10:26:02Z. Новые тесты перепроверяют, что raw-патч, начинающийся до пароля, не пересекает его область, и не блокируют соседнее поле SSID. **Нет оригинальной running-MVKView same-window приёмки, нет аппаратной записи и нет подтверждённой полной копии 1:1.** Docs-only commits не входят в проверенный исходный SHA.
