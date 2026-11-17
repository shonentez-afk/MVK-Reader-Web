# Stage111Z31FJ — длинный GetSignal из оригинального 2M-кольца Go → Core → Qt

Дата: 17 ноября 2026. Рабочая ветка: `research/stage111-mvkview-desktop-20261029`.

## Три обязательных приватных источника

Локально сверены `/mnt/data/mvkview.idp`, `/mnt/data/Projects.7z`, `/mnt/data/mvk_idr(1).sqlite`; ни один приватный исходник не публиковался.

- **IDP + SQLite:** `TMvkChannelStorage.GetSignal` = `007D0C30`, `CheckDataAvailability` = `007D1998`, `AllocBufferChunk` = `007D1B08`, `ProcessBufferChunk` = `007D2398`; `tmInterfaceUpdateTimer` = `0084F7C8`; SQLite `quick_check=ok`, 25404 functions/92767 calls/95 events. Исходная программа получает реальное окно только после проверки кольца, а 20мс GUI-таймер НЕ создаёт новые отсчёты.
- **Projects.7z:** `_Unit128.pas` создаёт при Mode2 8 Float32 + 2 BYTE `TMvkChannelStorage` c `FBufferSize=0x200000` каждый. `_Unit115.pas` использует UInt64 `FRxPos/FValidPos`, проверяет `CheckDataAvailability`; `_Unit125.pas` передаёт в storage только полученные исходные TCP-данные. Четыре исходных PAS/DFM ранее повторно проверены по SHA256 против SQLite. Файлы в репозитории отсутствуют.
- **Фиксация типов:** сетевой `SampleHeader.Index` — uint32 с естественным переполнением; `FRxPos` — локальный uint64. Привязывать их друг к другу простым числовым сравнением нельзя.

## Проблема FI

Stage111Z31FI реализовал полноценное Go-кольцо 8×2^21 Float32 + 2×2^21 Byte, но `MVK_NATIVE_LIVE_PREVIEW.zip` по-прежнему переносит максимум 262144 Float32 на ADC. Исходный `bAdcHScale` при 65536Гц и 20с требует 1310720 действительных отсчётов; уменьшать до 262144 или добавлять нули запрещено.

## Изменения FJ

1. **Go:** `source_live_long_window.go` принимает один атомарный локальный `MVK_SOURCE_WINDOW_REQUEST.json` **только внутри уже разрешённой папки текущего Native-сеанса**. В запросе: `session_id`, неповторяемый `request_id`, номер АЦП, настоящий `bAdcHScale Tag`, точный `N=Fs*ms//1000`, локальный `capture_end` uint64 и сетевой `device_end_index` uint32. Никаких произвольных путей, произвольных N, второго сокета или команд прибору.
2. **Go в единственном потоке:** после проверенного `MVK_NATIVE_LIVE_STATUS.json` считывается **ровно один** выбранный непрерывный Float32 участок из уже восстановленного полного кольца; проверяются текущая Fs, непрерывность, исходный диапазон `FValidPos`, незатёртая история, абсолютный индекс с modulo-2^32 и calibrated domain. Отсутствие реального окна отклоняет запрос. Создаётся atomically replaced `MVK_SOURCE_WINDOW_RESULT.zip` с `zip.Store` и SHA256 одного ADC, объём не более ~8МиБ.
3. **Core:** `original_source_long_window.py` создаёт локальный запрос, строго проверяет `run_directory`, session/request ID, SHA, точную исходную `Tag/N/Fs`, raw counters, byte length, float32 finite, source-end/uint32+64bits, неизменённую калибровку и границу перезаписи. Верифицированный `LivePreview`-объект создаётся **только из одной подтверждённой 2M-вырезки**. Реальный FFT остаётся в прежнем pipeline.
4. **Qt:** `NativeCaptureDialog` опрашивает локальный результат через текущий 900ms статус, но создаёт запрос **только на активной PageAdc** и не чаще раза/3с при N>262144. `MainWindow` использует штатный `provisional_waveform` и `source_getsignal_readiness` с точным размером N. Экран получает не более 4000 min-max-отображаемых точек, числовые параметры считаются по исходному всему окну; 20ms графический таймер не перестраивает 1.3M окно 50 раз/с.
5. **STOP/error:** новые окна не допускаются при ошибках потока, смене сеанса, freeze, остановке, изменении частоты или нехватке истории; поздние сообщения не могут воскрешать отключённый график.

## Приёмка

Тесты Go: фактическое 20с окно 1310720 Float32 из кольца, переполнение uint32, SHA/ZIP store, отсутствие повторного копирования для одного ID, защита от подделки/end-index, от перезаписанного участка, неверных Tag/N/session и symlink. Core: контракты N/Fs, SHA/сессии, 2M ring overwrite, stream rollover, 4000 min-max точек из 1310720 **реальных** Float32. Qt: реальный QWidget рисует исходные 20с в одной PageAdc, не перерисовывает старые 5МиБ на 20ms, не запрашивает пока PageStatus/Stop/freeze.

CI: должен завершить 4/4 для кодового SHA, включая Go native build и Windows Qt. Не объявлять полный PASS до подтверждения.

## Не завершено этим пакетом

Новый путь пока **не** восстанавливает оригинальный Win32 x87/FIR/TQGrapher численный паритет, не добавляет/включает аппаратные команды и не проходит проверку на физическом МВК01. Исходный `FreezeUpdate` и длительные записи всех статусов остаются открытыми; `original_delphi_compatibility_verified=false`. Приватные IDP/PAS/DFM/SQLite/RAW/PCAP не коммитить.
