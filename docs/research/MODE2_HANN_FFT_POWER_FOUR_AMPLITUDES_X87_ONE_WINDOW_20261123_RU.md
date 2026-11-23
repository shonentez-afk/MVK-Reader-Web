# MVKView — единая проверка Hann → FFT → Power → 4 режима (23.11.2026)

## Основание
Следующая незакрытая часть после source GetSignal/GetSpectrum Float64 sum — исходная цепочка Hann → TDSXFastFourier.fft → Single Power → Tag0/1/2/3. Сверены локально приватные Projects.7z/_Unit115.pas, mvkview.idp и mvk_idr(1).sqlite. Эти первоисточники и пользовательские BIN/TSXML/VALUES/TABLE не загружались в репозиторий.

Проверенные исходные переходы: 007D1FE8 (Hann stride 262144/N, затем FFT, затем Single Power); 007CC198 (радиальный radix2, Single stores и twiddle); 007D1586..15BC (низкие бины); 007D15DD..1649 (Tag0, x87 LOG10 и -180 для нулей); 007D1652..16A2 (Tag1); 007D2164 и 007D16A7..172C (Tag2, интегрирование один раз); 007D1731..17E7 (Tag3, интегрирование два раза).

## Что добавлено

- tools/research/x87_spectrum_modes_reference.c — независимая модель x87 для низких бинов, Float32-интегрирования, FLDLG2/FYL2X Log10, FSQRT и четырёх амплитуд; только синтетические данные, без оборудования.
- mvk_compatible/tests/test_mode2_four_mode_x87_end_to_end.py — один SHA-проверенный синтетический Float32 вход: mean/DC удаляется ровно один раз; уже существующий независимый C Hann/FFT/Power сверяется со штатным Python Core побитово; затем все четыре режима и Power после интегрирования сравниваются целиком (N/2 Float32), а не только по RMS/пикам.
- Сценарии: N1024/Fs65536/FRange1; N4096/Fs512/FRange1.25; N8192/Fs65536/FRange0.75. Есть проверка границы низких бинов, нулей dB, полной длины, конечных значений и неизменности исходного массива. На Windows нет x87 C компилятора — аппаратная совместимость не заявляется; тест честно пропускает Linux-only C часть.

Локально до GitHub-пакета отдельный x87 FLDLG2/FYL2X/FSQRT инструмент на 131072 синтетических значений каждого режима совпал с Python-путём 0 различий в каждом из Tag0/1/2/3. Это проверка численного алгоритма, НЕ original Win32 Delphi oracle. Исходники Native/Task2/TCP/RAW/GetSignal/WriteValues/WriteData/Stop и main данным пакетом не изменены.

## Обязательный аппаратный выходной критерий (пока НЕ выполнен)

1. С одной аутентичной пары исходных данных original Win32 MVKView 1.0.47 и нашего Go/Qt получить проверенный same-run RX/PCAP и один и тот же исходный Float32 pre-Hann window/режим/Fs/FRange.
2. Побайтово сравнить из оригинала и нашего результата: Hann Single (полная таблица или выбранная выборка с адресом), FFT complex Single, Power Single, промежуточный Power после каждой интеграции, четыре полных Y Single, GetSpectrum summary; учитывать CW/PC/RC и Win32 x87 Sqrt/Log10. Если оригинальный этап недоступен — оставить конкретный data gate, без ложного 1:1.
3. На ТОЙ ЖЕ принятой сессии проверить WriteData/WriteValues и Stop, границы TCP/Frame mark, BIN/TSXML/VALUES/TABLE, закрытие файлов, ACK/DENIED/reconnect и ошибочные сценарии — только по разрешению оператора оборудования.

Флаги original_delphi_compatibility_verified=false, physical_mvk01_e2e_verified=false, same_physical_capture_authenticated=false остаются без изменений. Автоматические синтетические тесты не снимают аппаратную границу. Не просить пользователя повторно переданные исходники/измерения и не смешивать архивные пары разных замеров.

## CI

Текущий коммит и соответствующий ему GitHub Actions проверять отдельно. PASS предыдущих SHA не приписывать этому пакету.
