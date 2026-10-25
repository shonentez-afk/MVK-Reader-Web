MVK Reader Web v0.3.30 — лабораторная сборка

1. Распакуйте в НОВУЮ папку. Не удаляйте старую установленную программу.
2. Для чистого запуска: python -m venv .venv
3. .venv\Scripts\python.exe -m pip install -r requirements.txt
4. .venv\Scripts\python.exe CHECK_PC.py
5. .venv\Scripts\python.exe START_READER.py

ВАЖНО: в ZIP отсутствует SQL-база. При первом запуске она создаётся заново.
Для переноса из старой установки СНАЧАЛА остановите оба сервера.
Перед переносом требуется сохранить собственную копию новой папки, если в ней уже есть реальные данные.
Команда переноса только в ПУСТУЮ папку collector (без devices.json и collector.sqlite3):
.venv\Scripts\python.exe TRANSFER_OLD_DATA.py --old C:\path\to\old --new C:\path\to\new
Если в новом collector есть шаблон devices.json, сначала вручную сохраните его копию вне папки и удалите ТОЛЬКО ПОСЛЕ проверки отсутствия пользовательских данных.
Если пути содержат пробелы, заключите их в двойные кавычки.

Ни один из скриптов переноса не соединяется с приборами.
Конфигурации с enabled=true или заданным interval_seconds переноситься не будут.
