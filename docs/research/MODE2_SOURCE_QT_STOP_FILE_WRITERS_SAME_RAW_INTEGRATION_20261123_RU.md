# Тест полного штатного Stop из Qt, без прибора (23.11.2026)

После найденных операторских скриншотов спектра и восстановления меню, следующая незакрытая сквозная часть — WriteValues/WriteData/Stop на **том же самом** RAW.

Добавлен Go-тест source_original_qt_stop_file_full_cycle_test.go: одна реальная loopback TCP-сессия и синтетические исходно-подобные кадры; подготовка двух исходных frame-mark запросов записи; единственный подтверждённый SetRate(65536) на том же сокете (36 байт); 6 ADC1 пакетов и PARAM 0x3100 между ними. Отдельный имитатор Qt записывает штатный файл `.mvk_stop_requested`, который обрабатывает **действующий** watchStopRequest. Проверки: реально остановлен приём через Context, raw SHA совпадает с ожидаемыми байтами, TCP в единственном сегменте, WriteData не меняет полученные ADC Single, WriteValues получает только параметр 0x3100, оба writer-а закрыты с Outcome=CLOSED_BY_SOURCE_THREAD, имеются audit/packet-gate/frame mark/segment receipts; никакого дополнительного TX при Stop.

Оригинальные Projects.7z/_Unit125.pas, mvkview.idp, mvk_idr(1).sqlite прочитаны локально, исходный конец Execute 008089A3..008089BF: CloseFiles(force=1), затем Stage=0. Никаких приватных оригиналов или пользовательских RAW в GitHub.

Важно: CI на синтетическом loopback **не аттестует** Win32 оригинал или реальный МВК01. Полный Win32 Hann/FFT/Power/Y x87 и оригинальные WriteData/WriteValues байты на аутентичном **одинаковом** приборном RX всё ещё не подтверждены. Единственное назначение теста — закрыть путь взаимодействия кнопки Stop с реальным модулем Go RX и двумя writer-ами, вместо только программного ctx.cancel() в старом E2E.

## Дополнение после запуска CI и исправления исходного Go-багa

Реальный новый тест `TestOriginalQtStopFileEndsSameSocketAndClosesWriteDataWriteValues` первоначально выявил регрессию: даже при явном Stop-файле `watchStopRequest` сеть могла вернуть TCP EOF до следующей проверки ctx.Err, что ошибочно маркировало причину source-socket close как `REMOTE_DISCONNECTED`, отчего оба output writer-а закрывались аварийным Outcome при фактическом нажатии оператором Stop. Исправление продакшен-кода `main.go::liveCaptureAddressOnNIC`: после уже принятого RX, перед классификацией EOF в read-error branch проверяется ctx.Err и возвращается `STOPPED_BY_USER`; raw bytes, TCP commands и read loop не меняются. Коммит `f3b90ee08cf5bce16febdd11f21730b7962735b5`. Полный Linux Go receive test PASS на Actions #45104773877. Отдельный Linux Core PASS, Windows native QPA PASS; Windows Core/Qt в процессе на момент подготовки этого handoff, окончательный статус смотреть в Actions.

Предыдущие Windows Qt тесты после восстановления русских единиц Y ошибочно ожидали строки `0.01 усл.` вместо оригинальной номинальной `0,01 м/с²`; с актуальным отображением чисел и локалью исправлены только эти тесты в `8609d4c7b1e64f3216699940dba7ffba5c80eec8`. Не откатывать пользовательские screenshot-backed режимы/подписи.

По отчёту `STAGE111Z30C_TAG0_ORIGINAL_LOG_FULL_Y_131072_BITWISE_FOUR_MODES_RU.md` исходные операторские x32dbg захваты Tag0..3 ранее дали по 131072/131072 совпавших Y Single на КАЖДОМ захвате. Исходные позиции Tag2 и Tag3 различались. Поэтому отдельная численная паритетность `GetSpectrum` на известных захватах не равна доказанному сквозному исходному same-window/same-RAW измерению. Строгий comparator дополнен явными Tag0..3 Y и Tag2/3 Power с hard fail при missing/duplicate modes. Доказательство владельца/подлинности оригинальной Win32 сессии по одним файлам не формируется.

Никаких пользовательских оригиналов, реальных измерений, прошивок, raw скриншотов и промышленного TCP не использовано в автоматизированной синтетической проверке.

## Дополнение: Windows Qt legacy smoke

> **23.11.2026 — Windows Qt отдельный smoke: ранее 2 устаревших ожидания, исправлены.** Run #45104773877: 2898 Windows Core PASS / 15 skip + 57 Qt PASS, две старые проверки теста `test_desktop_qt.py` сравнивали `Сохранить CSV` вместо настоящей исходной `Сохранить` и 8 FFT research пунктов вместо 6 исходных `Гц/лин`. Удалены только ложные ожидания, источник GUI не откатывался, коммит `a3b7676beab0371daaed85733cd086360ae9846c`. Новый Windows Core/Qt + EXE запуск #45105519080 проверять до SUCCESS; старые успешные Linux/Go не доказывают этот новый SHA. Main не менялся.


## Дополнение: корректный checked status research FFT

> **23.11.2026 — Windows original-research FFT edge-case Qt test fixed.** `a3b7676` исправил старые ожидания “Сохранить CSV” и 8 original FFT пунктов. Следующий #45105519080 дал Windows Core 2898 PASS, native Qt 58 PASS/1 FAIL: в исследовательском `spec_n=1024/4096` исходное шестиэлементное `bSpecLines` меню имеет ноль checked по определению; предыдущее тестовое ожидание строго одного checked было ошибочным. Исправлено в `e657c960256a2953aa0a872739f59e9015acceb0`: 1 checked для original NFFT 8192..262144, 0 checked для research N1024/4096. Это только тест, без отката UI или изменений DSP. Полный CI и Windows EXE проверять по `e657c960`; любые прежние CI failure тестовых ожиданий не выдавать за аппаратную несовместимость. [Оригинальные меню](docs/research/MODE2_USER_ORIGINAL_SPECTRUM_SCREENSHOT_MENU_AUDIT_20261123_RU.md).


## Финальный подтверждённый CI / EXE

> **23.11.2026 — ИТОГ ПАКЕТА: 5/5 CI SUCCESS + EXE ГОТОВ.** Полный GitHub Actions [#45106110803](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45106110803) для последнего КОДОВОГО SHA `e657c960256a2953aa0a872739f59e9015acceb0`: Linux Core, Linux Go Original TMVKThread RX / WriteData / WriteValues / Qt Stop-file, Windows Core/Qt, Windows native DPI/QPA и Windows autonomous PyInstaller EXE **ВСЕ SUCCESS**. Windows EXE artifact `MVKViewCompatible_Stage111_Windows_Preview` id 14788520011, 69 528 924 B: [скачать](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45106110803/artifacts/14788520011). Контрольные снимки исходного UI 100%/150% artifact id 14787339513. Никаких физических МВК01, подлинной единой Win32 RX→four mode→WriteData/WriteValues→Stop сессии и x87-bytes полного исходного процесса в CI нет. Программные synthetic тесты и EXE успешно приняты; аппаратное 1:1 **ОТКРЫТО**. Не менять main/приватные исходники; не требовать повторно материалы 7z+IDP+SQLite/старые PNG. Новому чату прочитать этот блок и подробный [Stop-отчёт](docs/research/MODE2_SOURCE_QT_STOP_FILE_WRITERS_SAME_RAW_INTEGRATION_20261123_RU.md).

