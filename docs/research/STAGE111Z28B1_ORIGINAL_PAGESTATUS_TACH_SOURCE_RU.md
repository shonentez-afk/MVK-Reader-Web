# Stage111Z.28B1 — карта оригинальной PageStatus, TACH, контрольных ячеек

Дата 02.11.2026. Ветка research/stage111-mvkview-desktop-20261029.
ПРОТЕСТИРОВАННЫЙ source commit: 00b328d010f516394098cf99769ab802aaf7ab83
Статус: SOURCE STATIC AUDIT + CODE + OFFLINE CI + WINDOWS ONE-FILE VERIFIED. REAL ORIGINAL RUNTIME/PX/TACH RPM OPEN.

## 1. Оригинальная статическая проверка (без публикации оригиналов)

Предоставленный пользователем Projects.7z прочитан локально, без сетевых запросов. Проверены оригинальные _Unit125.pas, _Unit128.pas и mvkform.dfm. 27/27 заранее выбранных точных адресных/DFM признаков совпали. Для этой проверки не требуется и не использовалось аппаратное соединение. Временные копии оригинала удалены; архив Projects.7z и mvkview.idp сохранены без изменений. Приватные PAS/DFM/IDP/RAW/BIN/PCAP в GitHub НЕ передавались.

Source _Unit128:0x008475F5 — GetTabIndex оригинального tcStatus и переключение 15 логических режимов:
- индекс 0: tabStatus / StatusCellList;
- индекс 1: tabAlarmResult / ResultAlarmCellList (8 колонок АЦП);
- индексы 2–4: tabAllResult / три source result bank списка по всем 8 АЦП (RMS/PIK/PIK-PIK сопоставлены с уже существующими AUX-кандидатами, но оригинальное порядок/caption parity НЕ принят);
- индексы 5–12: tabResult и chResult по одному АЦП; 0x00847B2D — ровно 0x2B=43 исходных полосы;
- индексы 13–14: ResultTachCellList для двух TACH-банков;
- источники диспетчеризации: _Unit128:0084761A, 008476B7, 0084779C, 008479FD, 00847D58; TACH конструктор циклом 2, ADC конструктор циклом 8.

Source _Unit125:008053B8, конструктор ResultTachCellList: register base 0x3000 + tachIndex*0x100. Точное имя локализационного ключа, слово, тип и исходная подпись:

| Ключ оригинала | Смещение слова | Тип | Подпись исходника | Значение в Stage28A TIMELINE |
|---|---:|---|---|---|
| ResultTacho | +0x00 | Float32 | Гц | Есть, сырые Float32 биты |
| ResultTachoDelta | +0x02 | Float32 | Гц | Есть, сырые Float32 биты |
| ResultTachoError | +0x04 | UInt32 | нет | Есть, raw DWORD |
| ResultTachoTimestamp | +0x06 | UInt32 | нет | Есть, raw DWORD |
| ResultTachoCurrent | +0x08 | UInt32 | нет | Есть, raw DWORD |
| ResultTachoImpulse | +0xFE | UInt32 | нет | НЕТ в текущем 76B VALUES tick |

Буквы Гц в исходном IDR подтверждают лишь оригинальную подпись Float32 ячеек, но не численное/аппаратное соответствие частоты и не RPM. Исходный 76B VALUES tick содержит только по 10 слов на TACH, поэтому +0xFE НЕ импортируется из старого initial snapshot, который может быть устаревшим.

Source _Unit125:00805178 и _Unit128:008476B7: для восьми ADC по 8 контрольных слотов, по 3 строки на слот: AlarmValue 0x130+8*j (Float32); AlarmState 0x132+8*j (raw DWORD + преобразователь); AlarmAlert ТО ЖЕ 0x132+8*j (другой преобразователь, не отдельный регистр). Различные state/alert text options не дают права приписывать отсутствие/наличие аварии без real-word+live конфигурации. Получаемые AUX4700 блоки содержат лишь 0x122 words/ADC: адресов +0x130 и +0x132 нет. Контролируемый номер параметра и пороги берутся из отдельного конфигурационного блока (Stage63–65), оригинальная реальная настройка этой сессии отсутствует.

