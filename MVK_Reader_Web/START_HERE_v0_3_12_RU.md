# MVK Reader Web v0.3.12 — запуск и статус

1. Прочитайте `CHANGELOG_v0_3_12_RU.md`.
2. Оставьте `collector/devices.json` без изменений при первом запуске — он не подключается к приборам.
3. Установите Python-зависимости: `python -m pip install -r requirements.txt`.
4. Запустите Reader + Collector: `python -m uvicorn integrated:app --host 127.0.0.1 --port 8080`.
5. Посмотрите страницу `http://127.0.0.1:8080` и статус сервера `http://127.0.0.1:8080/collector/api/server-status`.
6. Запуск тестов: `python -m pytest -q` (если pytest отсутствует, `python -m pip install pytest`).

Без подтверждённой карты регистров и согласованного режима опроса не включать реальные приборы.
