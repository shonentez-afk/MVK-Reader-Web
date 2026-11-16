# Stage111Z31CN — оригинальный шрифт: нативная Windows Qt/GDI диагностика 100/150

**Дата:** 16 ноября 2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.
**ИСПОЛНЯЕМЫЙ CODE SHA:** `e7c5fb767c4bb1e8342cd6be5a990de1c407e05c`.
**GitHub Actions** [#43789638737](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43789638737) — **4/4 SUCCESS**.

## Что фактически сделано

Никаких изменений в FFT, FIR, GetSpectrum, FRange, original TQGrapher числах,
Go-приёмнике или состоянии Live устройства. Новый
`mvk_compatible/tests/test_stage111z31cn_native_qt_font.py` независимо
рисует цифры `0,1,2`, латинское `A`, русские `Б,Ж` в отдельном чистом
QImage QPainter и отдельном Win32 `TextOutW` на DFM Tahoma -13,
возвращает реальные попиксельные SHA, ink counts, bounds, а не полагается
на `QRawFont.supportsCharacter`. Все исходные файлы/шрифты приватны,
в репозиторий идут только синтетические чёрные символы на белом фоне.

В `.github/workflows/stage111-desktop-offline.yml` добавлен независимый
`windows-native-visual` job с **реальным `QT_QPA_PLATFORM=windows`**
при `QT_SCALE_FACTOR=1` и `1.5`, который также прогоняет настоящий
операторский сценарий `test_stage111z31cm_qt_source_operator_path.py`
на синтетическом BIN. Native job **2 PASS при 100%, 2 PASS при 150%**.
При этом обычная сборка остаётся безопасным независимым core/offscreen
pipeline: пакет оригинальной программы и прибор не подключались.

**Критический результат:** и Qt, и независимый GDI возвращают
**6 из 6 разных настоящих растров символов** на обеих платформах.
На 100% Qt ink counts `[50,31,36,41,48,76]`, GDI
`[52,31,36,46,48,79]`. На 150% Qt
`[47,24,36,44,48,69]`, GDI `[52,31,36,46,48,79]`.
В реальной native Windows QPA галерее кириллица и десятичные подписи осей
отображаются корректно, без прямоугольников. Прежние offscreen скриншоты
CM с квадратиками — **не нативный Windows-рендер**, НЕ доказательство
порчи шрифтов Tahoma в EXE. Не подменять Tahoma, не встраивать шрифты
и не модифицировать source TextOut для маскировки проблемы только CI.

## Точная CI-приёмка

- Linux Core: **1954 PASS /109 SKIP**, 1 warning, 30 subtests.
- Windows Core: **2128 PASS /7 SKIP**, 1 warning, 30 subtests.
- Qt smoke (offscreen Windows): **49 PASS**.
- Qt offscreen DPI100: **2 PASS** (CM operator+CN raster).
- Qt offscreen DPI150: **145 PASS**.
- Windows native QPA DPI100: **2 PASS**, native QPA DPI150: **2 PASS**.
- Standalone EXE + Native Go R6.1: SUCCESS, проверка actual SHA равна
  манифесту: `3bba8fc9338bfaad058bb7e28d0fe7b99f7392e70b83b99ad3621adfbebbe4c8`.
  [Artifact #14191947229](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43789638737/artifacts/14191947229)
  — ZIP **69 028 319 bytes**, до **30 ноября 2026**.
- [Нативные 100/150 PNG+JSON+JUnit #14191797852](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43789638737/artifacts/14191797852),
  ZIP 341458 bytes, до 23 ноября 2026.
- [Offscreen контроль #14192230253](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43789638737/artifacts/14192230253),
  НЕ использовать для доказательства настоящей кириллицы.
- В диффе CN менялись ТОЛЬКО тесты/CI, не Python GUI production code,
  поэтому данный CN не является новой компоновкой.

## Что обнаружено при изучении картинок

Нативный GitHub Windows-дисплей **принудительно уменьшает исходный
`win.resize(1360,850)`**: на native 100% реальный логический размер
**1028×749**; native 150% **960×580** (физически 1440×870).
Offscreen режим реализует 1360×850 логически и 2040×1275 физически
при 150%. Поэтому нынешние native PNG НЕ являются сравнимой
парой одного физического разрешения и НЕ являются оригинальным
`1942×1042` источником.

Native спектр работает: 3 исходных главных таба, 8 АЦП, X 0..25600,
Y -150..0 dB, 177 px pnSpecTools. На маленьком дисплее 150%
нижние кнопки Copy/Save вне видимого pnSpecTools до прокрутки,
поэтому тест, который вызывает `.click()` программно, **не доказывает
доступность физическим кликом**. Нужна следующая крупная приёмка:
`QTest.mouseClick` после прокрутки `QScrollArea.ensureWidgetVisible`,
реальная проверка видимой геометрии и пользовательского viewport,
отсутствия перекрытий и X/Y правого тика. Выполнять вместе с проверкой
реальной исходной геометрии `1942×1042`/Windows DPI150 на операторском
экране, не менять Core чисел.

Не считать выполнение 95 DFM event routes полным восстановлением 95
обработчиков или seven-page/three-form 1:1 паритетом; COPY/SAVE оригинала
и полный FFT/FIR Y-путь на одном архиве требуют отдельной верификации.
Оригинальные Windows процедуры Upload/Download/Reset/CalibStart/Write
НЕ запускались и запрещены без оператора.

## Следующее конкретное задание

Сохранить фокус на **одновременных UI+core операторских сценариях**:
(1) физический click/popup/cursor под реально маленьким 150% viewport,
(2) original PaintBox geometry и подписи X/Y на идентичных 1942×1042
операторских скриншотах и same window BIN, (3) post-FIR envelope/Y,
(4) фактическая операционность ещё не подтверждённых семи страниц и трёх
форм. Не запускать с нуля проверенную математику Power/Y и не
подменять original native screenshot синтетической отрисовкой.
