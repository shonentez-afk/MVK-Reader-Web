# MVKView Compatible — текущий статус Stage 111P (30.10.2026)

**Ветка:** `research/stage111-mvkview-desktop-20261029`; **программный SHA:** `38a895fd797e300fbc967f7e97700828c4330106`. Единственная целевая архитектура — автономный Windows PySide6/Qt, `mvk_compatible/`. Стабильные `main` и Web v0.3.40 не редактируются.

## Работает и подтверждено

- Stage 111O: оба курсора обновляются движением X, GetSignal кеширован, предыдущий программный коммит `aa3a0dd0a11e9821dfbfd350f16dfbb8bcc19fde` получил Linux #30, Windows Core/Qt #31, Windows EXE #32 SUCCESS.
- Stage 111O документация HEAD `8c4d199c115168a31fe21248c33d328b35ddef3f`: CircleCI Linux #34, Windows+Qt #33, EXE #35 SUCCESS.
- Stage 111P: восстановлена точная **SOURCE-STRUCTURE** последовательность GDI clGreen/pmXor, erase X + до двух Y, LineTo endpoint exclusive, возврат pmCopy. Новый независимый RGB XOR raster candidate, локальная приватная screenshot-сверка и native Win32 GDI тест.
- Stage 111P локальная синтетическая проверка: 9 XOR и 3 приватного сравнителя PASS. CircleCI source SHA выше: [Linux #39](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/39) SUCCESS; [Windows Core/Qt #40](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/40) и Windows EXE проверить до приёмки.
- Оригинальный DSP AUX4700/VALUES только приборный; никаких производственных коэффициентов, приватных BIN/PCAPNG/PAS/DFM/IDP не публиковалось; прибор не использовался.

## Не завершено

Оригинальный TCanvas Font/DPI/PixelRect/GDI снимки, паритет оригинального CursorString/Delphi RTL/x87, получение реального FFT/FRange/GetSpectrum/Narrowband по совпадающему окну/алгоритму и полный интерфейс трёх вкладок. Натуральный Win32 GDI synthetic PASS (если получен) НЕ равен пиксельной приёмке оригинального окна. Скачанный EXE SHA256 ещё не проверен.

[Отчёт Stage111P](STAGE111P_GDI_XOR_RASTER_RU.md) · [Матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [Handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [Новый чат](../../START_NEW_CHAT_RU.md).

**Продолжение:** Stage 111Q — оригинальная pixel/DPI/screenshot-сверка, затем осторожная интеграция XOR в Qt, FormatFloat и численные DSP кандидаты. На реальный прибор не подключаться.
