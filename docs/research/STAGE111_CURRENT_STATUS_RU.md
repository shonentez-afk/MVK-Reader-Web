# MVKView Compatible — актуальный статус Stage111Q (30.10.2026)

**Рабочая ветка:** research/stage111-mvkview-desktop-20261029

**Последний программный SHA:** d8c44318a09d328ecfd14a3a92f1bb987209999b

**Продукт:** только автономная Windows MVKView Compatible, Qt/PySide6; stable main и Web v0.3.40 не изменять.

## Выполнено

- Stage111P: исходная логика GDI XOR 1/2-series и попиксельное synthetic Win32 сравнение; Linux/Windows/EXE CircleCI SUCCESS.
- Stage111Q: из оригинального Delphi подтверждён динамический Margin обоих PaintBox = min(W div 53,H div 30), минимум 10, исходный PixelRect и относительное расположение полос прокрутки. Исправлена Qt Canvas-диагностика.
- Доступный приватно mvkform.dfm подтвердил **дизайн формы**: Tahoma, Font.Height=-13, PixelsPerInch=96, pbAdc 791×740, pbSpectrum 767×716. Это НЕ гарантирует такой же реальный TCanvas при запуске, DPI/scaling и resize.
- Новый производный DFM профиль, синтетический PaintBox layout и GDI font probe через Win32 GetTextExtentPoint32W; Qt-диалог показывает DFM проектный Font отдельно от Qt текущего.
- Локально 38 синтетических тестов новых core-модулей PASS. Предыдущий код 1baf980e611f55d38618b4dc170e8662089eaf62: CircleCI Linux #49 SUCCESS, Windows Core/Qt #48 SUCCESS, Preview EXE #50 ещё не принят. Текущий код d8c44318a09d328ecfd14a3a92f1bb987209999b: [Linux #55](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/55) SUCCESS; [Windows Core/Qt #54](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/54) PENDING на момент записи; EXE/скачанный SHA ещё не подтверждены.
- AUX4700/VALUES остаются единственным штатным приборным DSP источником; реальный прибор не подключался.

## Что НЕ доказано

Фактический оригинальный TPaintBox.Font.Name/Height/Style на нескольких DPI, живые Canvas.TextWidth/TextHeight и PixelRect, Qt↔Delphi регистрация пикселей, оригинальная GDI XOR-картинка, CursorString/FormatFloat/x87, FFT/FRange/GetSpectrum/Narrowband численная точность и полное поведение трёх вкладок. Успех synthetic CI не равен выпуску версии 1.0. EXE и SHA256SUMS скачать и проверить отдельно.

## Продолжение

[Отчёт Stage111Q](STAGE111Q_PAINTBOX_FONT_DPI_RU.md) · [Матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [Handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [START_NEW_CHAT](../../START_NEW_CHAT_RU.md).

Следующий Stage111R: подтверждение полного CircleCI на точном исходном SHA и EXE/SHA, приватная оригинальная Canvas.Font/DPI/X/Y/TextWidth/Height сверка, затем RTL/x87/FFT/двухрядный курсор. Не передавать оригинальные PAS/DFM/IDP/BIN/PCAPNG в GitHub или CircleCI, main/v0.3.40 оставить без изменений.
