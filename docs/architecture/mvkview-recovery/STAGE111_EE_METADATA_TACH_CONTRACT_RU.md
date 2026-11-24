# Stage111 Z31EE — уточнение FRange/Units и TACH

24.11.2026. Актуальная рабочая ревизия `8ebddeedb40d7a7f84738db4d09552a467686479`. Z31EE уже включает восстановление имен файлов, third-octave, части локальных маршрутов конфигурации и полного StatusSerial. [CI #45364186556](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45364186556) 5/5 SUCCESS. [Windows ZIP #14905444970](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45364186556/artifacts/14905444970). Prefix CI #45364186730 SUCCESS. ED full CI был отменен новым запуском; не выдавать его за отдельную принятую сборку.

## Результат нового сравнения

133/133 SHA исходников, IDP SHA и SQLite quick_check подтверждены локально. Машинные CALL и таблица адресов двух локальных TACH признаков повторно сверены. В оригинале первый ДЕСКРИПТОР непустого PARAM, не окончание всего frame, инициирует фиксацию Range/Units. Даже при Freeze пропускается изменение образа, но происходит Stage0→1. При reconnect прежняя Storage и register image сохраняются до этой точки. Нулевой Range становится 1, TACH Range=1/Units empty. ADC type9 units: 32 bytes до NUL, преобразование byte→char. При RX масштабирование выполняется перед продвижением позиции; plain GetSignal копирует physical, normalized paths делят на текущий Range и восстанавливают его в соответствующем выходном преобразовании. Не пересчитывать старые отсчеты задним числом и не применять двойной gain.

Признак TACH impulse — latch изменения принятого байта, не RPM и не количество импульсов. Сохраняется последний байт; перед reset оба значения доступны для VALUES. При принятом 0x3100 сбрасываются оба latch даже без открытого writer, но не последний байт. Freeze не изменяет latch. Действующий EE проверяет свежесть PARAM prefix, а не этот RX→latch→reset. Его PARAM journal не доказывает admission TACH, поэтому простая подмена последнего поля разрушит независимую проверку RAW.

## Исполняемый кандидат

[Отдельная ветка и код](https://github.com/shonentez-afk/MVK-Reader-Web/tree/research/stage111-ee-metadata-tach-contract-20261124/tools/research/stage111_source_metadata_contract), commit `8ddae35411e9a0c952961590b9b0b00ca151979b`. 6 top-level Go tests, 8 named subtests, 972 exhaustive TACH cases PASS; go vet PASS. Два Git blob SHA побайтно совпадают с локальными тестированными файлами. Это самостоятельный source-contract candidate, не действующий Monitor и не новая EXE. Unknown регистры не выдаются за полученные нули; exceptional x87 не аттестован. Приватные исходники, IDP, SQLite и граф не загружались. Полная карта v32 сохранена без изменений. Локальный архив `MVK_Z31EE_METADATA_TACH_CONTRACT.zip` содержит код, тесты, локальную QA и приватный handoff.

## Продолжение

Следующий крупный пакет: SHA-bound TACH admission/epoch ledger и независимый replay, сохранение snapshot-before-reset, новая версия source proof с совместимостью старых artifacts; перенос Range/Units через Go ring/long-window/Python/FIR/FFT/Qt и корректное разделение исходных и физических байтов BIN/TSXML. Не менять уже принятый VALUES prefix/Stop и не включать приборные команды. Нужна проверка SAME-RX и численного паритета. Не считать этот проход полной приемкой 61 маршрута.
