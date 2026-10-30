# MVKView Compatible — текущий статус Stage111S (30.10.2026)

**Целевая архитектура:** автономная Windows Qt/PySide6 MVKView Compatible, папка mvk_compatible/. Исследовательская ветка research/stage111-mvkview-desktop-20261029. main и прежняя Web v0.3.40 заморожены.

**Последний программный SHA:** af036bdd1be4dfdf2481a416f73cc9759db355d4.

## Реализовано и проверяется

- Stage111R: подтверждён защищённый Windows EXE через verified-dist PE/SHA256/BUILD_INFO. На предыдущем handoff HEAD 569567d54d1177439d3aedef90fcf2702ce70423 CircleCI Linux #67, Windows Core/Qt #66, Windows EXE #68: SUCCESS. Скачанная пользователем копия/хеш отдельно НЕ проверены.
- Stage111S: приватно исследованы оригинальные _Unit128.pas, mvkform.dfm и mvkview.idp. Восстановлены полные таблицы source H(10) 25600…50 Гц, FFT(6) 262144…8192 отсчётов, dB Y(6) 150…10, физические делители Y(6) 1…100000. Местоположение и порядок Tag сверены с оригинальными адресами gvar_008D3428/3450/3468/3480.
- Core: исходные VCL H/V Position/PageSize/Max, H clamp, V shift, правильный x87 FSUBRP знак, модель ScrLeft/ScrBottom по режимам. График Qt H больше не использует фиктивный 0..1000 slider.
- Native Qt: у bSpecHScale выпадающее меню всех десяти настоящих source частот, main click выбирает следующий меньший пресет. Источник SHA таблиц/данных доказан, Qt↔оригинальный TCanvas/Font/DPI численная и пиксельная идентичность НЕ доказана.
- Source FFT (8192…262144) и V меню пока в core: нужны достаточная история BIN, runtime графическая регистрация и проверка единиц. Research FFT 1024/4096 не выдавать за оригинальные presets.
- CircleCI нового программного SHA: [Linux #75](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/75) SUCCESS, [Windows Core+Qt #76](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/76) SUCCESS; [Windows verified-dist EXE #77](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/77) ещё выполняется. Не выдавать PENDING за SUCCESS.
- AUX4700/VALUES единственный штатный приборный DSP источник; нет подключения к реальному прибору.

## Открыто

Оригинальные runtime Canvas.Font/TextWidth/TextHeight/DPI/PixelRect, аутентичные CursorString/Delphi RTL/FormatFloat/x87, оригинальный FFT/GetSpectrum/GetNarrowbandValue/FRange на том же BIN/окне, полный UX трёх вкладок. Скачанный EXE и его SHA256SUMS ещё не сверены независимо, даже если CI job SUCCESS.

## Продолжение Stage111T

[Stage111S технический отчёт](STAGE111S_SOURCE_SPECTRUM_SCROLLBARS_RU.md), [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md), [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md), [START_NEW_CHAT](../../START_NEW_CHAT_RU.md).

Довести CI Linux/Windows Qt/EXE для указанного программного SHA; выполнить вертикальное шести-пунктное меню и шесть source NFFT с проверкой реальной истории архива, затем приватная регистрация оригинального TCanvas, сравнение FFT/x87. Не изменять stable main и Web v0.3.40, не подключать МВК без разрешения; никакие оригинальные PAS/DFM/IDP/production BIN/PCAPNG в GitHub не передавать.
