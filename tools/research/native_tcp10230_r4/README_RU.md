# MVK TCP/10230 Native R4 — офлайн-пакет исследования

**Это не готовый Live-клиент.** Ни одна программа в пакете не подключается к прибору и не отправляет сетевые команды. Ветка stable v0.3.40 не менялась. Старый `mvk_tcp_reader_v2` не используется.

## Состав

- `protocol.py`, `tcp_r3.py` — проверенное ядро Native R3: кадры, регистры, offline TCP reassembly.
- `session_r4.py` — receive-only автомат задач TMVKThread `Task=0` (однократная конфигурация) и `Task=2` (непрерывный приём), обработка ID, AUX4700, 0x3100, ошибок и завершения.
- `wire_preview.py` — чистая функция *только построения байтов* rate-команды; не умеет отправлять её в сеть.
- `recording_r4.py` — экспериментальный безопасный писатель одного откалиброванного ADC BIN + TSXML. Для каждого АЦП необходим проверенный коэффициент FRange того же прибора/сеанса. Неполная запись остаётся `.partial`.
- `reconnect_preview.py` — расчёт задержек повторного подключения из IDR, без реального ожидания или сокетов.
- `r4_replay.py` — офлайн-проверка архивного PCAPNG.
- `outbound_verify.py` — офлайн-сверка отправленной оригинальной MVKView rate-команды с IDR.
- `tsxml_schema_verify.py` — сравнение генератора с настоящими TSXML без публикации исходных данных.
- `r4_idr_check.py` — подтверждение адресных опор непосредственно по локальному оригинальному `_Unit125.pas`.
- `test_r4.py`, `test_recording_r4.py`, `test_reconnect_preview.py` — синтетическая регрессия.
- `STAGE100_R4_REPORT_RU.md` — результаты, доказательства и ограничения.

## Проверки

```
python -m unittest test_r4 test_recording_r4 test_reconnect_preview -v
python r4_idr_check.py /local/private/_Unit125.pas
python r4_replay.py /local/private/pcapng.pcapng --overlap-policy preserve_assembled --out replay.json
python outbound_verify.py /local/private/capture.pcapng
python tsxml_schema_verify.py /local/private/*.tsxml
```

По умолчанию `r4_replay.py` использует строгую политику `reject` при конфликтных ретрансляциях. `preserve_assembled` — **только для явно разрешённого архивного анализа**, где все неоднозначности сохраняются в отчёте. Нельзя представлять такой поток как безупречно восстановленный.

## Следующий этап

Native R5 — полный VALUES CSV и состояния записи BIN/TSXML нескольких каналов; позже отдельный read-only Live-клиент после стендового QA. **TCP/10230**, не Modbus/502.