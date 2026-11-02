# Stage111Z.24 — ИСПРАВЛЕНИЕ: FRange УЖЕ прослежен на Stage52, Native R6.1 УЖЕ готов и аппаратно принят

**Дата:** 02.11.2026. **Тип:** corrective reconciliation, повторная проверка существующих результатов, без изменений приложения/ядра/тестов. **Основание:** независимая повторная проверка оригинального приватного `Projects.7z` (только _Unit115.pas/_Unit125.pas/_Unit128.pas в памяти, без публикации) + существующие отчёты GitHub. Приватные оригиналы не отправлять в репозиторий.

## 1. Важное исправление прежнего Stage111Z.24

В прежних заметках `STAGE111Z24_FRANGE_WRITERS_FIRST_PASS_RU.md` и `STAGE111Z24_ORIGINAL_FRANGE_WRITER_CENSUS_PARTIAL_RU.md` ошибочно сказано, что **статический live writer Storage.FRange не найден**. Это противоречит уже завершённому **Stage52 от 28.10.2026** и оригинальному дизассемблированному листингу. Статический источник live FRange уже найден, повторно искать его **не надо**.

### Подтверждённые оригинальные адреса (повторно сверено по первичному IDR)

- **Live writer** `_Unit125.pas:0080863D` вызывает `00806964` для очередного Storage, затем `0080864C` получает объект из `form+[21124 + channel*4]`, `00808653 fstp dword ptr [eax+4]` записывает `TMvkChannelStorage.FRange`. Вызывается в цикле десяти каналов (с проверкой наличия Storage).
- **Live source** `_Unit125.pas:00806964..008069A9`: для ADC N=0..7 читает `TMvkCellList.GetFloatByAddr(0x0E)` из канальной таблицы `form+[0x1004+N*4]`; для N>=8 (тахосчётчики) возвращает 1.0; нулевое значение заменяет на 1.0. Полный control flow по всем ошибочным конфигурациям отдельно не аттестован.
- **Storage initialization** `_Unit115.pas:007D0A61`: `FRange=1.0f` в конструкторе, не окончательная калибровка.
- **Archive loader** `_Unit128.pas:0084655E`: устанавливает `Storage.FRange` по ранее выбранной величине: положительный `InternalChannelGain` из TSXML либо fallback из `DefaultConfig.txt` (ADC calibration `0x20` / sensitivity `0x02`; исключительный 100.0). Выбор `ViewedFileIsNormalized` предотвращает повторное умножение сохранённых калиброванных данных.
- **Live buffer/data path** `_Unit125:008081F0..008082DE` и `_Unit115:007D23D5`: `TmpStream.FMemory` алиас Storage-buffer, float32 масштабируется **in place** до `ChannelFile.Write`. Это уже было установлено на Stage51 и независимо подтверждено Stage111Z.23.

См. [Stage49](STAGE49_FRANGE_CHECK_RU.md), [Stage50](STAGE50_FC03_FRANGE_BIN_RU.md), [Stage51](STAGE51_BIN_MEMORY_ALIAS_RU.md), **[Stage52](STAGE52_FRANGE_ORIGIN_RU.md)**, [Stage53](STAGE53_GAIN_FC03_MATCH_RU.md), [Stage61](STAGE61_LOCAL_FRANGE_FORMULA_RU.md), [Stage62](STAGE62_ARCHIVE_FRANGE_SOURCE_RU.md), [Z21](STAGE111Z21_ORIGINAL_TSXML_GAIN_FRANGE_SOURCE_RU.md), [Z23](STAGE111Z23_ORIGINAL_LIVE_BIN_POINTER_ALIAS_FRANGE_RU.md). Существующий `tools/research/stage52_verify_frange_source.py` содержит 10 адресных проверок.

**Калибровка:** конфигурационное поле `0x0E` совпадает с документированным `K_Modbus` из read-only FC03, но сама оригинальная MVKView в этом live тракте получает значения через собственный TCP/10230/конфигурационную таблицу. Stage53 сопоставил 5/5 TSXML gains с FC03 после округления до одного знака, не для всех приборов и всех сессий.