## 2. Реализация Stage111Z28B1 в коде

- mvk_compatible/core/original_pagestatus_source.py — чистая offline модель исходных 15 режимов, source-backed mapping TACH1/TACH2, 8×3×8 контрольных ячеек и 43 полос на конкретный АЦП. В каждом численном поле потребляет только уже аутентифицированные AUX/VALUES и TIMELINE Stage28A; никакого второго DSP/FFT, double FRange или RPM.
- В старых проверенных ZIP и при новой LIVE записи отсутствующие регистры помечаются —. Контрольные зоны всегда UNKNOWN до появления привязанных реальных статусных слов; никакого фальшивого НОРМА/АВАРИЯ и автоматического выравнивания архивов.
- desktop/main_window.py — новая внутренняя страница Задачи → PageStatus · оригинальный порядок. Исходные 15 переключений tcStatus отображены компактным селектором, таблицы доступны для всех 8 ADC и отдельно TACH. Для выбранного ADC показывается существующая подтверждённая 43-полосная диаграмма, явно не pixel-exact chart chResult.
- Три главные вкладки приложения, инструменты Native R6.1, исходный RAW/BIN/TSXML/19-file timeline и весь оригинальный FFT/FRANGE goldens не изменены. Численная проверка оригинальной PageStatus по одному и тому же реальному tic ещё не выполнялась.

## 3. Автоматическая проверка

[GitHub Actions #41403349626](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41403349626) — все три задания SUCCESS.
- Linux Offline Core 1015 passed, 3 skipped, 30 subtests passed;
- Windows Offline Core 1016 passed, 2 skipped, 30 subtests passed;
- Windows Qt 48 passed; проверены 15 режимов, 24×8 недоступных alarm полей, 24×8 AUX RMS/P/PP, 43 bands, 6 TACH полей, no stale values after archive/LIVE.
- Native Go test/vet/Windows build PASS; PyInstaller one-file Qt+Go, PE header, BUILD_INFO и SHA256 PASS.
- [Windows artifact id 13121893952](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41403349626/artifacts/13121893952), ZIP 68 526 358 bytes, expired=false на дату проверки.
- Windows EXE SHA256: 05eb115f235ba224970f895e3dcbff8bcab96ab56636c72de2a47ed4876a66cc
- GitHub artifact ZIP SHA256: 6eafd2a0257e70b6185e3477b5a1518c26e87d289ef3fbb965190f7c51ce6e28
- Exact tested source SHA: 00b328d010f516394098cf99769ab802aaf7ab83. Последующие docs-only коммиты не создают нового проверенного EXE.

## 4. Что по-прежнему открыто

Stage28B1 SOURCE/STRUCTURE+CI CLOSED, но Stage28B2 REAL STATUS/CONTROL PARITY OPEN:
1. Получить реальные конфигурационные номера контролируемых параметров/пороги и per-tick source value/state/alert 0x130..; нельзя брать их из старого initial snapshot и выдавать за текущие.
2. Восстановить реальный original TMvkAdvancedCell mapping 11 zone options / 3 alert options, контроль времени и сбросов, не угадывая семантику по числам.
3. Измерить оригинальные TACH регистры и исходные GUI-подписи в одном проверенном сеансе; Hz → RPM только при подтверждённом числе импульсов/оборот, original runtime и метрологии. +0xFE требует отдельного достоверного пути.
4. Оригинальный PageStatus pixel parity и layout splitters/chart/fonts/DPI 1024x704/125%; текущий компактный Qt selector — исследовательский UX, НЕ 1:1 визуальный порт оригинала.
5. Stage27B original same-run BIN comparison и реальный аппаратный field-test нового Qt/Go — OPEN.

После source/status gate можно переходить к самостоятельному Stage29 original GetSignal/ring/envelope, затем Stage30 full-spectrum, Stage31 UI/UX, Stage32 long-run. Не возвращаться к Stage52 FRange, Stage108/109 Native, Stage26B live, Stage27A compare, Stage111Z8/Z10 FFT. Стабильные main и Web не менять.

[Общий план восстановления](STAGE111Z25_FULL_RECOVERY_MASTER_PLAN_RU.md).