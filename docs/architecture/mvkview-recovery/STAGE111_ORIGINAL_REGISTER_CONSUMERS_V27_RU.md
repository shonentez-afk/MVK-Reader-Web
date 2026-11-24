# Atlas v27 — оригинальные register access, PARAM, VALUES/TABLE и Status

24.11.2026. Только исследование оригинальной MVKView. Stage111/main/research/fix/PR #14 не изменялись. Приборные команды не отправлялись. Приватные исходники, адресные таблицы и HTML не публикуются.

## Результаты

133/133 SHA исходных файлов, IDP SHA и SQLite quick_check проверены повторно. Сохранены исходный v15 побайтно, архивный v21, все 641 ID и все прежние реестры/маршруты. Добавлены 15 карточек, 43 направленных отношения, 270 уникальных Pascal-опор, 6 маршрутов. Overlay v22–v27: 99 карточек, 236 отношений, 36 маршрутов, 20 прежних VMT строк.

- Реальный read/write dispatch: 32 позиции таблицы символов RAW и 30 допустимых индексов typed dispatch; повторяющиеся символы при RAW search выбирают первое совпадение. Восстановлены 1818 access-footprint records (initial binding, guarded method paths). GetDword/GetFloat используют DWORD alignment; GetValueText отдельно nil/descriptor/type/Advanced. GetValueWithFmt форматирует raw cell. Advanced InputValue при прохождении protection/type/pointer пишет целый DWORD, не bit RMW. RAW проверяет четность и начальный адрес, а не конец типизированного диапазона. 21 условное extra-byte чтение строк при отсутствии NUL в ширине; 10 могут читать начало следующего дескриптора того же списка, не выводят этот байт. Не заявлять runtime дефект.
- 3267 уникальных descriptor/consumer пар: VALUES_ROW 596; VALUES_HEADER_METADATA 596 (0 register bytes); TABLE 252; STATUS_SYSTEM 15; STATUS_ALARM 192; STATUS_ALL 636 (union режимов); STATUS_CHANNEL 636; STATUS_REGISTER_BAR 344. Это potential slots, не одновременная трасса. Header и row используют одинаковую последовательность и latched masks. TABLE текущие channel flags, ResultADC + первый BAND + TACH, не SPEC и не values masks. Status register bar — не FFT из хранилища. Все 3 BAND выбранного ADC доступны в его таблице.
- PARAM: count nonzero/even, range bound, Task0/2 и Freeze gate; запись блока в backing image, затем 14 watched DWORD addresses (отдельны от 15 StatusCellList descriptors), gate по попаданию только начального слова. Accepted Task2 VALUES trigger: optional writer, затем reset двух TACH impulse latch даже без ValuesFile. При исключении writer reset не гарантирован. Не утверждать full-word freshness или snapshot atomicity.
- First-response Stage0→1: восемь direct raw ADC range reads вне descriptor catalog, Units via descriptor lookup; publish Storage range/units. Нулевой range заменяется на 1; TACH range=1 и units empty. Не перекачивать этот metadata route как per-PARAM refresh.
- Повторная типизация 231 исходного generic ID: 18 normal factory AddrLimit before Add, 2 rebind base, 2 factory Data overwrite только на известном config refresh route, 24 guarded value access, 19 localization branch, 5 address metadata, 1 raw start limit, 123 no-match retained, 4 explicit offset bypass, 33 indirect open. Rebind не равен изменению значения указателя. 123 не глобальные исключения; это не 231 доказанная runtime def-use. Семь GetRawSignal и background producer открыты.

## QA и приватная передача

266/266 structural/Chromium targeted checks PASS, 0 JS errors, node --check PASS. Проверены все 36 маршрутов, исторические реестры и новая фильтрация, 596 row/header mask order. Browser page.set_content; file:// попытка заблокирована политикой. ZIP CRC OK, 281 entries, 133 source files. Приватный пакет MVK_ALIAS_V27_PRIVATE_HANDOFF.zip и полный HTML сохраняют исходный трехпанельный интерфейс. Не публиковать их в GitHub. Не аттестованы реальный EXE, физический прибор, x87/ANSI/locale parity.

## Продолжение

Крупным проходом: исходные 15 полей PageAdc/PageSpectrum отдельно от Status register chart; formulas/format/units; TX/queue, metadata Range/Units и reconnect; динамические SetAddr/GetDwordRaw/GetRawSignal, Background producer, OnTerminate/DoTerminate, exception cleanup и remaining conditional routes. Сохранять существующий полный Atlas, не исправлять Stage111 в этом чате. Передавать рабочие расхождения основному чату только в документации.
