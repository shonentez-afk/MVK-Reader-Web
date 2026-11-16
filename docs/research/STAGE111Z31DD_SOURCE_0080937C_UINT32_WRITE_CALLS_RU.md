# Stage111Z31DD — исходный отправитель 0080937C: план вызовов Write UInt32 (БЕЗ TCP)

Дата: 16 ноября 2026. Основано на приватном Projects.7z/_Unit125.pas и mvkview.idp. Ни один из этих файлов не добавлен в репозиторий.

## Исходные адреса

- 00809330 QueueCommand выделяет 12 байт **памяти** под Cmd:Int32, Addr:UInt32, Data:UInt32 и ставит в TList.
- 00809288 Get(0), Delete(0) — FIFO.
- 0080937C..008093FA: восемь последовательных вызовов TIdIOHandler.Write. ECX=0 означает AConvert=False у исходной перегрузки Cardinal Write 007F3E58. Дополнительная проверка _Unit116.pas ToBytes(LongWord) 007D8968 доказала для Win32 little-endian порядок четырёх байтов каждого UInt32; границы TCP-пакетов и ответы при этом остаются неизвестными.
- 00807F2F..00807F52: при source Stage=1 берётся CurrentCommand, EDX=CurrentCommand.Addr, ECX=2 и выполняется 0080937C; далее отдельный Write с EDX=CurrentCommand.Data.
- 00809364 и 00809400: SetRate при изменении MvkSampleRate создаёт Cmd=1, Addr=0x0E, Data=новый INTERNAL rate CODE. Source default 309 — НЕ Hz.

## Восстановленные значения аргументов Write (не packet bytes)

0080937C выполняет восемь последовательных вызовов с EDX:

1. 0xFF800C0D
2. ((ECX >> 1) + 8) * 4
3. 0
4. 0
5. 0
6. 0
7. 1
8. ((ECX << 16) + Addr) modulo 2^32

В ветви очередной команды ECX=2, Addr=0x0E; восемь аргументов получаются: [0xFF800C0D, 36, 0, 0, 0, 0, 1, 0x0002000E]. **Девятый** вызов отправляет Data (для SetRate — исходный новый код частоты, пример в тесте 101, а не измеренная Fs).

Это не значит, что исходный протокол посылает девять отдельных TCP-пакетов. Порядок байтов отдельного UInt32 вызова теперь доказан по private Indy source. По-прежнему не доказаны границы TCP-пакетов, трактовка регистра/команды в ответе, handshake, read timeout, операционное применение пяти оригинальных Tag и эквивалентность собранному MVKView. Недопустимо превращать 12-байтовую TList-запись непосредственно в пакет.

## Реализовано без сетевого доступа

- core/original_mode2_wire_word_candidate.py — чистая функция header_source_words и модель plan_verified_source_rate_command только для исходно подтверждённого SetRate. Никаких socket/QProcess/Go импортов; невозможна отправка команды.
- tests/test_stage111z31dd_source_wire_word_candidate.py — стабильная проверка восьми исходных UInt32 Write arguments, девятого Data, недопустимых размеров/типов, отсутствия аппаратного sender и неизвестных команд.

## Дальнейшая приёмка

1. Перегрузка Indy восстановлена: _Unit123.pas 007F3E58 с AConvert=False и _Unit116.pas 007D8968 с memcpy DWORD в 4 bytes — Win32 little-endian. Следующая проверка: границы TCP, исходные ответы и полный exchange с разрешённым пассивным PCAP или закрытым offline эмулятором.
2. В закрытом offline-эмуляторе восстановить ответы/ошибки/порядок обмена. Тестировать без физического МВК01.
3. Только после независимой проверки полной транзакции и разрешения ответственных лиц рассматривать физическую проверку с прибором.
4. В основной Native R6.1 **никаких новых команд**: его read-only поток и исправленные DB/DC жизненные циклы остаются неизменными.

## Дополнение по предоставленной SQLite (Stage111Z31DE)

Приватная mvk_idr(1).sqlite: 25 404 функции, 92 767 calls, 95 DFM events, 162 components, 3 forms; все 95 event rows имеют resolution=exact_unique. В поле reconstruction лежат только короткие метки, не исходный дизассемблированный текст; full IDP RTTI не декодирован. Для точного разбора обработчиков SQLite необходимо проверять по локальным PAS/DFM. Ключевое подтверждение: кнопка bSampleRate запускает popup bAnyDropDownClick, а пять пунктов создаются динамически из gvar_008D2F7C через TMenuItem.Insert(0). Именно mRate1Click вызывает SetRate. Вход в Mode2 создаёт TMVKThread и сразу вызывает mRate1Click до активации PageStatus/таймера. Таймер tmInterfaceUpdate=20 ms из DFM вызывает обновление только ActivePage (6 возможных страниц), затем видимой pnMeasure; не 7 страниц одновременно. У SQLITE components.properties_json поля Interval нет, несмотря на его наличие в DFM.

Программная модель SourceWordCallPlan.indy_uint32_stream_bytes теперь доказательно формирует 4-byte little-endian последовательность только в RAM, без сети; receiver/ACK/физический паритет по-прежнему НЕ доказаны. Полная приватная SQLite не выкладывается в GitHub.
