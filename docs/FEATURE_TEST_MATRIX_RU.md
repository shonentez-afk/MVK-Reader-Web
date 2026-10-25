# Матрица функций и испытаний

Градации: **есть исходники**, **офлайн тест в GitHub**, **фактически пройдено**, **ждёт реальный прибор**. Само наличие теста не означает успешный прогон.

| Функция | Модуль | Соответствующая проверка | Установленный статус |
|---|---|---|---|
| Запуск веб-приложения | `integrated.py`, `START_READER.py` | `MVK_Reader_Web/reader_web/tests/test_web.py` | Файлы есть; текущий runtime не проверен |
| BIN+TSXML → архив | `reader_web/server.py`, `mvk_core.py` | `MVK_Reader_Web/tests/test_decoder.py`, `reader_web/tests/` | Тесты есть; отчёт прогона не зафиксирован |
| Временной сигнал и спектр PCAPNG | `signal_bridge/*` | `MVK_Reader_Web/tests/test_pcap_offline.py`, `test_pcap_compare.py` | Офлайн код и тесты есть |
| Расчётные данные Live/Archive | `collector/*`, `integrated.py` | `MVK_Reader_Web/tests/test_calculated_modes_340.py` | Тесты есть; не запускались в этой проверке |
| Устойчивость Collector | `collector/core.py`, `scheduler.py` | `MVK_Reader_Web/tests/test_collector_resilience_328.py` | Тесты есть |
| Выбор устройств | `mvk_device_selector.py` | `MVK_Reader_Web/tests/test_device_selector_337.py` | Тесты есть |
| Modbus FC03 калибровка | `protocol/mvk_calibration.py` | `protocol/test_mvk_calibration.py` | Исследования на двух приборах подтверждены ранее; CI запуск оформляется отдельно |
| Старт TCP/10230 от одного connect | `tools/tcp10230_passive_test/` | Полевой тест + PCAPNG | **Не проводился: блокирует Live-разработку** |
| Отсутствие Modbus-записи | `tools/modbus_calibration_test/` | Кодовые ограничения FC03, ревью | Инструмент добавлен; факт выполнения конкретного запуска не фиксировался |
| Экспорт и архивные диапазоны | `collector/service.py` | `MVK_Reader_Web/tests/test_export_consistency_325.py` | Тесты есть |

Перед каждым релизом заполнять реальные результаты тестов в `docs/TEST_RUNS_RU.md`; не выставлять VERIFIED по одному факту наличия скрипта.
