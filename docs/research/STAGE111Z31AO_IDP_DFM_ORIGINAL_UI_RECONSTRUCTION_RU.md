# Stage111Z31AO — восстановление интерфейса MVKView 1.0.47 по IDP/DFM: первая реализация

**Дата:** 2026-11-10. **Ветка:** `research/stage111-mvkview-desktop-20261029`.  
**Решение пользователя:** восстанавливаем **всю программу, включая UI**, непосредственно по IDP/декомпилированным DFM и исходным процедурам; x32dbg используется только для неоднозначных участков, а не как основной метод. Порядок приоритета: спектр/вывод → остальной UI → остальные функции. На данном этапе **новый live x32dbg не запускать**.

## 1. Источники, реально прочитанные при Stage111Z31AO

Оригинальные приватные материалы пользователя изучены офлайн:

- `mvkview.idp` — IDR Project v3, SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`, размер `42094126` байт.
- `Projects.7z` — SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363`. Внутри найдено **134 записи**, среди них текстовая форма `Projects/mvkform.dfm` размер `817704` байт (SHA256 `192c0ebaf1bf722292a9b64497493a1de6af52a4bf8ffbe2ea28d0fe0b68c2d4`), `Projects/mvkeditform.dfm` размер `1848` байт (SHA256 `0d3900313f24b086d494e108438f33a180e4d1f12397fad434e50e88677e7531`), отдельная `WindowManForm.dfm`, `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas` и `mvkview.dpr`.
- Инвентарь `mvkform.dfm` (извлечён **локально**, без копирования Bitmap/PNG/DFM): обнаружено **145 Delphi components**. Источники `_Unit128.pas`, `0084709E..008470F8` и `0084ECF0`, отдельно раскрывают runtime активную страницу, видимость вкладок и вызовы при переключениях.
- Эти исходные материалы **не закоммичены** в публичный `MVK-Reader-Web`; там хранится только компактный производный контракт с геометрией и компонентами.

## 2. Что действительно говорит оригинал

Корневая главная форма `Tmvkform`:

- Caption = **«ТПО МВК»**; Delphi ClientWidth=`1008`, ClientHeight=`929`, `Tahoma` `Font.Height=-13`, DPI96 design-time, `Constraints.MinWidth=1024`, `MinHeight=704`.
- `pnMain` с `Pages:TPageControl` (TabHeight **44**). **Семь оригинальных TTabSheet в точно установленном порядке:**
  1. `PageStart` ImageName=`BWHand`;
  2. `PageConfig` ImageName=`BWGear`;
  3. `PageStatus` ImageName=`BWTable`;
  4. `PageAdc` ImageName=`BWOsc`;
  5. `PageSpectrum` ImageName=`BWSpec`;
  6. `PageFile` ImageName=`BWEdit`;
  7. `PageCalib` ImageName=`BWBinary`.
- **Все Caption в исходном DFM: `'$'`** — это метки runtime-перевода, нельзя объявлять их буквально «Задачи/Настройка/...» в качестве проверенных оригинальных подписей. В новом Qt они пока **семантические русские резервные заголовки**, точные локализованные строки предстоит восстановить по `_Unit128/uLanguages`.
- **Не смешивать design-time и runtime:** DFM содержит `ActivePage=PageCalib`, однако при запуске оригинал (`_Unit128:0084709E..`) выбирает **PageStart** и скрывает остальные шесть до перехода в соответствующий рабочий режим. Это нужно отдельно восстановить по `Mode`, а не закреплять активной `PageCalib`.
- `PageAdc` и `PageSpectrum` содержат канальные `TTabControl` TabHeight **36**, инструменты справа от origin x=4? Фактически **панель управления слева шириной177** с началом `(4,6)`, `pn*Graph` слева x=181.
- `PageSpectrum/pnSpecTools`: 9 основных Delphi компонентов с жёсткими координатами: `bSpecEnvelopeType` y9, `bSpecType` y56, `bSpecLines` y103, `bSpecHScale` y150, `bSpecVScale` y197, `lbSpecHint` y257, `lbSpecMean` y327, `bSpecCopyValue` y464, `bSpecSaveValue` y511. Все основные кнопки x9/w162/h41. `pbSpectrum` (8,32,767,716), вертикальная панель прокрутки шириной24, верхняя высотой24.
- `PageFile` — Splitter x369/w8: `tcFileChannels` 369 слева, `tcFileActions` 615 справа. `PageCalib` — аналогичная 369/8/615 структура. `PageStatus` использует `tcStatus`, TStringGrid и `chResult` шириной400 слева.
- `PageStart` реальные 5 task buttons: `bTaskConnect` (29,19,301,86), `bTaskConfigCh` (370,19,458,86), `bTaskView` (29,105,301,86), `bTaskConfigIP` (370,105,458,86), `bTaskConfigCalib` (370,193,458,86; `Visible=False` в DFM); оригинальные события `bTask*Click`.
- `mvkeditform.dfm`: отдельная диалоговая форма редактирования, ClientWidth357/Height445, Tahoma-11 и `bOk/bCancel/bRecalc`, `edVal/cbVal`. Её тоже нужно встроить позже, а не изображать отдельной вкладкой.

