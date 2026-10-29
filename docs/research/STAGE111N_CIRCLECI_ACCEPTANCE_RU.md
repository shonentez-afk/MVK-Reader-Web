# Stage111N — приёмка перехода на CircleCI (2026-10-29)

**Ветка:** `research/stage111-mvkview-desktop-20261029`  
**Проверенный программный SHA:** `11f022925a407495d7bf4b3b7dcb94b21afe7ced`

| Задание | Состояние | Ссылка |
|---|---|---|
| Linux Core | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/15 |
| Windows Core + Windows Qt offscreen | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/16 |
| Windows Preview EXE | SUCCESS | https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/17 |

Успех подтверждён **реальными CI-статусами CircleCI, записанными в GitHub**, а не архивным логом Stage111M. Windows Core и Qt выполняются отдельными pytest-командами внутри одного задания. GitHub Status API не показывает точные счётчики pytest; не приписывать им неподтверждённые количества. Запуск сборки означает, что PyInstaller и загрузка Artifacts завершили работу успешно, но бинарный EXE/SHA256SUMS отдельно ещё не скачаны и не сверены.

В Stage111N восстановлены первоначальные тесты однорядного и двухрядного TQGrapher после ошибочной замены тестовых файлов короткими версиями, сохранены новые inverted-X проверки и корректный запрет нулевого YScale. Отрицательный stoiM разрешён по оригинальному Delphi. Все тесты **синтетические и офлайн**: численный/визуальный паритет оригинальной MVKView НЕ доказан.

Старые GitHub Actions #40905305758 завершались до предоставления runner (steps=[]), после перехода CircleCI подключён. Главный продукт — автономный Windows Qt, main/v0.3.40 не менять, прибор не подключать без разрешения.
