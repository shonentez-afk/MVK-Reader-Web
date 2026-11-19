# Восстановление исходной цепочки FRange и ProcessBufferChunk (MVKView 1.0.47 / Native Mode2)

Дата: 19 ноября 2026 года. Исследовательская ветка `research/stage111-mvkview-desktop-20261029`.
Код: [`6c4a4cb`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/6c4a4cbaa0a3f308f5f004df8c7d5deb64bc149a), [`2f728e6`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/2f728e6840401a8f25a31a7aff27810b5738f963), [`0cd35cf`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/0cd35cf022f42f27790ae69e964b227403cccbea), [`7196169`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/71961692b8116d9d648840c5142c48d49dfe31e5).
Финальная регрессия: [GitHub Actions #44464375293](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44464375293). До полного окончания **не заявлять software PASS** и не заменять аппаратную парную проверку синтетическими данными.

## Три приватных источника — использованы вместе, без публикации

1. `/mnt/data/Projects.7z` SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`. Исходные `_Unit115.pas` (690281 байт), `_Unit125.pas` (1766784), `_Unit128.pas` (523337) и `mvkform.dfm` сверены по SHA256 и размерам с `source_files` SQLite. Никакие дизассемблированные файлы или уникальные байты оригинала в коммиты не включены.
2. `/mnt/data/mvk_idr(1).sqlite` SHA256 `97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c`, `PRAGMA quick_check=ok`. По таблице `functions/calls` проверены `TMVKThread.Execute=00807A98` → `TMvkChannelStorage.AllocBufferChunk 008081F6` → `TMvkChannelStorage.ProcessBufferChunk 0080828C` (адрес функции `007D2398`); архивный загрузчик `0084F7D0` → `0084F98F` также вызывает этот метод, но с **другим** `ApplyRange`.
3. `/mnt/data/mvkview.idp` SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Оригинальные поля `TMvkChannelStorage.FRange:Single +4`, `FAdcDataType +0C`, `PAdcFloatData +34`, `FRxPos +20`, `FBufferMask +14`; `TMVKThread.MvkSampleRate +400D0`, `FreezeUpdate +400CD` согласованы с Pascal и SQLite.

## Перепроверенный оригинальный алгоритм

### LIVE приём после кнопки «Измерить»

- `_Unit128.pas` `Tmvkform.bTaskConnectClick 00846C7A..00846CB2` вызывает `TMvkChannelStorage.Create` для 8 ADC типа Float32 и 2 TACH типа Byte, каждый с ёмкостью `0x200000`. Для LIVE не используется сохранённая локальная архивная нормализация.
- `_Unit115.pas` конструктор `007D0A61` инициализирует `FRange:Single = 1.0`. Это конкретно подтверждённая стартовая величина для исследованного исходного Mode2, а не коэффициент, угаданный по регистрам прибора.
- `_Unit125.pas` `0080822F..0080824B`: перед обработкой проверяются `packet.Fs == MvkSampleRate` и `!FreezeUpdate`; всё TCP сначала читается в RAW независимо от этого разрешения.
- `_Unit125.pas` `00808284` устанавливает `cl=1` (`ApplyRange=true`), затем `0080828C` вызывает `ProcessBufferChunk(SizeBytes, true)`.
- `_Unit115.pas` `007D2398..007D23E1`: если `FAdcDataType==0` и `ApplyRange`, каждый **Float32 в самом приёмном кольце** преобразуется как `Single(Float32_wire * FRange)`; затем `FRxPos += SizeBytes / 4` (для BYTE/TACH — `FRxPos += SizeBytes`). Для первоначального LIVE `FRange=1.0` это исходные Float32-биты (для конечных чисел).
- `GetSignal 007D0C30`, `GetSpectrum 007D13D4`: исходное кольцо — отдельная область данных; копирование для обработки имеет ветку деления на `FRange`, а итоговая линейная амплитуда снова масштабируется через исходное поле. При начальном LIVE `FRange=1` повторное перемножение «Native gain» не требуется и было бы ложной калибровкой.

### Открытие архивных файлов — НЕ путать с LIVE

- `_Unit128.pas` `008464B0..0084655E` — отдельная ветка загрузчика сохранённых данных. По первичным данным `TMvkCellList.GetFloatByAddr` она устанавливает **архивный** `FRange` из отношения исходного поля канала к чувствительности датчика, с защитным fallback `100.0` при очень малой чувствительности. Только после этого `0084F982..0084F98F` вызывает `ProcessBufferChunk` с архивным флагом `ViewedFileIsNormalized`.
- Происхождение архивной настройки и поразрядный Win32 x87 результат на произвольных аппаратах не верифицированы аппаратно. **Нельзя переносить архивную формулу на LIVE** по названию `FRange`.

## Выявленное расхождение нашего Native R6.1 и исправление

**Раньше:** `LiveBinSpool` применял независимый реконструированный device-register gain из `0x0100 + ch*0x100 +0x0E`, затем мог напрямую помещать **уже умноженные** числа в названное «оригинальным» кольцо `2^21`. GetSignal/GetSpectrum неверно принимали домен `CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32` за первичное кольцо MVKView. По исходному Pascal это разные задачи; такая подмена могла исказить амплитуды.

**Теперь (общий кодовый пакет):**
- `Monitor.consume` после оригинального `rate/Freeze` gate записывает в кольцо **только исходные Float32 из того же TCP пакета** с отдельно проверяемым `sourceApplyOriginalFRange(FRange=1.0)`. Запись выполняется **один раз на допущенный пакет**. Идентификатор: `ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32`; подтверждение `original_live_f_range_single=1.0`.
- Между `LiveBinSpool` и `sourceOriginalStorageRing` **полностью удалена ссылка в типах Go**; экспортёр не может подменить приёмные данные даже при ошибочном будущем вызове. Существующий экспериментальный BIN и независимое сравнение с RAW не сломаны.
- `source_live_long_window.go` теперь выдаёт запросы `HTag / bSpecLines / FIR` только из непрерывного `ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32` кольца; пакетный манифест/сырые bytes/SHA/индексы и `FRange=1` остаются связанными с оригинальным `FRxPos`.
- Python `original_source_ring_receipt.py`, `original_source_long_window.py` и `original_live_view_gate.py` требуют **оба доказательства**: Go-домен исходного кольца **и** `FRange Single=1`. Прошлое название калиброванного BIN отвергается; склеить старый ZIP и новый статус нельзя.
- `native_r6_live_preview.py` различает старое forensic BIN-preview и оригинальную картину приёма. FFT-кандидат для источника передаёт `input_domain=original_float_storage` и `f_range=1.0`, а не `calibrated_bin`; GetSignal/FIR использует полный `float32`, не коэффициент экспортёра повторно.
- `sourceApplyOriginalFRange` отдельно проверяет представимость типа Single и Float32-произведение. Для двух нормальных конечных binary32 множителей Float64 обеспечивает точный 48-битный продукт перед корректным округлением в Float32; **это не претензия на общий Win32 x87 1:1** для NaN, субнормалов, изменённого CW и сложных DSP-цепочек.

## Новая сквозная регрессия

- Синтетическая начальная PARAM-схема с **gain ADC1 = 510.0**, исходный TCP ADC Float32 `0.125`. В оригинальном живом кольце обязательно `0.125`, в отдельном forensic BIN `63.75`. Старый механизм ошибочно делал в кольце `63.75`; этот тест доказывает принципиальное исправление.
- Проверено, что экспортёр конструктивно не имеет ссылки на исходное кольцо; обычный RAW не изменяется.
- Границы `FRxPos`, SHA одного Float32 окна, строгий `FRange1` JSON/Qt/Go контракт, защита от изменённых коэффициентов и чужого BIN-превью.
- Проверены без хардкода физических команд: тесты `source_original_f_range_live_test.go`, `source_original_ring_test.go`, `test_mode2_original_source_live_f_range_1.py`, `test_stage111z31fj_original_long_window.py`, Qt source-view gate и весь общий пакет.

## Ограничения / оставшаяся приёмка

- `original_delphi_compatibility_verified=false`. Синтетические PASS и совпадение исходных адресов не доказывают побитовую Win32 x87 обработку, все варианты ошибок/потерь и физическую работу МВК01.
- **Живое значение FRange** установлено из исходного конструктора Mode2 и проверенной ветки вызовов. Если в реальной оригинальной программе оно изменяется после старта из необычных настроек датчика — требуется трасса записи поля `TMvkChannelStorage.FRange +4`; не выдавать FRange=1 как доказанный универсальный диапазон для всех offline файлов.
- Native BIN-перевод с register gain пока является независимой реконструкцией; исходные подписи, время и побайтовый Delphi TSXML/CSV/GetValueText не приняты.
- Совместная реальная приёмка `IP → Измерить → 8 ADC/2 TACH → original ring/FRange/FFT → WriteData/WriteValues → Stop/reconnect` должна сравнить одинаковую PCAP/RAW и форматы файлов с оригинальной запущенной Win32 MVKView, включая прерывание/ошибки.
- Исходники Pascal/DFM/IDP/SQLite, FIR-коэффициенты, PCAP и данные приборов **не публиковать**. Ветка `main` не меняется.

Дальше работать **крупными интегрированными пакетами**, без микро-PR и без ложных заявлений полного оригинального паритета.
