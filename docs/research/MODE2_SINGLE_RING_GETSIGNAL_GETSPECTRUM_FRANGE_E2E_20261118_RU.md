# Единая приёмка: IP → Измерить → исходный 2M ring → GetSignal / GetSpectrum → Stop

**Дата:** 18.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. Продолжение одной большой задачи восстановления, без отдельных micro-stage. Все новые действия ниже **локальны**, не открывают второй TCP-сокет и не отправляют команды МВК01.

## Доказательная база — три оригинальных приватных источника вместе

- `/mnt/data/mvkview.idp` (IDR v3, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`): типы `TMvkChannelStorage`, поля `FRxPos`, `FValidPos`, `FBufferSize`, `FBufferMask`, `FRange`, `TMvkChannelStorageCalcParams`; исходные адреса вызывающих процедур.
- `/mnt/data/Projects.7z` (SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`): локально извлечены и SHA256/size независимо сверены с SQLite **все пять** `_Unit114.pas`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`, `mvkform.dfm`; приватные тексты/байты не опубликованы. В `_Unit115.pas` восстановлены `GetSignal 007D0C30..007D0E57`, `GetSpectrum 007D13D4..007D1937`, `CheckDataAvailability 007D1998..007D1A06`, `ProcessBufferChunk 007D2398..007D23FE` и чтение кольца `007D2228`. В `_Unit128.pas` подтверждены переходы UI к `GetSignal 00847FCF` и `GetSpectrum 00848200`.
- `/mnt/data/mvk_idr(1).sqlite` (SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`): структура `functions/calls/source_files`, `quick_check=ok`, адреса `007D0C30,007D13D4,007D2398` и строки `_Unit115.pas` совпадают с извлечёнными исходниками.

## Найденное существенное расхождение

До исправления реальный Go-приёмник правильно сохранял в `incoming.raw` **все** ADC/TACH, а исходное отдельное 2²¹-элементное кольцо пропускало пакеты при `FreezeUpdate` и `Fs!=MvkSampleRate`. Однако Qt для короткого временного сигнала и любого Live FFT мог брать **обычную Native preview ZIP**, где такие пропущенные пакеты всё ещё есть, и тем самым выдавать данные TCP-просмотра за оригинальный `GetSignal/GetSpectrum`. Локальный source-ring IPC с SHA раньше поддерживал только H-время длиннее 262144 отсчётов; его валидатор ошибочно отличал source ring от preview **по длине массива**.

## Связанные исправления, одна система

1. **Go-приёмник** `source_live_long_window.go`: существующий единственный обработчик локального `MVK_SOURCE_WINDOW_REQUEST.json` теперь возвращает SHA-bound копию настоящего `sourceOriginalStorageRing.window` для **любого исходного bAdcHScale Tag0..13**, включая короткий сигнал, с `0<N<=2^21`. Не полученные или перезаписанные отсчёты, смена Fs, Freeze и недостоверный датчик остаются отказами. Для спектра `source_h_tag=-1` — **только локальный** IPC-дискриминатор, не оригинальный HTag/команда; `samples` обязан точно совпадать с одним из восстановленных `bSpecLines`: 1024/4096/8192/16384/32768/65536/131072/262144. Кадры из отдельного RX-потока не синтезируются, zero-padding не применяется.
2. **Python** `original_source_long_window.py`: тот же контракт строгой проверки session ID, status, `FRxPos`, `FValidPos`, `first_readable`, device sample index (uint32 wrap), `RAW counters`, ZIP `SHA256`, калиброванного домена. `submit_source_fft_window` запрашивает точное N через тот же ограниченный файл; `load_source_long_window` проверяет ответ независимо. Обозначение `source_ring_provenance_verified=True` появляется **только после проверки ZIP и текущих позиций Go**, а не по размеру окна.
3. **Qt** `native_capture_dialog.py`: один переключаемый источник запросов в одном TCP-сеансе: на PageAdc выбирается bAdcHScale, на PageSpectrum — bSpecLines. Не чаще одного обновления за 3 с, без второго сокета, без физической TX, без сохранения избыточных 8×2M снимков.
4. **Qt** `main_window.py`: отдельные состояния подтверждённых окон GetSignal и GetSpectrum; переключение АЦП/режима/FFT не переиспользует старое окно, Stop/ошибка очищают оба. Если validated Go storage доступно — live-график разрешается **только по проверенному окну этого кольца**. Пока оно отсутствует, очищается прежний график и показывается ожидание; Native preview больше не подменяет источник. Для исторического статуса без проверенного кольца прежняя Native preview остаётся явно помеченным кандидатом, а не оригинальным измерением.
5. **`original_live_view_gate.py`**: source ring определяется явным SHA-проверенным признаком, а не `len(samples)>262144`; короткое окно после Freeze сравнивается с original `FRxPos`, а обычное preview — с forensic Native samples и gate. Никаких «переводов» неподходящей Fs или Freeze-отсчётов в исходное кольцо.
6. **FRange**: текущий Go source-ring ADC домен маркирован `CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32`; FFT и GetSignal читают те же калиброванные Single, а `FRange` **не применяется дважды**. Исходный Delphi `ProcessBufferChunk 007D23B7..007D23E5` масштабирует ADC Float32 при `ApplyRange`, `GetSpectrum 007D1494..007D14A5` читает с обратным делением на FRange, затем линейный спектр умножается на FRange. На Go исходные raw-байты и калиброванный ring домен различены. Пока нет оригинального физического FRange и пары Delphi BIN/RAW, нельзя объявлять побитовое совпадение чисел, x87/Hann/FFT и единиц.

## Общая приёмка и негативные кейсы

- Go `source_live_long_window_test.go`: короткий (500мс) HTag после Freeze; 20с окно; FFT N=65536 в том же кольце, точные байты `ADC1.f32`, SHA и индексы; отказ при чужой сессии, неподдерживаемом N, перезаписи, ошибочной Fs, не-RAW запросах; `SourceSetRateBytes==0`.
- Python `test_stage111z31fj_original_long_window.py`: короткий SHA/source-ring GetSignal после пропущенных freeze-сэмплов; FFT строго по `bSpecLines`, no second gain, запрет фальшивого ZIP и недостающей истории.
- Pure `test_stage111z31db_live_view_gate.py`: короткий подтверждённый source ring не превращается в Native preview по размеру; при исчезновении проверки кольца — отказ.
- Windows Qt `test_stage111z31db_qt_live_view_gate.py`: если source ring проверен, но новое локальное окно ещё не получено, **не рисовать обычный TCP preview** ни в PageAdc, ни в PageSpectrum.
- Все пять CI jobs должны завершиться PASS **на одном финальном кодовом SHA**: Linux Go, Linux Core, Windows Core/Qt, Windows QPA 100/150%, Windows EXE. Приватные исходники/PAS/DFM/IDP/SQLite/реальные RAW/PCAP не помещать в CI.

## Что всё ещё OPEN

Это синтетический контракт и source-backed алгоритм, **не битовая 1:1 приемка Delphi**: физические МВК01 и парный оригинальный сеанс; оригинальная функция GetSpectrum в x87 на тех же Float32, точная FIR/огибающая, численная FRange из измерения/TSXML, Win32 имена/время BIN/TSXML/CSV и WriteValues GetValueText локализованные строки; аппаратный timeout/DENIED/reconnect и разрешённый оператором SetRate. `original_delphi_compatibility_verified=false`. Не изменять main, не отправлять Flash/IP/Reboot.
