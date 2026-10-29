> **Stage111C (2026-10-29):** восстановлен неогибающий путь оригинального `GetSignal`: DFM AC Tag0/`NoDC=1`, AC+DC/`NoDC=0`, f32 удаление среднего, возврат **реверсированного буфера**, локальное СКЗ окна, кольцевой zero-prefix. В Qt вкладке «Временной сигнал» добавлено переключение **хронологический BIN ↔ выходной буфер GetSignal**, курсор с реальным исходным индексом. **Огибающая и ориентация TQGrapher не проверены**, настоящий DSP остаётся AUX4700. Адресный отчёт [Stage111C](../docs/research/STAGE111C_GETSIGNAL_IDR_OFFLINE_RECOVERY_RU.md). Для Windows EXE пользоваться только новым успешно проверенным Actions run; Stage111B Preview старее этих изменений.

> **Stage111B (2026-10-29):** новое независимо тестируемое восстановление FFT из Delphi IDR: безусловная коррекция среднего перед FFT, float32-ориентированная radix-2 FFT и точное обнуление первых `max(2,Round(N/(2fs)))` бинов. В «Спектр» можно переключать **IDR float32 / NumPy** и сравнивать кандидатов, но ни один из них ещё НЕ принят как численный эталон оригинальной MVKView. Читайте [адресный отчёт Stage111B](../docs/research/STAGE111B_ORIGINAL_FFT_IDR_FLOAT32_RECOVERY_RU.md). При наличии старого Preview следует использовать новую GitHub Actions сборку после успешного Windows QA.

> **Первая пробная Windows-сборка доступна:** [GitHub Actions Stage111A — 19 Linux / 21 Windows PASS + Windows EXE](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40847041592). Внизу страницы **Artifacts → MVKViewCompatible_Stage111_Windows_Preview**: внутри `MVKViewCompatible_Stage111_PREVIEW.exe` и `SHA256SUMS.txt`. Срок хранения артефакта до 12.11.2026. В этом EXE нет обязательного веб-сервера. **Это unsigned исследовательская сборка, не релиз и не проверенный полный аналог MVKView.** См. [протокол QA](../docs/research/STAGE111A_WINDOWS_PREVIEW_ACCEPTANCE_RU.md).

# MVKView Compatible — Stage111 Desktop-first

**Не веб-страница и не замена v0.3.40.** Отдельная Python/Qt программа для Windows. Создана 29.10.2026 на отдельной исследовательской ветке.

## Структура
- `core/offline_export.py`: реальное автономное ядро из Stage110A/B. Без FastAPI, Qt и сети. Проверяет ZIP, 8 BIN/TSXML, SHA256, VALUES и исходные AUX. Штатные DSP значения отображаются без локального пересчёта, BIN — без повторного K.
- `desktop/main_window.py`: PySide6/pyqtgraph, отдельное окно с вкладками «Расчётные данные», «Временной сигнал», «Спектр», каналами, таблицами, графиками и курсорами.
- `__main__.py`: запуск GUI и проверка без Qt через `--verify`.
- `tests/`: только синтетические автономные файлы, без настоящего оборудования.

## Запуск на Windows (PowerShell) из корня репозитория
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r mvk_compatible\requirements-desktop.txt
.\.venv\Scripts\python.exe -m mvk_compatible
```
После запуска нажать «Открыть архив ZIP», выбрать **локальный законченный архив R6.1/Stage107**.

## Проверка без Qt и без сервера
```sh
python -m pip install -r mvk_compatible/requirements-core.txt pytest
python -m mvk_compatible --verify /path/to/EXPORT.zip
python -m pytest -q mvk_compatible/tests/test_offline_core.py
```

## Достоверность
- `MVK_DSP`: подлинные значения AUX4700/VALUES, включая 43 третьоктавные полосы, 24 RMS, PEAK и PEAK-PEAK при полном AUX.
- `MVK_ADC_CALIBRATED_BIN`: исходный калиброванный BIN (K повторно НЕ применяем).
- `APP_DERIVED_FFT_MVKVIEW_CANDIDATE`: локальный FFT в четырёх режимах. **Полный паритет с Delphi ещё не доказан.** AC с вычитанием среднего — тоже кандидат.
- 0x400 отражается как ALERT.
- Никакого TCP/10230 подключения, приборных команд, регистрации внешних слушающих портов или скрытой отправки данных.
- Qt smoke на Windows CI и визуальное сравнение с оригиналом обязательны до приёмки.

**Это версия исходников для исследования, а не готовый инсталлятор.** Идет поэтапное восстановление оригинальной MVKView, без имитации приёмки. ADR и состояние: `docs/ADR_2026_10_29_STAGE111_MVKVIEW_COMPATIBILITY_FIRST_RU.md` и `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md`.
