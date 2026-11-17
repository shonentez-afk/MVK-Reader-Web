# Stage111Z31ER — прямое исследование mvk_idr(1).sqlite, исходный путь IP → Измерить → запись

Проверено 17 ноября 2026 г. Исследовательская ветка. Приватную SQLite, PAS, DFM, IDP, PCAP и RAW НЕ загружать в публичный GitHub.

## 1. Что находится в базе

Файл mvk_idr(1).sqlite, 20 942 848 байт, открыт в read-only, PRAGMA quick_check(1) = ok. Таблицы: meta, source_files, forms, components, events, functions, calls. Содержимое: 3 формы, 162 компонента, 95 событий, 25 404 функции, 92 767 вызовов, 133 исходных файла.
В meta.idp_header: format IDR proj v.3, Delphi 2014, image_base 00400000, entry_point 008C1DC0. ВАЖНО: scope = header_and_segments_only; full IDP object/RTTI records not decoded. SQLite — индекс Pascal/disassembly и DFM-событий с частичной IDP-шапкой, не полноценное автоматическое восстановление всех объектов IDP.

Локальные SQL-запросы проверки (на самом приватном файле, НЕ в GitHub):

```sql
PRAGMA quick_check(1);
SELECT COUNT(*) FROM functions;
SELECT COUNT(*) FROM calls;
SELECT component_path, event_name, handler_name, handler_address
  FROM events WHERE form_name='mvkform' ORDER BY line;
SELECT site_address, raw_target, resolved_address
  FROM calls WHERE caller_address='00846AD4' ORDER BY site_address;
```

## 2. IP и источник задания

- bTaskConnectClick 00848E78 → sub_00846AD4 с Task=2 (измерение).
- bTaskConfigIPClick 00848E6C → sub_00846AD4 с Task=4 (ОТДЕЛЬНАЯ настройка IP); нельзя выполнять как обязательную часть Measure.
- Device/Address из оригинального Windows-1251 XML → edIpAddr.Text → TMVKThread.IPAddress, TCP/10230. Локальный IP адаптера — отдельная величина. Никакого подтверждения обязательного автообнаружения IP перед каждым Measure нет.
- sub_00846AD4: 55 вызовов, включая TMVKThread.Create 00846DD1, mRate1Click 00846DF7, переключение вкладок SetTabVisible 00846D2C..00846D74 и запуск таймера 00846E45. Вкладки появляются до TCP.
- tmInterfaceUpdateTimer 0084F7C8 обновляет дисплей независимо от TCP, исходный интерфейсный DrawInterval=20ms НЕ является частотой АЦП.

## 3. Оригинальные WriteData / WriteValues

- bWriteAdcClick 0084E914: WriteData Boolean и дата/время запуска, десять масок cbFileChannels в [TMVKThread+400D4 .. +400DD].
- bWriteValuesClick 0084E988: WriteValues Boolean и время запуска, 43 спектральные маски +400DE, 24 параметра АЦП +401DE, 43 полосовых +402DE, 6 тахометрических +403DE, ещё десять каналов +400D4.
- bWriteTableClick 0084E020: отдельная локальная операция экспорта таблицы, не команда прибора и не замена WriteData/WriteValues.
- _Unit125: исходное WriteDataStage=2, после включения 2→0 (открытие до 10 файлов), переход 0→1 по первому кадру ADC0 при совпадении исходной частоты и отсутствии FreezeUpdate, завершение 1/0→2 с закрытием файлов. Анализ 00809414..00809811, 00808294..008082DC.
- WriteValuesStage=2→1 при создании VALUES-*.csv, закрытие 1→2 при выключении. Анализ 00809814..008099CF. Имена данных имеют дату yyyy-mm-dd--hh-nn-ss, канал .bin, значения VALUES-...csv.
- Исходные VALUES заголовки пишутся через sub_00806334: префикс sep=|, pipe delimiter |, локализованный xTime, TMvkCellList.GetTitle и xChannel; строка sub_008066F0 использует часы hh:nn:ss.zzz и TMvkCellList.GetValueText.
- КРИТИЧЕСКИЙ trigger WriteValues: _Unit125 008085A5..008085BD проверяет адрес входящего блока PARAM 0x3100 при Task=2 и существующем ValuesFile; лишь тогда вызывает sub_008066F0. Это НЕ AUX4700 — не считать все AUX обновления CSV-строками оригинала.
- Read-write SetRate: mRate1Click 0084DEC4 → TMVKThread.SetRate 00809400 → FIFO 00809364/00809330; фактический source Task2 36-byte LE command после PARAM/Stage1 при отдельном разрешении.

## 4. Исправлено в совместимой Core/Go (Stage111Z31EL–EQ)

- Go Native публикует исходный счётчик values_ticks_address_3100 отдельно от aux4700_updates во время записи и в Source Frame Mark audit.
- Core проверяет согласованность исходных 0x3100-триггеров с финальным summary и границами операторских кадров, а не подменяет их AUX-тиками.
- Локальный WriteData/WriteValues Core больше ошибочно не запрещает исходную работу после разрешённой настоящей SetRate; реальный источник TX строго проверяется, аппаратные команды не приписываются кнопкам записи.
- Core отказывает в ложной записи через два физических TCP-сокета как в один непрерывный BIN; отдельно SHA-верифицированные RAW сохраняются.
- Добавлены тесты выбора масок, этапов 2→0→1→2 / 2→1→2, действительной санкционированной SetRate, несоответствия числа VALUES и другого TCP-сеанса.

## 5. Что НЕ восстановлено окончательно

Оригинальный live TFileStream с точными временными границами, побайтовая запись настоящих Delphi BIN и VALUES CSV со всеми локализованными GetTitle/GetValueText, однозначный источник ВСЕХ расчётов DSP/FFT/RPM/FRange, полный паритет семи страниц/трёх форм и все сервисные Task=4/настройка IP, Upload/Download/Calib в живом приборе, аппаратные тесты после Measure. То, что исходный обработчик присутствует в IDR, НЕ доказывает, что он уже реализован в Qt/Core. Не устанавливать ложный флаг full original Delphi compatibility.