## 3. Что уже изменено в Qt-клоне (без изменения математического Core)

1. **`mvk_compatible/core/original_ui_form_contract.py`:** версионированный, чисто Python source-derived контракт формы, семи страниц, geometry/buttons/events (не содержит оригинальных PNG/DFM/IDP).
2. **`mvk_compatible/desktop/original_shell.py`:** самостоятельная Qt-оболочка `OriginalRootShell` создаёт семь исходных верхних вкладок `Pages` высотой44 и маршрутизирует Start/Status/ADC/Spectrum к существующим функциональным страницам. Внутренний 3-tab Qt сохраняется как совместимое API (`self.tabs`) и скрывается визуально — **расчётная цепочка и все прежние callbacks сохранены**. Вместо устаревших трёх верхних страниц теперь семь основных идентификаторов.
3. `PageConfig`, `PageFile`, `PageCalib`: первый source-derived каркас с реальными Delphi object names, tab-контейнерами и splitter geometry. Действия конфигурирования оборудования/калибровки **отключены**; просмотр локальной записи остаётся рабочим. Не выдавать каркас за готовую функциональность.
4. `mvk_compatible/desktop/main_window.py`: интегрирована `install_original_shell` и синхронизация доступности Wave/Spectrum; три старых index 0/1/2 оставлены совместимыми для остальных методов. `_active_tab_changed` исходного приложения не переписан, а перенаправлен только в исходные пути.
5. **Регрессионные тесты:** `test_stage111z31ao_original_ui_contract.py` — строгие данные по семи страницам/DFM geometry; `test_stage111z31ao_original_qt_shell.py` — семь верхних page, routing, internal three-tab compatibility и disabled unsafe actions. Чистая Python часть запускается без PySide6; Qt часть требует Windows/Qt зависимостей.
6. **Оригинальный спектр Code20/LOG0 по Stage111Z31AM остаётся 0 ULP подтверждённым на одном окне**. UI работа это не повторная разработка FIR/FFT/LOG, никаких исходных коэффициентов в git.

## 4. Что ещё НЕ восстановлено и что нужно сделать следующим крупным функциональным пакетом

**Это лишь первая реализация новой DFM-оболочки, НЕ полная визуальная 1:1 MVKView.**

- Довести **PageStart** до исходной сетки пяти больших кнопок, фонового изображения и логики режимов; восстановить **точные runtime-подписи/состояния** страниц из `_Unit128`, язык и скрытие вкладок, обработчики `PagesChange`.
- Довести **PageAdc/PageSpectrum** до фактических канальных вкладок и размеров `tcAdc/tcSpectrum`; снять старую независимую Qt header bar или переотнести её к отдельной панели исследования. Вернуть исходные `bSpec*` button styles/menu, status labels, cursor interactions; входной канал и SpectrumMode должны управляться единым источником.
- Привести **TQGrapher/TCo2Draw** график к источнику: 10×10 Grid, first-two-bin suppression, исходные ограничения размеров/строк, raster, séries/pixel projection, scrollbars. По возможности использовать уже реализованные `tqgrapher_*_source_candidate`, а не рисовать третий параллельный график. Windows 150% scaling проверять **только на нашем Qt-клоне**; оригинальный процесс не трогать.
- Заполнить реально работоспособные и безопасные **PageStatus/PageFile** в пределах уже подтверждённого offline архива; в **PageConfig/PageCalib** оставить unsupported device actions disabled, но восстанавливать их форму/внешний вид по DFM и функции только после проверки protocol.
- Восстановить отдельный `mvkeditform` диалог; восстановить изображения/иконки если их публикация допустима, иначе безопасные производные альтернативы; **не коммитить приватные оригинальные bitmap/IDP/DFM без согласия**.
- Сборка Windows EXE и настоящий UI screenshot нашего клона, сверка геометрии с DFM и ранее присланными screenshot оригинала. Только после этого объявлять shell визуально близким к оригиналу; никакого дополнительного x32dbg для уже восстановленной математики.

