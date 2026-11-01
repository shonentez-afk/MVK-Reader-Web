# Stage111Z.15 — перенос CI и сборки Windows EXE на GitHub Actions

**Дата:** 01.11.2026. **Репозиторий:** `shonentez-afk/MVK-Reader-Web`. **Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. **Задача:** автономный Windows-аналог MVKView на Qt/PySide6, без старого Web-сервера.

## 1. Почему меняли систему

В октябре лимиты GitHub Actions были исчерпаны, поэтому проект временно использовал CircleCI для Linux DSP, Windows Qt и сборки EXE. На 1 ноября оператор вручную запустил существующий workflow `offline_static_checks.yml` на `main` и получил **Success (12 секунд, job offline — green)**. Это подтверждает, что хотя бы Linux runner GitHub снова работает; остаток минут в Billing самостоятельно этим фактом не доказывается.

Поступило прямое указание пользователя **перейти обратно на GitHub Actions**. Продуктовые исходники и алгоритмы `GetSpectrum`/FFT/Cursor при миграции НЕ изменялись.

## 2. Выполнено в GitHub

### 2.1. Новый основной workflow на двух ветках

`.github/workflows/stage111-desktop-offline.yml` синхронизирован:

- на **default `main`** — **только конфигурационный YAML** для появления кнопки **Run workflow** в интерфейсе GitHub Actions, без переноса кода Stage111 в `main`;
- в **`research/stage111-mvkview-desktop-20261029`** — рабочий запуск `push` при изменениях `mvk_compatible/**` или самого workflow, и ручной `workflow_dispatch`.

**Все jobs защищены проверкой конкретной исследовательской ветки**. Если случайно выбрать `main` в форме ручного запуска, Stage111-EXE с устаревшим кодом `main` собираться не будет. В форме **Run workflow** выбирать `research/stage111-mvkview-desktop-20261029`. На `push` в другие ветки workflow не запускается.

### 2.2. Три стадии и gating

| Job GitHub Actions | Runner | Проверка |
|---|---|---|
| `linux-core` | `ubuntu-latest` | Python3.11, синтаксис всего `mvk_compatible`, **все** core pytest без Qt |
| `desktop-windows` | `windows-latest` | Python3.11, все core pytest на Windows и отдельная Qt/PySide6 GUI smoke suite с `QT_QPA_PLATFORM=offscreen` |
| `windows-exe-preview` | `windows-latest` | стартует **только после SUCCESS обеих предыдущих jobs**, PyInstaller onefile windowed; делает SHA256, `BUILD_INFO` с точными GitHub SHA/ref; дважды проверяет PE и SHA через `verify_windows_preview_artifact.py`, публикует `verified-dist` как Actions Artifact |

Только исходный `research/stage111-mvkview-desktop-20261029`, никаких производственных приборов, интернета приложения, реальных RAW/BIN/PCAPNG/архивов, оригинальных EXE/IDP/PAS/DFM и приватных исходных изображений в CI. Все действия workflow имеют `permissions: contents: read`; checkout `persist-credentials:false`.

Используются GitHub Actions checkout/setup-python/upload-artifact последних Node24-совместимых стабильных major `@v6`. Это устраняет старое предупреждение про Node20 от прежних `@v4/@v5` checkout/setup. В GitHub Actions использован полный набор тестов CircleCI, не только старый ограниченный offline script.

**Artifact:** `MVKViewCompatible_Stage111_Windows_Preview`, внутри `MVKViewCompatible_Stage111_PREVIEW.exe`, `SHA256SUMS.txt`, `BUILD_INFO.txt`, `BUILD_VERIFICATION.json`. Хранение **14 дней**. При ошибке любой проверки artifact НЕ публикуется. Это исследовательская preview-сборка, НЕ официальный production-релиз и НЕ полная Delphi-аттестация.

### 2.3. CircleCI сохранён как ручной резерв без затрат push CI

