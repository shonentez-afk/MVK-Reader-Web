# STAGE111Z31BE — исходная семантика ConfigIP, ConfigCalib и TMvkAdvancedCell

Дата: 2026-11-11. База: Stage111Z31BD (source 1e33e08, CI #42972196643 SUCCESS). **BE — отправлен в GitHub, финальная CI/оригинальная Win32 приёмка не объявлена.**

## Исходные доказательства

Локальный Projects.7z: SHA256 3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363.
Локальный mvkview.idp: SHA256 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438.
В архиве 129 PAS, 3 DFM, 1 DPR. Оригинальные файлы/байты не загружены в GitHub.

- _Unit125.pas:00802D4C — 15 сетевых полей (IP 0x04, Netmask 0x06, Gateway 0x08, ModbusPort 0x0A, Endian 0x0C, NumGroups 0x14, Option 0x40, WifiMode 0x42, WifiIP/Mask/Gateway 0x44/46/48, WifiPort 0x4A, WifiEndian 0x4C, SSID 0x50, Password 0x60); Modbus ports 1..65535.
- _Unit125.pas:00803580 — 8 CalibADC (0x20+2*i, i=0..7), TachoMin 0x12, TachoMax 0x10; обоим тахометрам границы 0..10000.
- _Unit125.pas:0080380C — 11 базовых ConfigADC полей на канал, 8 каналов; Sensitivity 0x02; Overload 0x04; Units 0x10; Serial 0x20; HF 0x3E; Octave 0x40/42/44/46; MaxVoltage 0x50; MinVoltage 0x52. Это отдельная карта от 512 Alarm-полей Stage BD.
- _Unit115.pas:007D0584/007D0714/007D0734/007D0774/007D07A4/007D0808 — TMvkAdvancedCell: UInt32 ID, первая точная позиция ID, Link, отображение неизвестного ID в шестнадцатеричном виде, composite-mask, соединение '; ', пустой результат '---'. Из исходного конструктора восстановлены Modbus endian IDs 0/0x99999999/0x66666666 и HF IDs 0..3. NumGroups/Option/WifiMode/Octave source enum strings полностью НЕ доказаны и не подменяются догадками.

## Реализация

**Core:** mvk_compatible/core/original_config_semantics.py — автономные неизменяемые схемы полей и методы AdvancedCell без зависимости от Qt, прибора, сети и изменяемого регистра. Неизвестные ячейки = UNKNOWN, не ноль. Типы TMvkCellList оставлены исходными кодами (7, 15, 2, 10, 13, 14, ...), а не ошибочно интерпретированы как подтверждённые форматы IPv4, SSID, Float32 или live-регистр.

**Qt:** исходный Mode4 (IP) и Mode5 (Calib) отображаются в одном соседнем tabConfigBasic, а Mode6 — в исходном двухвкладочном tcConfig с Channels/Alarms. bTaskConfigIP теперь выполняет только read-only переход на Mode4, а не оригинальный вызов настройки прибора. bTaskConfigCalib остаётся скрыта/заблокирована; в Mode5 можно зайти программно для офлайн-проверки. Пароль Wi-Fi маскируется в сетевой таблице; редактирование не разрешено.

**Регрессии:** mvk_compatible/tests/test_stage111z31be_config_semantics.py и test_stage111z31be_qt_config_modes.py. Существующий тест test_stage111z31ao_original_qt_shell.py обновлён под локальный read-only переход ConfigIP. Core synthetic tests отдельно локально прошли при разработке, после интеграции весь CI проверяется отдельно.

## Границы приёмки и следующий пакет

Сравнение original↔candidate на **одном физическом Windows запуске и одном файле** пока не проведено; нет доказательства реального device-config, локализованных строк и семантики устройства. Save/Upload/Download/Reset/Calib/EEPROM/Flash не разрешались, оригинальная MVKView и x32dbg/F9 не запускались. Само описание Calib полей НЕ означает восстановления измерительной калибровки. Обязательно проверить CI 3 jobs, затем построить Windows read-only paired snapshot/parity harness (два запущенных PID, same-run геометрия/текст/таблицы/скриншоты без ввода и без устройства); завершить source enum и format type audit.
