# Единый реестр исследовательских файлов MVKView

Дата: 2026-10-28. **Реестр охватывает текущие доступные локальные ресурсы, а не все материалы из всех чатов.**

## Ключевые файлы в GitHub (исследовательская ветка)
- `tools/research/mvk_tcp_reader_v2.py` — Stage 40, читающий клиент TCP/10230.
- `tools/research/README_MVK_TCP_READER_V2_RU.md` — инструкция.
- `docs/research/MVK_TCP_10230_PROTOCOL_VALIDATED_RU.md` — сетевой протокол.
- `docs/research/MVK_DSP_STAGE13_VALIDATION_RU.md` — контроль точности DSP.
- `docs/research/MVKVIEW_STAGES_25_40_REGISTER_RU.md` — история этапов.
- `docs/research/STAGE41_SPECTRUM_CHAIN_RU.md`, `STAGE42_FFT_CORE_RU.md`, `STAGE43_SPECTRUM_PIPELINE_RU.md`, `STAGE44_HANN_WINDOW_RU.md` — спектральный тракт.
- `tools/research/stage41_verify_idr.py`, `stage42_verify_fft.py`, `stage43_verify_spectrum.py`, `stage44_window.py` — проверочные инструменты.
- `docs/research/MVKVIEW_HANDOFF_AND_EVIDENCE_RU.md` — продолжение проекта.

## В локальной резервной копии
Инвентаризация выявила 25 Python/shell-скриптов, включая `dfm_decode.py`, `stage26_map.py`, `stage27/call_graph.py`, `stage31/idp_inspect.py`, `stage32/audit.py`, `stage33/probe.py`, `stage33/validate.py`, `stage34/{analyze,deep}.py`, `stage36/protocol.py`, `stage37/analyze.py`, `stage38/analyze.py`, `stage39/verify.py`, `stage40/{mvk_tcp_reader_v2,replay_capture,test_offline}.py`, `stage41/analyze.py`, `stage42/analyze.py`, `stage43/verify.py`, `stage44/window_stage44.py`, а также вспомогательные сценарии.

**Файлы архивированы локально, но не все 25 оригинальных скриптов загружены на GitHub.** Не считать GitHub полной резервной копией до сверки SHA-256 каждого файла. Контрольные суммы доступны в `SCRIPTS_REGISTER.csv` внутри `MVKVIEW_STAGE44_AND_INVENTORY_20261028.zip`. Список GitHub-версий отдельно от локальных исходников: текст мог изменяться при восстановлении.

## Не публиковались
`mvkview.exe`, `mvkview.idp`, `Projects.7z`, PCAPNG/BIN/VALUES/TABLE, оригинальные архивы Stage 25–44 и утилиты IDR. Эти файлы хранятся отдельно от публичного GitHub и необходимы для полной воспроизводимости.

## Процедура восстановления
1. Найти оригинальный EXE и экспорт IDR `Projects.7z`.
2. Скачать исследовательскую ветку; для точного набора локальных скриптов использовать `MVKVIEW_RESEARCH_SCRIPTS_FULL_BACKUP.zip` из архива Stage 44.
3. Сверить файлы по SHA-256 в `SCRIPTS_REGISTER.csv`; проверить `python stage40/test_offline.py` в окружении, где находится исходный декодер.
4. Исследования выполнять изолированно, стабильную `v0.3.40` не заменять.
5. Содержимое исходящего сетевого трафика и команды записи конфигурации не тестировать на производственном приборе без отдельного плана испытаний.
