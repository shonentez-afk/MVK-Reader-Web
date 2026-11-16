# Stage111Z31CP — исходный idle PageStart «Задачи»: Qt+Core, 100/150% DPI, безопасные реальные клики

**Дата:** 16 ноября 2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.  
**Исполняемый код и EXE SHA-коммит:** `2d4c55fb2baca2774a52da0f51d5af48d342f5f1`.  
**[GitHub Actions #43795018198](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43795018198): 4/4 SUCCESS**.

## Источник и граница точности

Пользователь прислал составной PNG **`MVK_Original_vs_Qt_Start_20261116(3).png`**:
слева оригинальная MVKView 1.0.47 без измерения (в сравнении указано
1920×1020), справа предыдущая Qt-копия из CI 150% (указано 1440×870).
Это два изображения РАЗНЫХ физических размеров, масштабированных в
общую иллюстрацию. Расстояния и цвета можно сравнивать качественно и
по логическим Delphi DFM-прямоугольникам, **но нельзя объявлять
1:1 pixel parity**. Оригинальный составной PNG и частные IP/папки
оператора в публичную ветку не добавлялись.

Отчёт original idle Tasks, ранее основанный только на словесном
описании, теперь дополнен прямым визуальным свидетельством:
- главная вкладка «Задачи» единственная видимая;
- четыре компактных открытых команды с самостоятельными иконками,
  синими заголовками и поясняющей строкой для настроек;
- команды: «Измерение», «Загрузка сигнала из файла»,
  «Настройка параметров измерительных каналов» (подзаголовок:
  «Коэффициенты передачи датчиков, частотные полосы и др.»),
  «Настройка системных параметров» (подзаголовок:
  «IP-адрес, маска подсети, настройки Modbus/TCP»);
- «IP-адрес прибора:» и «Папка хранения результатов измерений:»;
- основной фон очень светлый голубой, сгущающийся в голубую шахматную
  область у правого края; логотип ВАСТ внизу слева;
- пятая исходная DFM-кнопка Calib остаётся невидимой в обычном состоянии;
  оригинальные TCP/Modbus настройки НЕ изучались через реальное нажатие.

## Изменения production

**`core/original_start_workbench.py`:** новые
`START_OPERATOR_CAPTIONS`, `START_OPERATOR_IP_LABEL`,
`START_OPERATOR_LIBRARY_LABEL`, provenance
`START_OPERATOR_REFERENCE`. Это операторские *русские runtime строки*,
не исходный Delphi DFM `Caption='$'`. Верифицированные исходные
`START_BUTTONS`, `START_IP_RECT=(157,208,173,24)`,
`START_LIBRARY_RECT=(29,276,301,24)`, исходные Mode1/2/4/5/6
и валидатор IPv4/локальной папки оставлены БЕЗ изменений.

**`desktop/source_start_command.py` (новый):** настоящий наследник
`QPushButton` в каждом исходном прямоугольнике DFM, рисующий
прозрачный CommandLink (синяя строка, маленькая синяя подсказка,
процедурная иконка Gears/Open/EditGear/EditNet). Убраны несовместимые
белые прямоугольники и большая заливка при hover; клавиатура/мышь,
`clicked`, original TabOrder metadata и безопасная маршрутизация
по-прежнему функциональны. Пиктограммы — **Qt-кандидаты**, не
экспортированные vendor SVG/BMP.

**`desktop/original_start_ui.py`:** тот же
`OriginalStartController`, реальные `bTaskConnect`,
`bTaskView`, `bTaskConfigCh`, `bTaskConfigIP`,
`bTaskConfigCalib`. Тексты и вторичные строки теперь
соответствуют видимому оригиналу; поля и их исходные координаты
сохранены. Mode2 только открывает consent-gated Native диалог,
не производит TCP-подключения самостоятельно; Mode1/4/6 остаются
локальными проверенными маршрутами. Старые технические списки
сохраняются за F12 и не мешают источнику.

**`desktop/source_visual_skin.py`:** вместо янтарного/жёлтого
цветового дефолта — процедурный бело-голубой горизонтальный
градиент, синий checkerboard только в последней части правого поля
TImage; компактный процедурный footer-логотип и автоматическое
перемещение его вниз в окне **меньше design-time height=688**.
Исходная DFM мета-геометрия `imLogo=(3,568,432,120)` сохраняется;
на полной высоте соответствует исходной. Истинные частные original
`imBackL/imBackR/imLogo` могут быть загружены **только локально**
через `MVKVIEW_PRIVATE_SOURCE_DFM` или F12 action; исходные байты
не коммитятся и не встраиваются в публичный EXE. Для данного
синтетического CI original bitmap parity=false.

**`tests/test_stage111z31cp_qt_start_operator_visual.py` (новый):**
настоящая `MainWindow`, PageStart без архива,
геометрия пяти source кнопок, четыре видимые + скрытая Calib,
согласованные исходные подписи, голубой raster, DFM rect и
видимое нижнее branding, QTest.mouseClick на Mode1/4/6,
Mode2 через заглушку consent-only диалога; `device_io_performed=False`,
`network_scan_performed=False`. В CI создаются только снимки
Qt-копии (09_cp_idle_operator_blue_command_links) + JSON, **не оригинала**.

Старый `test_stage111z31cl_qt_source_visual_shell.py` теперь
проверяет сохранение исходной rect-метки лого отдельно от адаптивной
Qt координаты при малом экране. Публичный производственный код и
тесты прошли одну совместную приемку; FFT/Power→Y/10x512 FIR/FRange
не изменялись.

## Реальные результаты 16.11.2026

| Check | Result |
| --- | --- |
| Linux offline Core | **1954 PASS / 111 SKIP**, 1 warning, 30 subtests |
| Windows offline Core | **2132 PASS / 7 SKIP**, 1 warning, 30 subtests |
| Windows Qt smoke | **49 PASS** |
| Windows Qt offscreen DPI 100 | **6 PASS** |
| Windows Qt offscreen DPI 150 | **149 PASS** |
| Native Windows QPA DPI100 | **6 PASS** |
| Native Windows QPA DPI150 | **6 PASS** |
| Autonomous Windows onefile + embedded Native Go R6.1 | **SUCCESS** |

- [EXE artifact #14193863426](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43795018198/artifacts/14193863426):
  ZIP **69 039 458 байт**, до **30.11.2026**, внутри EXE SHA256
  `486b75223f1632f0ef251206c4e2c5cb2d566118387667bde6b73d7e9edbdf7d`
  (**manifest actual checksum совпадает**).
- [Native 100/150 image gallery/JSON #14193938308](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43795018198/artifacts/14193938308):
  **749 311 байт**, до **23.11.2026**, содержит
  `qa_stage111cn_native100/09_cp_idle_operator_blue_command_links.png`
  и `qa_stage111cn_native150/09_cp_idle_operator_blue_command_links.png`.
- [Offscreen source UI gallery #14193383971](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43795018198/artifacts/14193383971)
  — только логический QA, у offscreen возможен другой raster шрифтов.

## Что ещё не закончено, следующий крупный пакет

1. Прямой 1:1 физический оригинал+Qt, **одинаковая** 1920×1020 и
   Windows DPI150, без изменения измерения/окон. Нынешний CI
   native 150% вынужденно 960×580 logical/1440×870 physical.
2. При наличии локального original DFM/ресурсного ImageCollection
   подгрузить реальные **иконки кнопок и вкладки** так же безопасно,
   как уже поддержан локальный `TPicture.Data` фон/логотип.
   Не внедрять оригинальные проприетарные битмапы в публичный
   GitHub. Конечные пользователи без оригинала получают приближение.
3. Совместно проверить **PageStart visual→Mode1/4/6 state→PageConfig/File**
   на реальном оригинале, только с безопасными разрешенными шагами,
   затем продолжить источник PageAdc/PageSpectrum, исходный full
   envelope post-FIR и остальные 7 страниц/3 формы одним крупным
   Core+UI пакетом. Не перерабатывать заново уже принятые FFT/FRange.
4. Ни одна кнопка не получила несанкционированный доступ к реальному
   прибору: Upload/Download/Reset/CalibStart/Write запрещены без
   разрешения оператора. Real live hardware original parity НЕ доказан.
