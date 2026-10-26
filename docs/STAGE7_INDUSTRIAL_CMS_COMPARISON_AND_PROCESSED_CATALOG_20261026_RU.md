# Stage 7 — каталог обработанных записей и сравнительный обзор стационарных систем (26.10.2026)

## Исследование аналогов
- **Bently Nevada System 1:** короткий подробный тренд, долгосрочные укрупнённые уровни (first/min/max); при авариях и пусках — отдельное хранение более подробных данных. https://www.bakerhughes.com/bently-nevada/orbit-home/orbit-article/system-1-use-case-diagnostic-hmi
- **SKF @ptitude Observer:** настройки хранения трендов, exception-based storage, запись динамических данных в зависимости от режима/условий, фильтрация одиночных ошибочных пиков. https://cdn.skfmediahub.skf.com/api/public/0901d19680326e0b/pdf_preview_medium/0901d19680326e0b_pdf_preview_medium.pdf
- **Emerson AMS Asset Monitor:** периодическая, событийная и запрошенная выдача показателей и осциллограмм. https://www.emerson.com/en/automation-systems/asset-performance-management/machinery-health-management/ams-asset-monitor
- **Brüel & Kjær Vibro SETPOINT CMS:** хранение выборочных осциллограмм при изменении состояния и по максимальному временному интервалу. https://www.bkvibro.com/fileadmin/mediapool/Internet/Manuals/SETPOINT/CMS_Instructions_S1176125_002_en.pdf

Это обзор заявленных производителями возможностей, а не утверждение о тождественности внутренних алгоритмов.

## Решение MVK
Пользователь требует **отдельный запуск режима «Реальное время»** и режим **«Запись» без постоянного хранения сырой осциллограммы**. Поэтому перспективная архитектура — (1) live RAM-графики без истории, (2) сеансы обработанной SQLite-истории, (3) укрупнённые исторические тренды, (4) журнал диагностических событий. Сырые снимки по событиям — только будущая добровольная опция с квотой, не default.

## Реализация Stage 7 (исходники в отдельном пользовательском ZIP)
Созданы `stage7_session_manager.py`, `trend_rollup.py`, `test_stage7.py`, `test_rollup.py`. Существующие Stage 1–6 объединены в пакет `MVK01_STAGE7_CATALOG_STORAGE_20261026.zip` (исходники **ещё не импортированы в production репозиторий**).

- Session catalog в `catalog.sqlite`, состояния recording/complete/interrupted/failed.
- Отдельный processed SQLite на сеанс, без создания, копирования или удаления исходного RAW.
- Статус complete ставится только после проверки записи в БД, восстановления и PRAGMA integrity_check.
- При повторном старте оставшиеся recording -> interrupted, независимо от наличия неполной БД; ошибочный сеанс помечается failed.
- Rollup укрупняет тренды (first/last/min/max и корректно объединённое RMS с учётом различий средних) в отдельную таблицу. Никакого автоматического удаления исходных графических точек.

## Проверка
- 35/35 unittest PASS.
- Реальный RAW №84 27 862 260 bytes -> обработанный SQLite ~900 KiB; 104 graph, 192 metrics. Каталог ~16 KiB. Rollup 60s: 16 записей из 104.
- Никакого TCP к прибору. MVK Reader Web v0.3.40 не изменена.

## Дальше
Доработать live-source abstraction и фоновый worker/процесс для длительной работы; проверка повреждения диска, согласованного завершения окна и синхронизации multi-channel; управляемые retention tiers, защита от переполнения. **Не смешивать** режимы записи и live без отдельного запроса пользователя.