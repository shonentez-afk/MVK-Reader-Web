# Stage111 EE — TACH / метаданные: интеграция в Task2

База 8ebddeedb40d7a7f84738db4d09552a467686479, проверенная EE. Отдельная исследовательская ветка, без слияния и без новой принятой EXE.

- Проверенная модель состояния подключена к фактическому main/Monitor Task2: успешный TCP connect задаёт epoch, первый принятый/замороженный PARAM descriptor фиксирует Range/Units. Метаданные сохраняются отдельно от forensic RegisterImage, LiveStatus/summary содержат наблюдение с provenance. NumericScalingApplied=false: FRange ещё не подключён к численному ring/Qt/DSP/BIN.
- TACH: реальный allowedFrame → 64-byte SHA-bound admission record → local byte-change latch. Даже пустые TACH пакеты учитываются, но не изменяют latch. На 0x3100 snapshot обоих latch до reset; без открытого writer reset тоже выполняется. RAW image и V1 PARAM gate не меняются. V2 writer получает явную версию схемы.
- Python повторяет change/reset из RAW + PARAM Freeze + TACH journal. Проверяет полный SHA, порядок, epoch, Fs, flags и канал, сравнивает строки Go. V1 архивы не получают новой аттестации. Multi-socket общий архив по-прежнему не принимается. Локальный журнал не подписан прибором и не доказывает runtime оригинала.
- Тесты реального Monitor/Finalize: first descriptor, metadata suffix, unarmed reset, both channels, frozen и wrong-rate frames, trigger-before-reset, suffix, repeated unchanged byte, RAW preservation, V1/V2, reject rehashed corrupt journal/row. Отдельные CI jobs native Windows/Linux + Python cross-language/full core. Статус проверять по фактическому SHA.

Остаток: окончательное применение FRange и Units по всей цепочке Go Storage / local window receipt / Python FIR+FFT / Qt / TSXML; отдельная source latch projection в PageStatus/TABLE. Не включать приборные команды, не менять main. Не считать это полной приёмкой 61 маршрута. Приватные материалы не публиковать.
