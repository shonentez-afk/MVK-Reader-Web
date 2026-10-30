# Stage 111R — Qt/Delphi TPaintBox coordinate bridge and Windows Preview integrity

**Дата:** 30.10.2026  
**Ветка:** `research/stage111-mvkview-desktop-20261029`  
**Программный SHA:** `aa8e3b87671034636a4a63dc6486d0432c3b72c3`  
**Предыдущий полностью проверенный HEAD Stage111Q:** `6b29e9169d31004c52784cc78b6590ba161a19ea`

## 1. Состояние, восстановленное непосредственно из GitHub

Для предыдущего HEAD Stage111Q, `6b29e9169d31004c52784cc78b6590ba161a19ea`, независимо подтверждены CircleCI статусы:
- [Linux Core #58](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/58): SUCCESS.
- [Windows Core+Qt #57](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/57): SUCCESS.
- [Windows EXE #59](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/59): SUCCESS.

Это успех задания упаковки, но исторически скачанный EXE/SHA256SUMS **отдельно не сверяли**.

## 2. Оригинальная база Delphi и подтверждение/неподтверждение

Имеются приватные исходные реконструкции `Projects.7z`, `mvkview.idp` и `mvkform.dfm`, которые **не помещаются в GitHub/CI**. В Stage111Q по оригинальным `_Unit128:0084B40F–0084B42D` и `0084C840–0084C864` подтверждён размерный Margin обоих PaintBox, `_Unit115:007CA4E8–007CA62F` — исходный PixelRect и зависимости от TextWidth/TextHeight, `_Unit128:0084C8A6–0084C8F8` — расположение полос прокрутки. Исторические подтверждения о TQGrapher XOR, CursorString и x87 остаются в предыдущих отчётах.

Новых фактических метрик **запущенной оригинальной MVKView** для Stage111R пока не получено. Проектный DFM Font=T​​ahoma, Height=-13, PPI=96, размеры PaintBox на этапе дизайна не доказывают фактический DPI/шрифт/координаты при открытии окна.

## 3. Реализовано в Stage111R

### Контроль целостности автономного Windows Preview

- Новый файл `mvk_compatible/verify_windows_preview_artifact.py` — самостоятельная offline-верификация **реального файла EXE**, `SHA256SUMS.txt` и `BUILD_INFO.txt`.
- Валидируется сигнатура PE (MZ, указатель на PE и PE\0\0), повторно считается SHA-256 из байтов EXE, строго проверяется точное имя Windows Preview, source SHA (40 hex) и только разрешённая исследовательская ветка.
- Отказ при подмене/повреждении EXE, неверном манифесте, другом коммите/ветке, невалидном PE или symlink. Контроль не требует исходных приборных данных, оригинальных файлов и внешних сервисов.
- В `.circleci/config.yml` добавлен отдельный Windows шаг **после PyInstaller, но ДО `store_artifacts`**. При несоответствии build job завершается с ошибкой, артефакт не публикуется. После проверки рядом с EXE сохраняется `BUILD_VERIFICATION.json` (SHA-256, размер, source commit/branch, флаги проверок), исходный `SHA256SUMS.txt` и `BUILD_INFO.txt`.
- Это подтверждает непротиворечивость **внутри конкретной сборки CircleCI**. Факт последующего скачивания другим человеком и соответствие его копии должны подтверждаться независимой локальной проверкой: статус `separate_download_integrity_verified=False`.

### Разделение Qt и оригинального TPaintBox

- Новый `core/tqgrapher_qt_canvas_bridge_candidate.py` — явная непривилегированная **гипотеза** аффинной регистрации scene X/Y Qt ↔ исходный PixelRect; в обе стороны, с отдельным `devicePixelRatioF` как свойством среды, без бездоказательного умножения координат Delphi на DPR.
- Функция `compare_measured_landmarks` принимает только локальные независимые измеренные пары соответствующих точек Qt/native и выдаёт **только ошибки**, не сами координаты или исходные изображения.
- В существующем диагностическом диалоге Canvas Qt теперь показаны дополнительные `scaleX/scaleY` как **непроверенный кандидат**, реальные Qt font/PPI и проектный исходный DFM остаются отдельными. Линии графиков пока рисуются прежним Qt-средством; новый bridge не управляет реальным курсором.
- В коде и выводах остаются флаги `original_delphi_pixel_parity_verified=False`, `original_paintbox_runtime_landmarks_verified=False` и `native_mouse_integer_rounding_parity_verified=False`.

## 4. Тестирование и ограничения приёмки

На локальном изолированном наборе синтетических данных Stage111R прошли 22 теста: 9 integrity и 13 coordinate bridge, включая порчу EXE, MZ/PE подписи, неправильную ветку, symlink, границы/ошибки регистрации и DPR 1/2. Проверена синтаксическая корректность обновлённого CircleCI YAML. Дополнительная Qt GUI проверка добавлена в `test_desktop_qt.py`.

CircleCI кодового коммита `aa8e3b87671034636a4a63dc6486d0432c3b72c3`:
- [Linux Core #61](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/61): SUCCESS.
- [Windows Core/Qt #60](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/60): итог проверить перед окончательной приёмкой.
- Windows Preview EXE: должен пройти новый integrity шаг, фактический job/результат проверить по одному SHA.

Синтетические 22 PASS и новый CI **НЕ** означают оригинальную численную/пиксельную идентичность всей MVKView. Полные счётчики pytest Core/Qt не устанавливаются по GitHub Status API. Не подключаться к реальному прибору, не менять штатные приборные AUX4700/VALUES локальным FFT.

## 5. Приватное продолжение Stage111S

1. Проверить Windows Core/Qt, EXE и `BUILD_VERIFICATION.json` после фактического успешного pipeline для программного SHA. Извлечь Windows Preview из CircleCI Artifacts и на машине получателя независимо сверить SHA256SUMS.
2. На работающем оригинале приватно измерить Canvas.Font.Name/Height/Style, реальные Canvas.TextWidth("0"), TextWidth("0.000000"), TextHeight("0"), PixelRect/DPI, Position X/Y и 1–2 ряда в одном окне. Файл оригинального скриншота остаётся только на локальной машине.
3. Сопоставить независимо измеренные точки через `compare_measured_landmarks` и `canvas_sweep_reference_compare`. При несовпадении исправить source-derived модель, **не** подгонять без доказательств.
4. Продолжить original x87/FormatFloat/CursorString и FFT/GetSpectrum/GetNarrowbandValue/FRange на одном архивном окне; полной Delphi/parity и пользовательской приёмки 1.0 пока нет.

**GitHub:** `main` и Web v0.3.40 не изменять, аппаратные подключения без отдельного разрешения запрещены. Оригинальные PAS/DFM/IDP/production BIN/PCAPNG/закрытые коэффициенты не коммитить.

## 6. Финальный программный коммит — атомарная публикация только после проверки

**Итоговый программный SHA Stage111R:** `8c9f0d29895a8a2ae68ad09c42e678cfffe01bee`. Исходный SHA `aa8e3b87671034636a4a63dc6486d0432c3b72c3` содержит новый код/тесты; дополнительный коммит изменяет только `.circleci/config.yml`.

**Важная исправленная тонкость CircleCI:** шаг `store_artifacts` выполняется даже при провале обычного `run`, поэтому ранее использованный `store_artifacts: path: dist` потенциально мог публиковать не прошедший проверку EXE! Официальная спецификация: https://circleci.com/docs/reference/configuration-reference/#the-when-attribute

Теперь Windows Preview job:
1. Собирает EXE в `dist/`; независимо проверяет исходный PE, SHA256, manifest SHA и source commit/branch.
2. Только при успехе копирует EXE и два манифеста в **непубликуемую** временную папку `verified-dist.tmp/`.
3. Вторично проверяет уже скопированные байты; после успешной проверки пишет `BUILD_VERIFICATION.json` и переименовывает всю папку в `verified-dist/`.
4. `store_artifacts` направлен **исключительно** на `verified-dist`. При сбое до переименования эта директория отсутствует, следовательно, непроверенный EXE не окажется в Artifacts.

Изменение синтаксически проверено PyYAML локально; окончательный CircleCI на **новом SHA** проверять отдельно: [Linux #64](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/64), [Windows Core+Qt #63](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/63), Windows Preview EXE job назначается после PASS обеих зависимостей. Не переносить результаты старых запусков на новый SHA. Независимая проверка файла, скачанного пользователем с CircleCI, по-прежнему отдельная операция.

