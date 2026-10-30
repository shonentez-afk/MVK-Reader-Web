# MVKView Compatible — текущий статус Stage111X (30.10.2026)

**Единственная рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. **Автономная архитектура Windows Qt/PySide6** в `mvk_compatible/`; стабильный `main` и Web v0.3.40 не изменять.

**Последний программный SHA:** `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`.

## Что подтверждено

- Stage111W программный SHA `080dcddbb65a8d199ea444ac9ae8d3676ac5e57f`: [Linux #93](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/93), [Windows Qt #94](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/94), [Windows verified-dist EXE #95](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/95) — все SUCCESS. Скачанная пользователем копия EXE отдельно по SHA256 не сверялась.
- В Stage111X приватно исследована бинарная карта `mvkview.idp`: 3 прямых `Set8087CW`, 4 прямых `Get8087CW`, 5 прямых `@FpuInit`. По адресам `0041BD84` и `0041BDDA` восстанавливается CW перед внешними вызовами; `00448296` изменяет только биты масок, сохраняя PC/RC.
- В оригинальном парсере чисел `0042EBC1` сохраняется прежнее CW, `0042EBC8` используется локальное **`0x133F`**, `0042EC68` восстанавливает CW. Прежнее исходное значение `0x1332` остаётся подтверждённым **статическим**, не измеренным live-runtime.
- Добавлен `private_x87_callsite_audit.py` с синтетическими тестами, не публикующий оригинальные байты. Прямые callsites по адресам и opcode сверены непосредственно в частном оригинале. **Полная проверка косвенных вызовов / всех путей FLDCW НЕ выполнена.**
- Добавлен `private_x87_runtime_reference_compare.py`: приватный протокол `MVKVIEW_RUNTIME_X87_GOLDEN_V1` для будущего FRange/GraphDefaultVScale/CW из одной реальной original Delphi сессии. Отчёт содержит только агрегатные ошибки в ULP и распределения FPU PC/RC, без самих оригинальных значений.
- Тесты используют только искусственные IDR/числа, не исходный защищённый материал. Доступный локальный набор — **100 PASS**. [Linux Core #97](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/97) SUCCESS; [Windows Core+Qt #96](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/96) SUCCESS, [Windows Preview EXE #98](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/98) PENDING.
- Реальный прибор не подключался; исходные PAS/DFM/IDP/BIN/PCAPNG/измерения в GitHub не загружались.

## Что открыто — Stage111Y

1. Довести CI для SHA `0d1c36f431e23b0cf5eb58df839d92abbb1467e1` до Linux, Windows Qt и Windows verified-dist EXE, отдельно скачать EXE и сверить SHA256SUMS.
2. Без прибора снять в **работающей оригинальной Delphi MVKView** значения `Get8087CW`, `TMvkChannelStorage.FRange` и `GraphDefaultVScale` для одного и того же канала/окна/режима. Сейчас доступен только статический `mvkview.idp`, а не измерение активного оригинального процесса; настоящие golden данные не выдумывать.
3. Сопоставить оригинальные битовые наблюдения с x87 `FYL2X`/Power/`@TRUNC`, исследовать `FormatFloat` и `GetSpectrum/GetNarrowbandValue/FRange/FFT`; верную исходную вертикальную шкалу применять к Qt только после численного подтверждения.
4. Продолжить TPaintBox.Canvas.Font/DPI/PixelRect/CursorString и финальную приёмку автономного Windows приложения; не возвращаться к Web и не менять `main`.

[Stage111X отчёт](STAGE111X_ORIGINAL_X87_CALLSITES_AND_GOLDEN_RU.md) · [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [START_NEW_CHAT](../../START_NEW_CHAT_RU.md).

**Не объявлять source-static аудитор доказательством runtime parity.**
