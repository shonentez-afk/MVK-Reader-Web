# Каталог тестов и контрольных материалов

Этот индекс обновлять при **каждой** новой тестовой программе, диагностическом скрипте и эталонном наборе.

| Путь | Назначение | Статус |
|---|---|---|
| `tools/tcp10230_passive_test/` | Подключение к TCP/10230 без прикладных команд, ограниченный приём | **Ожидает реального теста** |
| `tools/modbus_calibration_test/` | Только FC03: считывание 17 групп калибровочных регистров | Реальные результаты по двум приборам получены ранее |
| `protocol/mvk_calibration.py` | Безсетевой CDAB float32 и преобразование raw*gain | Код опубликован, проверка в CI не настроена |
| `protocol/test_mvk_calibration.py` | Модульные тесты декодирования коэффициентов | Есть в GitHub |
| `MVK_Reader_Web/tests/` | Тесты основной программы предыдущих версий | Перенесены из исходного пакета |
| `MVK_Reader_Web/CHECK_PC.py` | Локальная проверка Windows среды | Перенесён |
| `MVK_Reader_Web/pcap_session_compare.py` | Анализ PCAPNG/соединений | Перенесён |

## Добавление нового теста
1. Поместить исполняемый файл в `tools/<name>/` (полевой инструмент) или `MVK_Reader_Web/tests/` (автоматизированный тест).
2. Добавить README: назначение, команда запуска для Windows CMD и при необходимости Termux, требуемые библиотеки, разрешённые сетевые действия, таймауты, ожидаемые файлы отчёта.
3. Указать `offline`, `read-only network` или `requires device access`.
4. Добавить минимальный обезличенный фикстурный набор и ожидаемый результат, если возможно.
5. Зафиксировать версию/commit и результаты в `docs/TEST_RUNS_RU.md`.

## Внешние эталонные данные
Реальные PCAPNG/BIN/TSXML и JSON опросов могут содержать технические данные предприятия. Не добавлять их целиком в Git без отдельного разрешения/обезличивания. Сохранять описание и SHA256 в `docs/CAPTURE_MANIFEST_TEMPLATE.csv`, сами файлы — в закрытом хранилище вне Git.


## Stage79 (2026-10-28)
`tools/research/stage79_verify_tsxml_idr.py` — offline-only статическая проверка опор генерации TSXML по оригинальным `_Unit125.pas`, опционально `_Unit128.pas`. Пример: `python tools/research/stage79_verify_tsxml_idr.py _Unit125.pas --unit128 _Unit128.pas`. Скрипт ничего не пишет в сеть; нужен локальный IDR, не публикуемый в GitHub. 23/23 структурных маркера вручную проверены по листингу; проверка связки с реальным BIN открыта.

- `tools/research/stage79c_verify_bin_open.py` — offline-only статические проверки чтения TSXML, fallback и открытия BIN (вход: оригинальный `_Unit128.pas`, без сети/оборудования). Запуск: `python tools/research/stage79c_verify_bin_open.py _Unit128.pas`. Результаты адресной ручной перепроверки: 18/18 строковых опор.

- `tools/research/stage80_verify_storage_signal.py`: offline IDR static verification (14/14 anchors) of `_Unit115.pas`; run `python tools/research/stage80_verify_storage_signal.py _Unit115.pas`.

- `tools/research/stage80b_verify_bin_fft_chain.py` — только офлайн, исходные `_Unit128.pas` и `_Unit115.pas`; проверяет 14 статических опор пути BIN/FFT. Запуск `python tools/research/stage80b_verify_bin_fft_chain.py _Unit128.pas _Unit115.pas`. Никакой сети.
