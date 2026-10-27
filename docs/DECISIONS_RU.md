# Архитектурные решения и ограничения

## Зафиксированные правила
- Сохранять полную архитектуру и пользовательский интерфейс MVK Reader Web.
- Один Collector на прибор, множество браузеров; не устанавливать отдельное TCP/10230 соединение на каждый браузер.
- TCP/10230: 8 каналов АЦП (индексы 0–7) плюс 2 тахометрических канала (8–9).
- **Назначение индексов 8 и 9 подтверждено разработчиками по словам пользователя (26.10.2026).** Не обрабатывать их как АЦП 9/10.
- TCP/502: только разрешённые FC03-чтения, без записи Modbus.
- Физическое ускорение для проверенных пар TCP/BIN: `a = raw_float32 * K`; BIN повторно не масштабировать.
- Учитывать прибор, номер канала, источник и время калибровки.
- Промышленные PCAPNG, BIN, локальные адреса и базы не публиковать.

## Проверено экспериментально
- Два пассивных теста 26.10.2026: поток TCP/10230 начинается после connect, **без прикладной команды клиента**. См. `docs/PASSIVE_TCP10230_TEST_20261026_RU.md`.
- В обоих RAW: блоки 1052 байта, восемь АЦП с последовательностью счётчиков без обнаруженных разрывов; вспомогательные 284-байтовые сообщения с индексами 8/9. См. `docs/RAW_CONTINUITY_AUDIT_20261026_RU.md` и `docs/AUX_CHANNELS_8_9_AUDIT_20261026_RU.md`.
- Modbus FC03 float32: CDAB; `A+0x02` чувствительность, `A+0x0E` коэффициент пересчёта.

## Незакрытые вопросы
- Полная схема пакета тахометрических каналов при подключённом датчике.
- Семантика служебных типов 44/76/160/4700 байт.
- Поведение нескольких клиентов TCP/10230 и повторных подключений.
- Полная сверка импортированного исходного дерева и регрессионные испытания.

## Ограничение работы
До отдельного решения пользователя **не запускать новую версию**, не подключаться к реальным МВК01. Анализировать сохранённые записи офлайн. Новые тесты и доказательства сохранять в GitHub.

## CORRECTION 27.10.2026 — TCP/10230 calculated data already proven
Previously 26.10 reverse engineered 4700-byte calculated frame on TCP/10230: 28-byte header, eight 584-byte per-ADC records; 43 third-octave values, 24 RMS, 24 equivalent peaks, 24 spans. Verified on 48 frames/384 channel records; see docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md and docs/FRAME_4700_REAL_RAW_REGRESSION_20261026_RU.md. TCP/10230 carries waveform AND calculated data. Port 502 is an ALTERNATIVE Modbus calculated/config reader, not the exclusive computed-data path. In the v0.3.40 UI calculated=502 reflects current implementation, not the packet format. P1.3 says 42 but Appendix 2 and real 4700 frame contain 43 slots (0.63-10000 Hz); whether first 0.63-Hz slot is reserved/unused remains unproven. Do not erase the 43rd slot. Detailed docs/STAGE13_TCP10230_CALCULATED_43_VS_42_RECONCILIATION_20261027_RU.md. Respect source priority and do not repeat settled work.
