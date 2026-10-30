> **STAGE111R FINAL SOURCE — безопасные артефакты CircleCI (30.10.2026).** Финальный программный SHA: `8c9f0d29895a8a2ae68ad09c42e678cfffe01bee`; исходные модули и 22 новых локальных synthetic PASS добавлены коммитом `aa8e3b87671034636a4a63dc6486d0432c3b72c3`. Из-за того, что CircleCI `store_artifacts` выполняется даже при неуспешном тесте, Windows Preview проверяет PE/SHA/BUILD_INFO **дважды**, а публикуемая `verified-dist` создаётся атомарным rename только после успешной сверки скопированных байтов (новый `BUILD_VERIFICATION.json`). [Linux #64](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/64) SUCCESS; [Windows Core+Qt #63](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/63) результат проверить; Preview EXE начинается после обоих успешных jobs, скачанный EXE/SHA дополнительно проверить локально. [Полный Stage111R](STAGE111R_QT_GDI_REGISTRATION_AND_EXE_INTEGRITY_RU.md). По Qt↔Delphi TPaintBox создан только диагностический affine-кандидат, runtime оригинальный Canvas/DPI/FFT/x87 НЕ аттестованы. **Следующий Stage111S.** `main`/v0.3.40 не менять, прибор без разрешения не использовать, исходные закрытые PAS/DFM/IDP/BIN/PCAPNG в GitHub не передавать.

# MVKView Compatible — актуальный статус Stage111R (30.10.2026)

**Единственная целевая архитектура:** автономный Windows Qt/PySide6 MVKView Compatible (без сервера и Web). Ветка: `research/stage111-mvkview-desktop-20261029`.  
**Точный SHA исходников Stage111R:** `aa8e3b87671034636a4a63dc6486d0432c3b72c3`.

## Уже подтверждено

- Последний Stage111Q HEAD `6b29e9169d31004c52784cc78b6590ba161a19ea`: Linux Core [#58](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/58) SUCCESS, Windows Core/Qt [#57](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/57) SUCCESS, Windows EXE [#59](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/59) SUCCESS.
- Stage111R: новый fail-closed контроль реального PE EXE/SHA256SUMS/BUILD_INFO и commit/branch перед публикацией CircleCI Artifacts. Публикуется `BUILD_VERIFICATION.json`. 9 локальных synthetic integrity PASS.
- Stage111R: исследовательская аффинная регистрация Qt scene ↔ Source-derived Delphi TPaintBox PixelRect; независимые landmark errors, DPR отделён от оригинального Canvas; 13 локальных synthetic bridge PASS. Новый диагностический GUI тест.
- Stage111R code CI: [Linux #61](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/61) SUCCESS, [Windows Core+Qt #60](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/60) SUCCESS. [Windows EXE #62](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/62) на момент подготовки требовал подтверждения нового integrity шага.
- Штатные приборные DSP-показатели только AUX4700/VALUES, без подмены локальным FFT; не было доступа к прибору.

## Не доказано / блокеры

Фактический runtime Font/DPI и PixelRect оригинальной работающей Delphi MVKView, истинная регистрация original↔Qt, 1/2 series CursorString/Delphi RTL/x87, GetSpectrum/GetNarrowbandValue/FRange, оригинальный FFT и UX всех трёх вкладок. Synthetic/CI SUCCESS не равен оригинальному численному/пиксельному паритету. **Скачанный** Preview EXE/SHA256SUMS отдельно по байтам не сверялся; build receipt проверяет только сам процесс сборки. Приватные PAS/DFM/IDP/BIN/PCAPNG/коэффициенты в GitHub не помещены.

## Точка продолжения Stage111S

[Stage111R отчёт](STAGE111R_QT_GDI_REGISTRATION_AND_EXE_INTEGRITY_RU.md) · [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [новый чат](../../START_NEW_CHAT_RU.md).

Начать с окончательной проверки EXE CircleCI #62, `BUILD_VERIFICATION.json` и скачанного SHA256; приватно измерить оригинальные Canvas.Font/TextExtent/PixelRect и одинаковые точки по нескольким DPI. Только после независимых измерений изменять реальный Qt курсор. Продолжить x87/FormatFloat/FFT, не трогая `main`, Web v0.3.40 и прибор без отдельного разрешения.
