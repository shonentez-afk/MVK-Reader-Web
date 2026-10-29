# Stage111N — временный переход GitHub Actions → CircleCI (29.10.2026)

## Цель

Продолжить автоматическую офлайн-проверку отдельной Windows Qt MVKView Compatible в исследовательской ветке `research/stage111-mvkview-desktop-20261029`. В GitHub Actions Stage111N run 40905305758 оба ядра не получили runner (runner_id=0, steps=[]), Windows EXE skipped. Эти сведения не являются результатом pytest и не доказывают неисправность приложения.

## Изменения непосредственно в GitHub

- `.circleci/config.yml` — CircleCI 2.1 с официальным Windows orb `circleci/windows@5.0.0`; Linux `cimg/python:3.11`, Windows Server 2022.
- `linux-core`: установка `mvk_compatible/requirements-core.txt` + pytest, проверка compileall, все тесты без `test_desktop_qt.py`, JUnit XML.
- `windows-core-and-qt`: системный Python 3.11+ в локальном venv, `requirements-desktop.txt` + pytest, отдельные команды для Core и нативного Qt offscreen, JUnit XML.
- `windows-exe-preview`: стартует только после успешного завершения **обоих** тестовых заданий; PyInstaller `--onefile --windowed`, `SHA256SUMS.txt`, `BUILD_INFO.txt` (CircleCI source commit and branch), `store_artifacts` папки `dist`.
- Workflow фильтруется **только** по исследовательской ветке. В коде нет запуска TCP, Modbus, подключения к прибору или подмены AUX4700; оригинальные PAS/DFM/IDP/BIN/PCAPNG не загружаются.
- `.github/workflows/stage111-desktop-offline.yml` перестаёт автоматически стартовать на push в исследовательскую ветку; ручной `workflow_dispatch` оставлен на случай восстановления runners. `main`/v0.3.40 не изменены.

## Проверки

YAML успешно прочитан PyYAML, локально проверены названия jobs, единственная допустимая ветка, зависимости EXE от Linux+Windows Core/Qt. Git blob `00631b45cb1f4088114784b0e0f51cd6776c70a5` на GitHub совпал с локальным `git hash-object` подготовленного `config.yml`.

**CircleCI server-side config validation, выделение Windows executor, pytest и сборка EXE ещё не подтверждены**: CircleCI проект должен быть подключён к приватному репозиторию. Не записывать synthetic pass и не объявлять Stage111N QA успешным до реальных логов.

## Настройка CircleCI

1. На circleci.com открыть Projects → Create Project / Set Up Project и разрешить CircleCI GitHub App доступ **к нужному приватному репозиторию** `shonentez-afk/MVK-Reader-Web`.
2. Выбрать существующий config из репозитория: `.circleci/config.yml`, **ветка `research/stage111-mvkview-desktop-20261029`**, не `main` и не создаваемая автоматически `circleci-project-setup`.
3. Подключить trigger на pushes этой ветки, если при настройке он не создан; при необходимости запустить pipeline вручную.
4. Проверить `linux-core`, `windows-core-and-qt` (оба отдельные тестовые шага), `windows-exe-preview`, и вкладку Artifacts → `MVKViewCompatible_Stage111_Windows_Preview` (EXE, SHA256SUMS, BUILD_INFO).
5. Перед приёмкой записать ID/URL CircleCI pipeline, source SHA, фактические counts и ошибки, Windows artifact размер/SHA. При ошибке Windows runner/credits/permissions различать инфраструктуру и pytest.

## Следующий Stage

Продолжить Stage111N/111O только после подтверждённого CI. Delphi Font/DPI/Canvas, CursorString, RTL/x87, FFT/GetSpectrum/GetNarrowbandValue/FRange и полное воспроизведение вкладок остаются незакрытыми. Проверенные Stage111M Actions 40900170911 (368 Linux / 368 Windows / 14 Qt / EXE) относятся **только к старому программному SHA** `ba5efaf3e868365a58edaa828bdfbb7953f45fdd`.

CircleCI Windows допускается в выбранном плане/лимитах; фактическую доступность и расход ресурсов проверить в CircleCI, не предполагать заранее.
