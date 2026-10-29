# MVKView Compatible — текущий статус Stage111O (2026-10-29)

**Основной продукт:** автономная Windows Qt MVKView Compatible; исходники `mvk_compatible/`, ветка `research/stage111-mvkview-desktop-20261029`. Web v0.3.40/main заморожены. Штатный приборный DSP — **только AUX4700/VALUES**.

## Проверенные программные SHA / CI

- Stage111N `11f022925a407495d7bf4b3b7dcb94b21afe7ced`: [Linux #15](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/15) SUCCESS, [Windows Core/Qt #16](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/16) SUCCESS, [Windows EXE #17](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/17) SUCCESS.
- Stage111O `aa3a0dd0a11e9821dfbfd350f16dfbb8bcc19fde`: [Linux #30](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/30) SUCCESS, [Windows Core/Qt #31](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/31) SUCCESS, [Windows EXE #32](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/32) SUCCESS.

Оба этапа имеют подтверждённые synthetic/offline job statuses; точные счётчики pytest и скачанный EXE SHA отдельно не аттестованы. Это НЕ численная или пиксельная приёмка оригинальной Delphi MVKView.

## Stage111O — реализовано

Подтверждено из приватного оригинала: курсор Time/Spectrum обновляется **при движении мыши по X**, повторный целый X пропускается, Y не участвует в UpdateCursor, исходная отрисовка использует clGreen/pmXor. В Qt работают оба MouseMove, Time hover кеширует окно GetSignal для O(1) выбора отсчётов без повторного чтения ZIP. Qt/TCanvas/GDI пиксели пока не тождественны.

## Нерешённое и следующий Stage111P

Нужны оригинальные Canvas/TextWidth/TextHeight/DPI и 1/2-row CursorString/DrawnX/Y на идентичном BIN, Delphi x87/RTL FormatFloat, FFT/GetSpectrum/Narrowband/FRange, полный интерфейс всех трёх вкладок. Получить фактический SHA Windows EXE; продолжить GDI XOR и приватную сверку Original. Без Live/приборных команд, без публикации оригинальных PAS/DFM/IDP/BIN/PCAPNG.

[Технический Stage111O](STAGE111O_ORIGINAL_MOUSEMOVE_CURSOR_RU.md) · [Stage111N QA](STAGE111N_CIRCLECI_ACCEPTANCE_RU.md) · [Compatibility Matrix](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [Handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md).
