# Stage 12.1 — исправление Windows WinError 32

26.10.2026. Во время `test_stage9.py::test_offline_no_raw_copy` на Windows с Python 3.15 выявлена `PermissionError: [WinError 32]`: `TemporaryDirectory.cleanup()` не может удалить `.processed.sqlite`, потому что соединение SQLite не закрыто.

**Причина:** `with sqlite3.connect(...) as db:` завершает транзакцию, но не вызывает `db.close()`; Windows блокирует удаление занятого файла. Исправлены блоки в `stage9_collector.py`, `stage8_collector.py`, `web_collector.py`, `export_graphs.py` и `test_stage6.py`: `with contextlib.closing(sqlite3.connect(...)) as db:`.

Новая автономная поставка: `MVK01_STAGE12_1_WINDOWS_SQLITE_FIX_20261026.zip`, включая `WINDOWS_SQLITE_FIX_RU.md`. Архив успешно проверен на целостность, компиляция Python успешна, на Linux **58/58 unittest OK**. **Проверка Windows ещё требуется** — устранение подтверждено кодом, но полевое повторение отсутствует. Не запускать живые приборы до успешного `RUN_TESTS.bat` в новой папке. Основная MVK Reader Web v0.3.40 не изменялась.