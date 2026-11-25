# Stage111Z31EJ — A02: TACH1/TACH2 Byte, GetSignal, GetSpectrum и курсор

Дата: 24.11.2026. Код: 3432086fba21e7e00bfe5b397193155d7264cc3f. Кандидат PR #17, ветка `fix/stage111-eg-computation-links-20261124`. Main не изменять. Это статически восстановленная реализация и синтетическая регрессия, не физическая аттестация MVKView.

## Источники и связи

Повторная локальная сверка Projects.7z, mvkview.idp, mvk_idr SQLite: _Unit115/_Unit125/_Unit128 соответствуют индексированным исходникам. Приватные материалы в репозиторий не помещены.
- GetSignal 007D0C30 -> 007D2228 (007D0CD6); GetSpectrum 007D13D4 -> 007D2228 (007D14A5). Byte branch 007D2317..007D232D: fild Byte, /255, store Single.
- PageAdc 00847EAC -> GetSignal 00847FCF; для type2 00847F49..00847F6C параметры NoDC и FIR равны нулю. PageSpectrum 00848148 -> GetSpectrum 00848200; удаление среднего 007D14B3, далее штатный спектральный тракт. 0084BB66 выключает spectrum envelope для Byte.
- TACH FRange=1 и пустой FUnits (00806964..008069E6). Пустые единицы не заменять на Count из файлового TSXML. GetDerivedUnits с пустым FUnits для режимов 0/1 возвращает пустую строку, 2/3 — ~ и ~~; дБ ось отдельно.

## Реализация
- Два live канала 9/10 в существующем IPC, только explicit Byte width=1. TACH1.u8/TACH2.u8 содержат реальные байты ring, SHA, sample_width_bytes и device_end_word_index. ADC сохраняет прежний Float32 контракт.
- Длина запроса в элементах Fs*ms//1000 либо FFT N; FRxPos TACH в байтах, wire index в 32-bit словах; lag между окнами должен согласовываться с шагом /4. Проверяются фактический word cursor и byte cursor, включая wrap/алиасы. Нельзя считать четыре байта одним графическим Float32.
- Python проверяет тип, длину, SHA, домен, актуальность окна и оба индекса; предыдущий ответ другого request_id не принимается. Byte->Single /255 только в вычислительном provider. GetSignal без DC/FIR, GetSpectrum удаляет среднее, Hann/FFT по прежнему backend. Курсор указывает локальную позицию Byte, не абсолютное время прибора.
- Qt: десять каналов только Mode2, синхронные селекторы, AC+DC и выключенные envelope controls на TACH; обратно ADC восстанавливает управление. Старые восемь ADC в offline/Stop. Проверка legacy NaN-looking word patterns: forensic счётчик сохранён, verified Byte ring не объявляется неисправным ADC Float32.
- EI cross-language fixture теперь изолирован в отдельном каталоге, нет конфликта .mvk_frame_marks_inbox. Неизвестная частота провода допустима в RAW rejected packet, но не разрешает запись source ring.

## Доказательства по SHA
- Prefix workflow [#45376321458](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45376321458): 3/3 SUCCESS (Go Linux, Go Windows, Core). Реальные Go synthetic fixtures TestSourceLocalTachCoreFixture и TestSourceTachByteWindowCoreFixture PASS, 50 focused Python PASS; полный suite 2832 PASS/151 skip/30 subtests PASS. Сюда входит независимая проверка A03 local latch/VALUES, а не только искусственный Python provider.
- Main offline workflow [#45376321281](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45376321281): Linux 2827 PASS/156 skip/30 subtests PASS; Linux Go RX/export SUCCESS. На момент фиксации Windows Core/Qt, QPA, verified EXE ещё не завершены. Не присваивать 5/5 заранее.
- Static syntax/calibration workflow #45376330733 SUCCESS.
- Новые Go/Python тесты: два TACH, Byte pattern в том числе IEEE-NaN-looking word, точные данные/sha, 4 спектральных режима, cursor wrap/alias, подмена type/domain/sha, stale request, отказ FIR/Freeze. Qt тест добавлен, итог Windows GUI проверить отдельно.

## Осталось
A05: отдельный retained source config/storage на retry. Оригинал на новом TCP выполняет Stage0 latch после первого descriptor, включая Freeze, читая общую конфигурацию; per-socket forensic image в Go не должен выдавать stale PageStatus. Разделить source retained config и новый RAW/socket, проверить неполный PARAM и retry, не ослаблять multi-socket/fail-closed guards. Не переписывать A01/A03/A04 без доказанного расхождения. A06–A10 protective differences сохранять. Аппаратный SAME-RX, Win32/x87, ANSI и реальные timestamps/имена файлов, оригинальная numerical/pixel parity остаются отдельной приёмкой.
