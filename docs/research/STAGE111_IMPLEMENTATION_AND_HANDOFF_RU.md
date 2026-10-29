> **СЛЕДУЮЩИЙ АКТУАЛЬНЫЙ ЭТАП — Stage111B→111C (29.10.2026).** Доказано по оригинальному IDR: `GetSpectrum` **всегда** удаляет среднее float32, а потом зануляет `Max(2,Round(N/(2fs)))` нижних FFT бинов (helper Max исследован в `_Unit114`). Новый модуль `mvk_compatible/core/fft_idr_candidate.py`, backend selector, численная сверка двух кандидатов и тесты сохранены в ветке. **Сначала:** `docs/research/STAGE111B_ORIGINAL_FFT_IDR_FLOAT32_RECOVERY_RU.md` и `docs/research/STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md`, затем проверить *последний* Windows/Linux CI + Preview. Не считать NumPy численным эталоном Delphi. Дальше оригинальные `GetSignal`, огибающая, курсоры, окна, точный спектральный экспорт; реальный прибор не подключать.

> **Stage111A QA обновлено (29.10.2026):** Windows Qt + синтетический ZIP `21 passed`, Linux core `19 passed`, Windows PyInstaller EXE preview собран и загружен. Артефакт `MVKViewCompatible_Stage111_Windows_Preview` (ID 12885936688) в [run #40847041592](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40847041592). Подробности и ограничения: `docs/research/STAGE111A_WINDOWS_PREVIEW_ACCEPTANCE_RU.md`. Проверить код GitHub stage111 и новый head перед началом; GUI визуальный/Delphi parity ещё не принят.

# Stage111A — начало MVKView Compatible Desktop / инструкция следующему чату

**Дата:** 29 октября 2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.

## ГЛАВНОЕ: принятое изменение стратегии
Пользователь 29.10.2026 окончательно утвердил **Compatibility First**: перестать исправлять v0.3.40 как основную архитектуру; восстановить максимально точный аналог оригинальной Delphi MVKView как отдельное самостоятельное Windows Desktop-приложение. Только после доказательной приёмки использовать общее ядро для собственных дополнительных функций и необязательного Web. Новый ADR: `docs/ADR_2026_10_29_STAGE111_MVKVIEW_COMPATIBILITY_FIRST_RU.md`. **НЕ отменять** ADR про оригинальный DSP: `docs/ADR_2026_10_29_ORIGINAL_MVK_DSP_DATA_SOURCE_RU.md`.

## Архитектура, которую нельзя разрушать
- `mvk_compatible/core/offline_export.py` — отдельный *PURE* Python модуль (без Qt/FastAPI/HTTP/socket). Работает только с локальными завершёнными ZIP Native R6.1/Stage107. `OfflineSession.open`, `verify`, `calculations`, `waveform`, `spectrum`, `exact_sample`, `exact_fft_bin`. Сохраняет исходные значения прибора через AUX4700 и не удваивает K BIN.
- `mvk_compatible/desktop/main_window.py` — Qt/PySide6/pyqtgraph: **одно настоящее окно**, три вкладки «Расчётные данные», «Временной сигнал», «Спектр»; переключение АЦП 1–8, расчётных обновлений, 43 третьоктавные полосы/24 RMS/PEAK, статусы датчика, графики, четыре режима FFT, курсоры, масштаб и окно времени. Исходный интерфейс DFM пока воспроизведён частично, не принята ни визуальная, ни численная идентичность.
- `mvk_compatible/__main__.py`: `python -m mvk_compatible` (нативный Qt Desktop) или `python -m mvk_compatible --verify <ZIP>` (без Qt). Нет локального веб-сервера и никакой сети.
- `mvk_compatible/tests/test_offline_core.py`: синтетические регрессии DSP/BIN/FFT/коррупции данных; `tests/test_desktop_qt.py`: Windows Qt offscreen GUI smoke.
- `.github/workflows/stage111-desktop-offline.yml`: Linux pure core + Windows Qt smoke. Смотреть последние результаты прежде чем писать PASS. Первоначальная CI выявила два дефекта: устаревшую включённую точку Найквиста/неверный dB режим в Stage110 GitHub и Windows locale UTF-8. Оба исправлены в отдельных Stage111 коммитах (ядро по Stage81d/110B, тест с `encoding='utf-8'`). Повторные CI проверить отдельно.
- `mvk_compatible/README_RU.md`: Windows команды запуска и ограничения.

## Подтверждённое и непроверенное
1. Native R6.1 и AUX4700 Stage109 приёмка на реальном №84 завершена, не начинать её заново. 8 ADC×65536 Гц, два TACH и AUX. Без команд. Реальный прибор подключать только с разрешения.
2. Локальное Stage111 core в контейнере было собрано из восстановленного офлайн Stage110B: **19/19 синтетических тестов PASS**, compileall PASS (29.10.2026). Это не доказывает оригинальную Delphi FFT; также содержимое GitHub Stage111 имеет свою CI и её нужно брать за основной источник успеха.
3. Четыре режима `GetSpectrum` — пока `APP_DERIVED_FFT_MVKVIEW_CANDIDATE`. По Stage81d/110B исключён Nyquist, dB кандидатом является `10*(fn(P)-2*fn(N/2))`; `fn=log10` ещё нужно доказать. FFT backend Py/NumPy не битово оригинален. AC-вычитание среднего также кандидат.
4. Ни один Windows `.exe` или установщик в этом этапе не опубликован. Qt GUI визуально в текущем контейнере не тестировалось, так как PySide6 отсутствует. Windows offscreen CI проверяет запуск и наличие трёх вкладок, **не** пиксельный паритет.

## Следующий строго технический шаг
Проверить GitHub head, Actions CI и результат Windows smoke. Затем адресно восстановить оригинальные Delphi DFM/IDR `pbAdcPaint`, `pbSpectrumPaint`, `GetSignal`, `GetSpectrum`, `TQGrapher.UpdateCursor` и фильтры/огибающую, добавить сравнения на одинаковых эталонных BIN/TSXML, провести живой GUI осмотр в Windows. Переходить в Live только с единственным R6.1 Collector как отдельным транспортным адаптером. Не вводить TCP/10230 в core или GUI напрямую.

## Безопасность и сохранение
Никогда не менять `main`, v0.3.40 и сохранённую `research/stage41-spectrum-chain-20261028` без отдельного решения. Не публиковать оригинальные `Projects.7z`, `mvkview.idp`, `*.pas`, `*.dfm`, сырые производственные RAW/BIN/PCAP/IDP или точный адрес оборудования. Хранить в Git только собственные выводы, программу и искусственные тесты.

## Начать новый чат
«Продолжи MVKView Compatible строго с Stage111A в `research/stage111-mvkview-desktop-20261029`. Прочитай ADR Stage111 и оригинального DSP, затем `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md` и `mvk_compatible/README_RU.md`. Проверь GitHub Actions, не трогай main/v0.3.40. Устраняй несовпадения с Delphi на основе оригинальных материалов и численной регрессии. Начни с Windows Qt и точной семантики `GetSpectrum`/`GetSignal`. Не подключай прибор без разрешения».
