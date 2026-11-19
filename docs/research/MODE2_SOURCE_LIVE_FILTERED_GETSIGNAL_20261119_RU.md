# Mode2 — восстановление source-ring GetSignal с FIR при нажатии «Измерить»

Дата: 19.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.
Код: [`2ef3058`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/2ef3058ec02f86ee3ef6e4f7df3e89a32c6ef80d).
[Проверка CI](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44446624450) — фиксировать PASS только после завершения **всех пяти** заданий.

## Проверенные оригинальные источники

Все три **локальные приватные** источника проверены совместно; не публиковать их содержимое или FIR-банки:

- `mvkview.idp`: `IDR proj v.3`, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`, содержит соответствующие поля, метаданные FIR/каналов.
- `Projects.7z`: SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`; пять оригинальных `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm` извлечены локально и по SHA/размеру совпадают с SQLite.
- `mvk_idr(1).sqlite`: SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`; `PRAGMA quick_check=ok`; найденные адреса событий и функций совпадают с Pascal.

## Что именно восстановлено в этом пакете

Оригинальный `GetSignal` в `_Unit115.pas:007D0C30` делает `CheckDataAvailability`, выбирает конец окна по `Contiguous`/`FRxPos`, затем для `EnvelopeCode>0` вызывает `GetAdjustedEnvelopeLength 007D1158` **до чтения исходных Float32**, применяет DC/FIR/децимацию/IQ и возвращает **обратный** по времени буфер. Это отличается от обычного HTag без фильтра и от спектрального `bSpecLines`.

Восстановленный маршрут: оригинальный выбор `bAdcHScale HTag` + код FIR → полная дополнительная pre-FIR история из единственного Go `2^21`-кольца → локальный SHA-bound ZIP (сессия, индекс, Fs, HTag, код фильтра, количество, freshness, без подмены Preview) → Python/Qt → локальный FIR/IQ-кандидат с обратным GetSignal-буфером. **Никакой второй TCP-сессии или команды прибору.** Новый `-3` — внутренний локальный селектор Go IPC, не wire-протокол MVK01.

Исправлены **вместе** Go `source_live_long_window.go`, Python `original_source_long_window.py`, Qt `native_capture_dialog.py` и `main_window.py`; добавлены Go/Python тесты. Синтетический контракт при Fs65536, 20 мс, Code20: выбранные 1310 исходных отсчётов HTag + 51 FIR истории = **1361 pre-FIR** → **655 post-FIR** при Fs32768; Code1: 1407→327 при Fs16384; Code26: 1359→1310 при Fs65536.

Защита: фильтр нельзя считать по обычному Preview, без оригинального SHA-проверенного локального IDP, без полного Go-кольца, с подменённым HTag/кодом/сессией/SHA/Fs, после Freeze или смены частоты. `FRange=1` используется только потому, что Go исходный экран получает уже откалиброванные Float32. Длинные FIR окна (более 262144 входных) **пока блокируются в Qt**, потому что вычисление надо перенести из потока отрисовки в DSP worker; исходное окно не подменяется коротким. Cursor/pixel/Win32 timing 1:1 не принят.

## Общая цепочка после «Измерить» и окончательная граница

Предыдущие пакеты восстановили Mode2→Task2 TCP/10230→PARAM/Status0, FIFO SetRate (только отдельно разрешённый TX), 8 ADC/2 TACH, RAW, исходный rate/Freeze gate, 2^21-ring, GetSignal/GetSpectrum source history, WriteData, WriteValues только по PARAM 0x3100, закрытие writer при Stop и SHA-аудит. Все это интеграционно проверено **в локальных синтетических/loopback сценариях**, не равняется Delphi hardware 1:1.

**ОСТАЁТСЯ `original_delphi_compatibility_verified=false`**: исходный x87 FIR/Hann/FFT/Power/Y, FRange на оригинальной сессии; настоящие Go/Delphi одинаковые RAW и численное GetSignal/GetSpectrum; BIN/TSXML/CSV/локализованный GetValueText/Win32 timestamps; аппаратные DENIED/timeout/reconnect/SetRate/Stop пары; полный Qt курсор и длинный FIR DSP worker. Никаких автоматических Flash/IP/Reboot/SetRate. `main` не менять и не объединять ветки. Продолжать **единым крупным пакетом**, а не micro-stage.