## 5. Статус приёмки

На момент записи: исходники внесены в рабочую ветку GitHub; CI запущен на commit с Qt-test. **Прямой запуск Qt-приложения в этом контейнере не выполнялся: PySide6 отсутствует.** До подтверждения Windows Actions и пользовательского запуска EXE статус **`DFM_SOURCE_SHELL_IMPLEMENTED_PENDING_QT_BUILD_AND_VISUAL_QA`**, а не `PIXEL_PARITY`.

**Приоритет дальше:** функционально работоспособное приложение на основе IDP и исходных DFM; лишь потом остаточные недоказанные случаи x87. Не переводить GigaCode обратно на ручные old x32dbg scripts/IDP повторную аттестацию.

## 6. Расширение Stage111Z31AP — source UI главной формы, каналы и диалог редактирования

После фиксации первого 7-страничного shell внесён следующий функциональный пакет:

- `mvk_compatible/desktop/original_task_ui.py`: **пять task buttons оригинальной PageStart** с DFM именами `bTaskConnect`, `bTaskConfigCh`, `bTaskView`, `bTaskConfigIP`, `bTaskConfigCalib`. Позиции и размеры сохранены в `ORIGINAL_TASK_BUTTONS`. `bTaskView` открывает локальное измерение, `bTaskConnect` вызывает существующий **отдельно подтверждаемый** Native R6.1 capture dialog, `bTaskConfigCh` переходит к безопасной панели конфигурации. Сетевые настройки и калибровка остаются disabled, `bTaskConfigCalib` original `Visible=False`. Старые Qt shortcut атрибуты не удалены, а скрыты ради оригинальной разметки.
- `PageAdc/tcAdc` и `PageSpectrum/tcSpectrum`: исходные **36px** канальные `TTabControl` теперь представлены двумя синхронными `QTabBar`, оба используют единый `self.adc` model (имеющиеся восемь каналов импортёра), смена канала в одном отражается в другом; число/имена реальных tabs в оригинале зависят от runtime конфигурации и ещё не полностью восстановлены.
- Посторонняя **Qt служебная верхняя панель** (открытие/канал/DSP), которой нет в оригинальном DFM main form, **скрыта по умолчанию**, доступна отдельно через меню `Вид → Служебная панель Qt`, её методы и данные не удалены.
- `mvk_compatible/desktop/original_value_edit_dialog.py`: первая реконструкция отдельной `mvkeditform` (`Редактирование`, Client357×445, `lbVal`, `lbUnits`, `edVal`, `cbVal`, `bOk`, `bCancel`, `bRecalc`). Исходное DFM содержит перекрывающиеся поля `edVal` и `cbVal` — Qt показывает **либо редактор, либо список** согласно режиму. `bRecalc` скрыт (`Visible=False` по DFM). Пока это автономный локальный диалог, **ещё не привязан** к исходным обработчикам параметров прибора.
- Новые Qt тесты следят за source PageStart, 36px синхронизацией каналов, отсутствием аппаратных действий и диалоговым режимом.

**Статус тестов:** исходный UI-shell коммит `bb221fe01414a9a688553b3309cb942ef37fd3e8` в GitHub Actions [#42785507481](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42785507481) завершён **SUCCESS** (Linux, Windows Qt и EXE). **Расширенный пакет с каналами и диалогом: CI SUCCESS** [Actions #42786689689](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42786689689): Linux core PASS, Windows offline core/Qt PASS, автономный Windows EXE PASS. Проверенный EXE хранится в artifact **[MVKViewCompatible_Stage111_Windows_Preview #13748099890](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42786689689)** (собран из source commit `db07c28361d981e9025d82d2e19bab0825551812`). Это подтверждает сборку/тесты, **не pixel-exact** интерфейс и **не полноту** конфигурации/калибровки.

**Следующий приоритет:** восстановить точные локализованные caption strings, фон/иконки главной формы и PageStart, связать `PageStatus` напрямую с моделями статуса без внутренних вкладок исследования, полностью перенести исходный сценарий PageFile (на локальном архиве), привести TQGrapher axis/font/plot размер к исходной layout и Win32/Qt 150% DPI. Конфигурирование и калибровка прибора остаются отключёнными до восстановления исходной semantics и отдельного разрешения.

