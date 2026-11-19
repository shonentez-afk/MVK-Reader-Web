# Mode2 — единый пакет Measure → Task2 → GetSignal/GetSpectrum → WriteData/WriteValues → Stop

**Дата:** 19.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Последний кодовый коммит:** `352facda0c9873c6c1011b15a3519c975fb4b1ab`.

## Назначение

Не дробить оригинальную цепочку приёма на несвязанные мелкие этапы. Один source-backed пакет объединяет запуск Mode2, реальный локальный TCP/Task2, оригинальную 36-байтную команду SetRate, PARAM, 8 ADC/2 TACH, оригинальный 2^21 FRange=1 Float32 ring, точные GetSignal и GetSpectrum окна, оба оригинально-граничных live writer, Stop, RAW и SHA. Все входящие данные и исходящие команды **только в синтетическом `127.0.0.1`**, без физического MVK01.

## Приватная исходная сверка

Файлы были действительно проверены локально и совместно, а не только по предыдущим GitHub-отчётам:

- `Projects.7z`: SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`. Пять исходных `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm` распакованы и **5/5** проверены по точным размеру и SHA из SQLite.
- `mvk_idr(1).sqlite`: SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`, `PRAGMA quick_check=ok`. Исходный callgraph содержит `TMVKThread.Execute 00807A98` (`_Unit125`), `SetRate 00809400`, `ProcessBufferChunk 007D2398`, `GetSignal 007D0C30`, `GetSpectrum 007D13D4`, `bTaskConnectClick 00848E78`.
- `mvkview.idp`: SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`.

Все три источника остаются приватными; **в GitHub не добавлены** PAS/DFM/IDP/SQLite/PCAP/RAW или конфиденциальные FIR-банки.

## Выявленное расхождение и исправление

Ранее чтение полного исходного Go-ring требовало `len(summary.rates)==1` и `summary.SequenceDiscontinuities==0` с глобального TCP-потока. Это некорректно после настоящих пакетов с Fs != выбранной MvkSampleRate: оригинал продолжает получать их в RAW, но не включает в исходное хранилище. Свежая корректная непрерывная история из кольца не должна навсегда блокироваться исторической `summary.rates`.

Теперь `source_live_long_window.go` проверяет текущий `sourceOriginalStorageRing`, FRange1 domain, фактически допущенные через rate/Freeze данные, непрерывность через `ring.window`/`validPos`, индекс, SHA, 2^21 ёмкость, текущую сессию и неизменность Fs. Не принимает неполные или перезаписанные окна. Убран избыточный gate `m.liveBin!=nil`: оригинальное source ring — самостоятельный источник, forensic BIN exporter не владеет им.

В `monitor.go` обнаружение смены частоты для **дополнительно реконструируемого** BIN теперь смотрит на реально принятый source-ring Fs, а не на произвольные частоты, ранее встреченные в необработанном TCP. Неизвестные Fs остаются в RAW и не превращаются в `SOURCE_INVALID_PACKET`; настоящая смена принятой частоты по-прежнему запрещает некорректный single-rate BIN.

## Новый единый интеграционный тест

`tools/research/native_tcp10230_stage108_live_recording_r6_1/source/mode2_original_single_socket_full_acceptance_test.go`

- `TestMode2OneRealLoopbackSocketSignalSpectrumWritersStopSourceProof`: слушатель на `127.0.0.1:0`, реальный Go TCP и исходная 36-байтная команда SetRate; PARAM/System0, 8 ADC, 2 TACH, 0x3100 WriteValues; исходный FRange1-ring ADC1; в том же живом сеансе локальные IPC `GetSignal HTag9` и `GetSpectrum N=1024`, полные Float32 окна по SHA и байтам; завершение Stop, WriteData/WriteValues и два аудита; сравнение побайтно точного RAW с искусственным TCP-потоком.
- `TestMode2NonselectedWireFsSkipsOnlySourceRingAndDoesNotPoisonFutureWindows`: исходный ADC при Fs44100 не вызывает ложную ошибку, не меняет принятую частоту, не попадает в ring; новые корректные ADC при Fs65536 заполняют непрерывное реальное окно и доступны GetSignal.

Уже имеющиеся negative suites сохраняются: malformed source frame, invalid length, DENIED, Status0, reconnect после отдельного разрешения, TACH, Freeze, RAW/SHA и per-socket закрытие файлов. Новая проверка не заменяет их.

## Приёмочные границы

- **Software CI:** проверять исключительно итог последнего GitHub Actions, соответствующего SHA; до фактических результатов **не писать PASS**.
- **Original Win32 Delphi/MVK01:** `original_delphi_compatibility_verified=false`. Реальный совместный аппаратный поток с оригинальным 1.0.47 пока не снят в данном сеансе.
- Остаются открытыми 1:1 Win32/x87 FIR/Hann/FFT/курсоры и тайминги, полные исходные CSV/TSXML/локализованный GetValueText, байтовая парная приёмка SetRate/ACK/DENIED/timeout/reconnect/Stop на реальном приборе.
- Ни в каких автоматических тестах не отправлять Flash/IP/Reboot/Task3/4/5. `main` не менять и исследовательскую ветку без аппаратного 1:1 PASS не объединять.

