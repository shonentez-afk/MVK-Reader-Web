# Atlas v26 — дескрипторы, receiver и конфигурация оригинала

24.11.2026. Только восстановление оригинальной MVKView. Stage111/main/research/fix/PR #14 не изменялись, приборные команды не отправлялись. Приватные исходники, адреса и HTML не публикуются.

## Результат
133/133 SHA исходных файлов, IDP SHA и SQLite quick_check проверены. Сохранены полный v15, исторический v21, все 641 ID, 69 карточек и 25 маршрутов v25. Добавлены 15 карточек, 38 направленных отношений, 201 уникальная адресная опора, 5 маршрутов. Суммарный overlay v22–v26: 84 карточки, 193 отношения, 30 маршрутов, 20 прежних VMT строк.

- Раскрыты 74 прямых фабричных Add callsites, восемь перегрузок и пять циклов на 71 объекте: 1818 дескрипторов. Типы/размеры сверены по сохраненному машинному образу. Из 90 пересечений заявленных интервалов все внутри одного списка: разные биты, общая читаемая ячейка; ноль между разными объектами при исходной фабричной привязке. 268 номинальных пересечений v25 сохранены отдельно. Это интервалы дескрипторов, не полный footprint runtime accesses.
- 33 проверенных места происхождения receiver. Повторно классифицированы все 231 прежний generic ID: 71 compatible context guarded, 123 no match in inspected contexts, 4 explicit address bypasses LastAddr on factory path, 33 reader context open. Ни 123 глобальных исключений, ни 71 подтвержденных def-use не заявляется. Оставшиеся 33 относятся к SetAddr (22) и GetDwordRaw (11): extended RTTI подтверждена, classic method table на проверенной цепочке пуста, ограниченный поиск прямых E8/E9 не дал совпадений. Косвенный producer открыт. Семь GetRawSignal и background producer остаются открытыми.
- Загрузка конфигурации: ConfigIP receiver, recursive include, offset, raw write по адресу в backing image без lookup по индексу дескриптора. InputValue отдельно проверяет индекс, тип и защиту. Save использует режимы IP/Calib/ADC/TACH/Alarm, пишет смещение, адрес, тип и значение. Locale, close и line exception; rollback и ошибки вторичной очистки не аттестованы. Редактор публикует выбранный CellList, ADC helper согласует октавные пары.
- Калибровка: отдельный объект, публикация, флаги и Start/Terminate. TACH read и ADC coefficient generation — отдельные маршруты; причинная связь TACH→ADC coefficients не доказана. Cleanup Generator OutputOff/Free/nil, Switch Free/nil, ошибки выключения не доказывают физическое выключение.
- Сквозной граф разделяет form, measurement session, TCP epoch и параллельных consumers; конфигурационный режим показан отдельно.

## QA
196/196 structural/Chromium checks PASS, 0 JS errors, node --check PASS. page.set_content; file:// не аттестован. Приватный архив MVK_ALIAS_V26_PRIVATE_HANDOFF.zip содержит прежние версии, три первичных источника, все 133 извлеченных файла (PAS/DFM/DPR), полный HTML, CSV/JSON, скрипты и handoff. Оригинальный EXE и прибор не запускались.

## Далее
Фактические read/write footprints и reaching definitions для 71 compatible / 123 no-match contexts, format/bit masks/raw address length, PARAM/VALUES/TABLE/Status и rebind. Разрешение непрямых SetAddr/GetDwordRaw/GetRawSignal, background producer, OnTerminate и внешних callback. Калибровка ADC/TACH, outer cleanup и повторное измерение. Только восстановление оригинала в прежнем полном Atlas.