**Честная оставшаяся неопределённость:** авторитетно установлены указанные writer sites и маршруты; не аттестованы **runtime-снимки реальных значений FRange на всех ADC в оригинальном процессе** и побайтовая идентичность ORIGINAL MVKView BIN vs Native TCP/10230 для *одного и того же сеанса*. Не объявлять эти доказательства выполненными. Полный глобальный alias-census всех DLL/модулей тоже не доказан, но это не блокирует использование установленного live source.

## 2. Готовый полноценный Native R6.1 recorder УЖЕ существует

**Исходники:** `tools/research/native_tcp10230_stage108_live_recording_r6_1/source/` (Go, автономная Windows x64 программа).

- Wired Ethernet NIC selection + Winsock `IP_UNICAST_IF`, TCP/10230 **connect → read** без прикладных команд МВК.
- RAW `incoming.raw`; ID264 + register snapshot 32800, ADC1052 (8 x 256 Float32), TACH284 (2 счётчика), AUX4700, статусы каналов и журналы кадров.
- Потоковый `LiveBinSpool` пишет восемь калиброванных `ADCn.bin.partial` с коэффициентом из регистрационного снимка **той же сессии**. Формула `float32(float64(raw)*float64(gain_float32))`. Контроль индекса, rate, gain и ошибок.
- После окончания закрывает RAW и делает независимый полный replay, SHA-256 проверки временных BIN и RAW, атомарно публикует **8 BIN + 8 TSXML, VALUES, TABLE, TIMELINE, EXPORT_AUDIT**, либо fail-closed оставляет RAW; никаких новых подключений к МВК.
- Stage108: Go 39/39 тестов, offline replay двух реальных архивных сеансов и loopback pass.
- **Stage109: реальный аппаратный Windows/Ethernet тест 29.10.2026 на МВК01 №84 — PASS**: 30.0128155 с, 84 855 полных кадров, 15 725 824 ADC float32 независимо побитово сверены (0 различий), 33 600 AUX→VALUES численных сверок; PCAP prefix=RAW, 0 прикладных байт клиент→МВК, 8 BIN+8 TSXML+VALUES+TABLE, `STAGE108_EXPORT_STATUS.json: EXPORTED`. АЦП7/8 сообщали статус `0x400`: транспорт PASS не равен здоровью датчиков.

Источники: [Stage108](STAGE108_R6_1_LIVE_BIN_RECORDING_RU.md), **[Stage109](STAGE109_R6_1_FIRST_REAL_LIVE_DEV84_ACCEPTANCE_RU.md)**, [код R6.1](../../tools/research/native_tcp10230_stage108_live_recording_r6_1/README_RU.md). Утверждения README Stage108 «новая версия не тестировалась на физическом приборе» **исторические**; более поздний Stage109 их обновил. Остались вне приёмки длинные сеансы, аварийное восстановление/reconnect, byte-exact оригинальный MVKView и полный оригинальный export тacho sidecar.

## 3. Реальный незавершённый этап — интеграция в автономный Qt UI

`mvk_compatible/desktop/main_window.py` содержит только офлайн-открытие ZIP R6.1 и парных BIN/TSXML: в нём **нет** запуска Native, сетевого клиента, `QProcess`, live/start/stop записи. Строка интерфейса прямо сообщает «OFFLINE READ-ONLY · TCP/10230 не подключается». Это **не** отсутствие готового регистратора, а отсутствие соединения уже готового Go-recorder с Windows Qt оболочкой.

**Предлагаемое следующее задание:** упаковать уже проверенный R6.1 как внутренний компонент единого Windows-приложения (например, controlled QProcess с подписанным/проверенным SHA EXE внутри пакета; без Web/FastAPI), добавить настройку IPv4/Ethernet NIC, запуск/остановку, статусы качества, автоматическое открытие экспортированных данных, сохранение audit и аккуратный fail-closed. Никаких новых приборных команд, пересчёта FRange второй раз, замены оригинального FFT golden, изменения stable `main` или Web v0.3.40. Контроль поведения R6.1 должен остаться тем же, что прошёл Stage109; длительный/аварийный Live QA — отдельно.

## Итог

**Закрыть повторную задачу «найти source writer FRange» как уже выполненную Stage52.** **Не разрабатывать R6.1 заново**: он существует, исходники доступны, 30-секундная аппаратная приёмка завершена. Переходить к безопасной интеграции с текущим MVKView Compatible Windows Qt, сохраняя отдельную границу доказательств *от приёмника* и *от оригинального DSP/UI*.