В `.circleci/config.yml` **оставлены все существующие jobs**, но добавлены:
```yaml
parameters:
  run_circleci_backup:
    type: boolean
    default: false
```
И в workflow `stage111n-desktop-offline`:
```yaml
when: << pipeline.parameters.run_circleci_backup >>
```

Теперь новые push по умолчанию **не запускают CircleCI jobs**. Восстановление резервного workflow возможно вручную через CircleCI API параметром `run_circleci_backup=true`; оригинальные CircleCI job definitions сохранены. Не требуется удалять подключение/проект CircleCI.

## 3. Первый реальный запуск

- Добавление workflow на default `main`: commit `a69224807b5ea3e652589b9060a7ad2599a9fef8`.
- Вывод CircleCI в ручной резерв на research: commit `fab2e1f2b6a5e88c6cba1b3ea4d4b9872356e126`.
- Активация полноценного GitHub Actions CI в research: commit `685b411926e4d54531222e3f7e5ce97d3804053a`.
- **GitHub Actions run #161**, id `41282496457`, автоматически создан на research `push`. Ссылка: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41282496457

На момент первой проверки задания `Linux - all offline core tests` и `Windows - offline core and Qt smoke tests` были **in_progress**; EXE job ожидает оба. Не считать полный переход и доступность EXE **проверенными**, пока оба теста и Windows artifact не завершились SUCCESS. На новых документационных коммитах сборка не запускается (они исключены из `push.paths`), чтобы экономить ресурс Actions.

## 4. Как скачать после успешного run

1. В репозитории `Actions` выбрать **MVKView Compatible - Windows EXE**.
2. Открыть успешный workflow run на **исследовательской ветке**, не `main`.
3. Внизу страницы run открыть `Artifacts`, нажать `MVKViewCompatible_Stage111_Windows_Preview`.
4. Распаковать ZIP в обычную папку; запустить `MVKViewCompatible_Stage111_PREVIEW.exe` в Windows.
5. Сверить `SHA256SUMS.txt` с реальной контрольной суммой (PowerShell `Get-FileHash -Algorithm SHA256`), а `BUILD_INFO.txt` — с commit SHA run.

Если кнопка Run workflow отсутствует — проверить, что файл присутствует на default `main` и включены Actions для проекта. Файл на `main` добавлен именно для отображения этой кнопки; выбирать в dropdown **research/stage111-mvkview-desktop-20261029**.

## 5. Новый снимок текущей Qt версии пользователя (не оригинальный)

Пользователь прислал screenshot запущенной Stage111 Qt preview. На нём видны вкладки `Задачи / Временной сигнал / Спектр`, график с чёрной кривой, левый сайдбар с подрезанным текстом при текущем размере окна, видимые диапазоны графика и названия вспомогательных полей. Исходный screenshot MVKView Stage111Z.14 и этот Qt screenshot относятся к **разным состояниям архива** (например, разные видимые диапазоны X), поэтому нельзя заявлять pixel-for-pixel нестыковки исходной визуализации без идентичного BIN/канала/режима/N/Fs/FRange/Geometry. Но **обрезание левых контролов и текстовых подписей у Qt следует внести в UI backlog** и отдельно исправить в следующем Stage111Z.16, не блокируя миграцию CI.

## 6. Следующий шаг

1. Проверить завершение run #161 и наличие **действительного** EXE в Artifacts. При ошибке GitHub Actions изучить **конкретные логи** и исправить YAML/тесты в исследовательской ветке, а не объявлять сборку завершённой.
2. После успеха сообщить оператору точную ссылку на новую **GitHub Actions** сборку; CircleCI оставить резервом.
3. Продолжить разработку Qt-интерфейса, прямого открытия оригинальных measurement BIN/TSXML без промежуточного Native R6.1 экспорта, и воспроизведение оригинального курсора/XOR. Не терять математическую аттестацию исходного FFT 131072/131072 и summary 3/3 для предыдущего пользовательского захвата.

**Граница:** этот этап меняет только инфраструктуру сборки/документацию, не подтверждает новых исходных алгоритмов и не исправляет уже видимые Qt UI различия.
