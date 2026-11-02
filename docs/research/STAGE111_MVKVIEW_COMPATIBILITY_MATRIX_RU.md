> **STAGE111T — 30.10.2026 / ОСНОВНОЙ ПРОГРАММНЫЙ SHA 35f13a6fd0d420bb2b8f70eb7f9fe7495093c390.** Цель — единая автономная Windows MVKView Compatible, branch `research/stage111-mvkview-desktop-20261029`. По приватному оригинальному Delphi `_Unit128:0084C5DB–0084C748` восстановлена V-полоса: db Full=150, Page=[150,100,75,50,25,10]; физические единицы Full=100000, Page=[100000,10000,1000,100,10,1]; при смене типа спектра Tag=0(dB) или Tag=3(физ.). В Qt `bSpecVScale` теперь шесть исходных пунктов и VCL Pos/Page/Max, но отрисовка Y использует явно НЕПРИНЯТЫЙ Qt GraphDefaultVScale candidate. `bSpecLines` теперь все 6 source NFFT=[262144,131072,65536,32768,16384,8192], исследования 1024/4096 отдельно, без zero padding; BIN history проверяется до вычисления, недостаточные пункты отключены. Синтетические тесты включают 4096 и 8192 отсчётов. [Linux Core #79](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/79) SUCCESS; [Windows Core/Qt #78](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/78) SUCCESS; [EXE #80](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/80) PENDING. [Stage111T отчёт](STAGE111T_VERTICAL_AND_SOURCE_FFT_RU.md). Следующий Stage111U: original GraphDefaultVScale, TCanvas DPI/Font/Cursor и GetSpectrum/FormatFloat/x87, независимый скачанный EXE SHA. `main`, Web v0.3.40 и реальный прибор не изменять, приватные PAS/DFM/IDP/BIN/PCAPNG в GitHub не публиковать.

> **STAGE111S — ВОССТАНОВЛЕНЫ 4 ИСХОДНЫЕ ТАБЛИЦЫ МАСШТАБОВ И МЕНЮ (30.10.2026).** Ветка research/stage111-mvkview-desktop-20261029, программный SHA af036bdd1be4dfdf2481a416f73cc9759db355d4. Приватный mvkview.idp плюс оригинальный Delphi _Unit128 подтвердили расположенные подряд DWORD: H(10)=[25600,12800,6400,3200,1600,800,400,200,100,50] Гц; FFT(6)=[262144,131072,65536,32768,16384,8192]; Y-физические делители(6)=[1,10,100,1000,10000,100000]; Y-dB(6)=[150,100,75,50,25,10]. Оригинальные файлы НЕ публиковались. В native Qt подключено выпадающее меню десяти H-пресетов (bSpecHScale, source Tag), сохранение/ограничение целой Hz-позиции; вертикальная шкала и выбор source NFFT пока отдельные кандидаты, т.к. нужен настоящий original Canvas/архив с достаточной историей. [Linux Core #75](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/75) SUCCESS; [Windows Core/Qt #76](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/76) SUCCESS; [EXE #77](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/77) PENDING. Предыдущий Stage111S core SHA fba280de65f25cee854f6b55aecf269c26ee6e74 уже прошёл Linux #72 и Windows Qt #73. [Полный технический отчёт](STAGE111S_SOURCE_SPECTRUM_SCROLLBARS_RU.md). Следующий Stage111T: source V popup/FFT history, runtime TCanvas/DPI, Original FFT/FRange/FormatFloat/x87. Главный продукт только автономный Windows Qt, не main/Web v0.3.40; не подключать прибор, не коммитить приватные PAS/DFM/IDP/BIN/PCAPNG.

> **АКТУАЛЬНО Stage111O (29.10.2026).** Linux/Windows Qt/Windows EXE для программного SHA `aa3a0dd0a11e9821dfbfd350f16dfbb8bcc19fde` подтверждены SUCCESS CircleCI jobs [#30](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/30) / [#31](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/31) / [#32](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/32). Source-verified Delphi MouseMove обеих вкладок и X dedup реализованы в native Qt, но Canvas/x87/GDI XOR и original FFT parity не приняты. [Отчёт](STAGE111O_ORIGINAL_MOUSEMOVE_CURSOR_RU.md) и [общий статус](STAGE111_CURRENT_STATUS_RU.md).

# Stage111 — матрица приёмки точного аналога MVKView (три вкладки)

**Дата:** 29.10.2026. **Состояние:** Stage111N signed ScrWidth/source Single/Canvas-DPI private sweep IMPLEMENTED_TESTED (новый CI PENDING), Stage111M source-verified TQGrapher horizontal Crosshair Y independent from averaged cursor label; private 1/2-line pixel reference comparator, offline CI 368 Linux/368 Windows/14 Qt PASS; исходный пиксельный/RTL паритет оригинальной MVKView НЕ принят. Численная/побитовая приёмка оригинальной MVKView ещё НЕ закрыта; это не релиз MVKView Compatible 1.0. Обновлять при каждом техническом Stage. Базовые документы: ADR Compatibility First, ADR original DSP, Stage81c/d, Stage109, Stage110/110B.

## Ключ к статусам
- **SOURCE_VERIFIED** — оригинальный приборный источник подтверждён Stage109, значения реально получены; не означает, что все элементы GUI совпадают.
- **IMPLEMENTED_TESTED** — реализовано в новом `mvk_compatible`, синтетическая регрессия и/или Windows GUI offscreen PASS; не обязательно паритет Delphi.
- **CANDIDATE** — расчёт/UX основан на IDR и исследованиях, численный/визуальный паритет ещё не доказан.
- **TODO** — штатная функция оригинала пока не воспроизведена/не принята.

## Источники данных и безопасность

| Проверка | Уровень | Источник / не закрыто |
|---|---|---|
| Native TCP/10230 8 ADC, 2 TACH, AUX4700 | SOURCE_VERIFIED | Stage109, один №84 и 30 секунд; не переписывать |
| Калибровка BIN K текущей сессии | SOURCE_VERIFIED + IMPLEMENTED_TESTED | Native R6.1; в новом GUI BIN не умножается на K повторно |
| 43 оригинальные третьоктавные и 24 RMS / ADC | SOURCE_VERIFIED + IMPLEMENTED_TESTED | По полному AUX или проверенному VALUES |
| 24 PEAK / 24 PEAK-PEAK | SOURCE_VERIFIED условно + IMPLEMENTED_TESTED | Только при исходном полном AUX того же RAW, иначе «—» |
| Состояние датчика 0x400 | SOURCE_VERIFIED + IMPLEMENTED_TESTED | Не скрывать предупреждение при наличии samples |
| Offline ZIP 8 BIN/TSXML SHA и DSP CSV | IMPLEMENTED_TESTED | Все восемь каналов, проверка источника/целостности |
| Без HTTP, фонового сервера, сетевых команд | IMPLEMENTED_TESTED | Pure core + standalone Qt, Windows CI |
| Multi-session/archive DB | TODO | Нынешний Desktop открывает один ZIP |
| Live через один Native R6.1 Collector | TODO | Требует решения по IPC и отдельного разрешения для прибора |

## Вкладка «Расчётные данные»

| Оригинальная функция | Статус Stage111A | Условие приёмки |
|---|---|---|
| `PageStatus`, `tabResult`, `tabAllResult` | CANDIDATE | DFM layout и порядок вкладок, сравнить скриншоты |
| 8 каналов в одной сессии | IMPLEMENTED_TESTED | Тесты и Qt переключение ADC1/ADC7 |
| 60 обновлений за 30с, выбор расчётного кадра | IMPLEMENTED_TESTED | В ZIP доступны 2..60+ в зависимости от сессии |
| 43 третьоктавных измерения | IMPLEMENTED_TESTED | 43 строки + график, график ещё НЕ идентичен TChart |
| 24 RMS, 24 PIK и 24 PIK-PIK | IMPLEMENTED_TESTED условно | Оригинальный AUX и метки единиц |
| Приборные сенсорные статусы и напряжение | IMPLEMENTED_TESTED | 0x400 ALERT, не маскировать |
| Оригинальные имена полей/форматирование и таблицы | CANDIDATE | Используется VALUES metadata, DFM паритет не доказан |
| `chResult`/SpecSeries/TBarSeries визуальный паритет | TODO | Оригинальные оси, частоты, раскраска, пороги |
| `tabAlarmResult`, контрольные зоны и тревоги | TODO | Нужны полные обработчики Delphi и эталоны |
| Тахометр и дополнительные режимы состояния | TODO | Нужны проверенные TACH подключенного датчика |

## Вкладка «Временной сигнал»

| Функция оригинала | Статус | Условие приёмки |
|---|---|---|
| `PageAdc`, выбор 8 ADC | IMPLEMENTED_TESTED | Qt-таб и кнопки выбора |
| `GetSignal` чтение хранилища / BIN | CANDIDATE + IMPLEMENTED_TESTED | Stage111C: оригинальный `007D2228` float32 ring wrap/zero-prefix, `007D0DEC` **обратный выходной буфер** и отсутствие двойного `FRange` без огибающей; exact TQGrapher ось ещё TODO |
| Осциллограмма из калиброванного BIN | IMPLEMENTED_TESTED | pyqtgraph, экстремумы и порядок времени |
| `AC/AC+DC` | SOURCE_VERIFIED + IMPLEMENTED_TESTED | DFM: AC Tag0/NoDC=1, AC+DC Tag1/NoDC=0; `007D2344` последовательно вычитает f32 среднее, SCЗ окна отдельное от DSP AUX |
| `bAdcHScale`/`bAdcVScale`/zoom/scroll | CANDIDATE | Qt масштаб доступен, поведение Delphi не доказано |
| `TQGrapher.UpdateCursor` и точная выборка | CANDIDATE | Точный sample индекс/значение и переключение хронология BIN / реверс GetSignal; **ориентация оригинальной абсциссы и формат CursorString не подтверждены** |
| Временное окно, перемещение по записи | IMPLEMENTED_TESTED | Начало и длительность, нет полной навигации GUI |
| `bAdcEnvelopeType`, `GetAdjustedEnvelopeLength` | CANDIDATE + IMPLEMENTED_TESTED | Stage111E: найдены оригинальные таблицы 8CD980/8D2A58/8CDA00/8CDA2C и 10×512 коэффициентов 8CDA58 в **приватном IDP**, реализованы IDR FIR/декмация/I-Q и выбор 31 кодов после локальной SHA-проверки; реальный эталон Delphi/окно/FRange ещё не подтверждены |
| Цвета, подписи, СКЗ/среднее и копирование | CANDIDATE + IMPLEMENTED_TESTED | Stage111C: `OutputMean` по оригинальному `GetSignal` фактически СКЗ окна; фиксируем отдельно от DSP/прибора. Оригинальные оси/цвета/экспорт TODO |
| Live/Archive переключение | TODO | Сейчас только завершённый архив ZIP |

## Вкладка «Спектр»

| Функция оригинала | Статус | Условие приёмки |
|---|---|---|
| `PageSpectrum` + 8 ADC | IMPLEMENTED_TESTED | Qt spectrum tab, выбор всех каналов |
| Четыре режима `mSpecType` | CANDIDATE + IMPLEMENTED_TESTED | Stage111F: огибающая + 4 original IDR режима: 0 log, 1 linear, 2 однократная 007D2164 интеграция мощности, 3 двукратная; отсутствует оригинальная численная сверка и точный FRange |
| Выбор FFT N 1024..262144 и df | IMPLEMENTED_TESTED | Выбор N и автоматическое уменьшение для короткого ZIP |
| Hann периодическое RMS `1/sqrt(1.5)` | CANDIDATE | Stage81c статическое IDR, NumPy FFT не битово оригинальна |
| FFT backend `TDSXFastFourier` | CANDIDATE + IMPLEMENTED_TESTED | Stage111B: собственный float32 radix-2 с bit reversal и twiddle по `_Unit115`, синтетически против NumPy; **x87 и оригинальный runtime ещё не сверены** |
| 0-й режим dB и `-180` | CANDIDATE | Stage81d/110B: `10*(fn(P)-2*fn(N/2))`; `fn=log10` не подтверждено |
| Безусловное вычитание среднего перед FFT | CANDIDATE + IMPLEMENTED_TESTED | Stage111B: `0x007D14B3→0x007D2344`, f32 running sum, регрессия по DC-offset; не путать с AC-сигналом |
| Нижние FFT-бин(ы): `max(2,round(N/(2fs)))` | SOURCE_VERIFIED + IMPLEMENTED_TESTED | Stage111B `_Unit115` + доказанный Max helper `_Unit114:007B1CF0`; при fs=65536 обнулить 2, в dB −180 |
| FFT IDR float32 / NumPy — два отдельных кандидата | IMPLEMENTED_TESTED | Qt переключатель, сравнение, exact cursor в выбранном backend; не оригинальный DSP |
| Исключение Nyquist `N/2` | IMPLEMENTED_TESTED | В Stage111A исправлено по Stage81d/110B |
| `bSpecLines`, частотное разрешение | CANDIDATE | N/df уже есть, оригинальные пресеты надо сверять |
| `bSpecHScale`/`bSpecVScale`, скроллбары | CANDIDATE + IMPLEMENTED_TESTED | Stage111E: реальные Qt кнопки масштаба и синхронные H/V QScrollBar 24px по оригинальному DFM, видимость при увеличении, функциональная регрессия; точные Delphi пределы не подтверждены |
| `GetNarrowbandValue` / `GetNoisePeak` | SOURCE_VERIFIED + CANDIDATE + IMPLEMENTED_TESTED | Stage111H: `007D0E58` исходный центр `Round(N/fs*InputValue)`, ширина `Max(1,Round(center_raw*0.0005))`, узкополосная сумма мощности; с шумовым флагом — поиск трёх соседних бин по диапазону до `N/8`, за исключением `center ± 20*radius`. Полный FFT BIN, отдельная исследовательская панель, отказ при небезопасном крае; численная Delphi parity и `FRange` TODO |
| **FRange:Single / исходная калибровка** | SOURCE_VERIFIED STRUCTURE + CANDIDATE + IMPLEMENTED_TESTED | Stage111I: оригинал `Create:007D0A61` инициализирует 1.0, но `ProcessBufferChunk:007D23D5` умножает вход, `007D22C8` делит при чтении, `GetSpectrum`/Narrowband/Signal используют итоговый масштаб. Новый `resolve_f_range` хранит DEFAULT_ONE vs OPERATOR_UNVERIFIED, строго float32; физический FRange каждого архива НЕ доказан |
| **GetSpectrum суммирование qword мощности** | SOURCE_VERIFIED STRUCTURE + IMPLEMENTED_TESTED | Stage111I: `007D1807..1810` на каждом бине сохраняет сумму в float64; вместо прежней pairwise NumPy теперь source-stepwise. Синтетический extreme-range стресс обнаруживает разницу, оригинальный x87 численный эталон открыт |
| **Домен исходного FRange буфера** | SOURCE_VERIFIED STRUCTURE + CANDIDATE + IMPLEMENTED_TESTED | Stage111J: оригинальный ProcessBufferChunk 007D23D5 масштабирует float-ring, GetSpectrum 007D14A5 и Narrowband 007D0F83 читают с флагом 1 и делят на FRange **до DC/FFT**, затем выход снова умножают. Явные calibrated_bin / original_float_storage, оригинальная принадлежность Native R6.1 BIN НЕ установлена; автоматического выбора нет |
| **SpecGrapher.Series.DataSize / XScale** | SOURCE_VERIFIED STRUCTURE + IMPLEMENTED_TESTED | Stage111J: 00848297–008482D1 подтверждает XScale=Single(fs/N), видимая серия ровно TRUNC((N/2)/1.28), например 1600 из 2048 при N=4096. Полный N/2 остаётся в GetSpectrum; видимая серия и диапазон скроллбаров ограничены отдельно |
| `GetSpectrum` OutputMean/OutputPeakX/OutputPeakY | SOURCE_VERIFIED + CANDIDATE + IMPLEMENTED_TESTED | Stage111G: оригинальный диапазон бин(ов) `max(2,Round(N/(2fs)))..Trunc(N/2.56)` по 007D1558, сумма мощности, максимум (при равенстве первый), **энергетический центр пяти бинов ±2** через 007D21A8, амплитуда `sqrt(sum(P)/2)*FRange/(N/2)`; FRange/x87/численный оригинальный эталон всё ещё TODO |
| Пиксельный курсор `TQGrapher.UpdateCursor` | SOURCE_VERIFIED STRUCTURE + CANDIDATE + IMPLEMENTED_TESTED | Stage111J: исходный pixel→bin Trunc, **signed maximum** на пиксель и 1/3 sqrt(sum squares) без деления; ограничение пиксельного поиска фактической TQGRSeries.DataSize. Отдельный native itosM/itosC для bin→pixel округления по 007CAB94; реальные исходные координаты/скриншот ещё TODO |
| **TQGrapher PixelRect / 6 коэффициентов Canvas** | SOURCE_VERIFIED FORMULAS + IMPLEMENTED_TESTED, DELPHI_PIXEL_PARITY TODO | Stage111K: оригинальный 007CA4C8 рассчитывает PixelLeft/Right/Top/Bottom из Margin, TCanvas.TextWidth(0 / 0.000000), TextHeight(0), XName/YName. Вычисляются независимые **Single itosM/C, stoiM/C, ytosM/C**, предусмотрены малые окна/защитные проверки. В Qt добавлено только **помеченное диагностическое** окно с метриками шрифта Qt; оригинальный Font/DPI/PixelRect НЕ измерены |
| **007B2090 Delphi FormatFloat маска** | SOURCE_VERIFIED PATTERN + IMPLEMENTED_TESTED, RTL PARITY TODO | Stage111K: отдельная cursor_decimal_mask_candidate() подтверждает цикл Single(abs(x)*10) до 10^(digits-1), динамическое «0.» + нули и последующее удаление хвостовых нулей; точная функция Delphi 0042EE10, x87 и TFormatSettings по оригинальному эталону НЕ проверены |
| **Приватная сверка Canvas со скриншотом** | IMPLEMENTED_TESTED DIAGNOSTIC, ORIGINAL REFERENCE TODO | Новый canvas_reference_compare.py принимает локальный JSON размеров и оригинальные точки PixelRect/itos/stoi; строгие допустимые ошибки, SHA256, исходные значения/скриншот не публикует. Нет оригинального измеренного скриншота, поэтому оригинальная геометрия не принята |
| **Перекрестие CursorDrawnX + CursorDrawnY** | SOURCE-VERIFIED STRUCTURE + IMPLEMENTED_TESTED CANDIDATE, ORIGINAL PIXEL PARITY TODO | Stage111M: 007CA9BA–007CA9F0 рисует горизонтальную линию на уровне **raw signed maximum × YScale** с отдельным Single ytosM/C, clipping PixelTop/Bottom и Round. При CursorAveraging=3 подпись вычисляется из sqrt(sum(Y²)) и НЕ является уровнем рисования линии. Первый/второй ряд имеют независимые горизонтальные линии, все исходные массивы/приборный DSP неизменны. В обычной Qt-вкладке «Спектр» при щелчке уже рисуется горизонталь по выбранной **raw** амплитуде, при averaging=3 подпись остаётся отдельной; координатное отображение выполняет Qt и не является оригинальным Delphi PixelRect. Полный двухрядный source-алгоритм остаётся изолированным до оригинального Canvas-эталона |
| **Оригинальная приватная сверка X/Y курсора** | IMPLEMENTED_TESTED DIAGNOSTIC, ORIGINAL REFERENCE TODO | Расширен cursor_reference_compare.py: оператор задаёт original X pixel и один/два horizontal CursorDrawnY; результат содержит только абсолютные ошибки, флаг совпадения количества линий и SHA, без оригинальных значений. Блокируется неправильный ввод и несовпадение; настоящий эталон оригинальной MVKView пока отсутствует |
| **Двухрядный курсор TQGrapher** | SOURCE-DERIVED STRUCTURE + IMPLEMENTED_TESTED, DELPHI PARITY TODO | Stage111L: для каждого из двух рядов отдельно ищется signed максимум в одном пиксельном диапазоне; общая YName, CursorPos/selected-bin/rounded-line pixel независимы, у averaging=3 — sqrt(sum(y²)) без деления, отказ при опасной граничной памяти. Отдельные чистые модули и 25 синтетических тестов; пока **не подключены к рабочему Qt-курсору** без эталона оригинала |
| **Приватная сверка CursorString и пикселя** | IMPLEMENTED_TESTED DIAGNOSTIC, ORIGINAL REFERENCE TODO | Stage111L: cursor_reference_compare.py читает только локальные JSON/NPY/TXT, запрещает pickle и отдаёт лишь SHA/флаги/позиции расхождений, не публикует исходные тексты и массивы. Настоящий исходный TCanvas/двухрядный эталон ещё отсутствует |
| **CursorString X/Y/XName/YName** | SOURCE_VERIFIED STRUCTURE + CANDIDATE + IMPLEMENTED_TESTED | Stage111J: 007CA459 CursorSep=CRLF, 007CA903..007CAAEE формирует formatted4 X + XName, затем formatted4 Y + YName и дополнительную строку при второй серии; локализация/Delphi FormatFloat 007B2090 не приняты |
| `bSpecEnvelopeType`, спектральные фильтры | CANDIDATE + IMPLEMENTED_TESTED | Stage111F: исходная IDR-структура `GetSpectrum` через FIR/IQ→Hann→FFT; **однократное DC до огибающей**, 4 режима, полный N/2, строгая FIR-история и SHA-верифицированный **локальный** IDP; точные исходное окно/физический FRange/Delphi FFT ещё не приняты |
| `bSpecCopyValue`/`bSpecSaveValue` | SOURCE_VERIFIED + CANDIDATE + IMPLEMENTED_TESTED | Stage111G: `0084BC28` — три значения `OutputMean(3) TAB PeakX*XScale(4) TAB PeakY(4)` в локальный clipboard; `0084BD7C` — заголовок `sep=|` и три поля через `|`, append. Работающие Qt действия доступны как **IDR-кандидаты**, локальный CSV с отдельным заголовком защищён от смешивания с оригинальным `SPEC-FREQ`; формат `007B2090`/Delphi RTL, оригинальный `edLibraryPath` и локализация НЕ приняты |
| **Оригинальный численный/текстовый эталон Copy** | IMPLEMENTED_TESTED DIAGNOSTIC, PARITY TODO | Stage111I: `triplet_reference_compare.py` отдельно сравнивает numeric delta и exact TAB/decimal candidate text; Qt позволяет открыть **приватный** оригинальный TXT, показывает только SHA и расхождения. `--require-display-text` строгий; ни одно синтетическое совпадение не утверждает оригинальный Delphi/x87 паритет |
| Оригинальные подписи/сетка/логарифмическая ось | CANDIDATE + LAYOUT_IMPLEMENTED_TESTED | Stage111E структура Spectrum: pnSpecTools 177px, оригинальный порядок девяти органов, верхний/правый скроллбар 24px; внешний вид, локализация и точная шкала всё ещё требуют скриншотов |

## Stage111M — независимый расчёт двух горизонтальных линий

По исходным IDR _Unit115:007CA9BA–007CAC5E восстановлено, что каждая горизонтальная линия CursorDrawnY вычисляется по отдельному raw максимуму конкретного ряда, масштабируется YScale и проецируется по ytosM/C с saturate PixelTop/Bottom и Round. **Не** использовать отображаемый averaging=3 RMS вместо raw для положения линии. Чистый модуль tqgrapher_crosshair_idr_candidate.py и приватный сравнитель X/Y пикселей получили новые синтетические тесты. Qt добавляет **одну горизонтальную линию** по raw Y на обычном спектре, но полный двухрядный изолированный кандидат и исходный pixel-to-pixel Delphi остаются без реального эталона. [Stage111M](STAGE111M_TQGRAPHER_CROSSHAIR_HORIZONTAL_LINES_RU.md).

## Stage111L — восстановлен независимый двухрядный TQGrapher

Исходные _Unit115:007CA76C–007CAAFB описывают два отдельных поиска максимума по общему пиксельному диапазону, общую YName для обоих рядов, отдельное округление линии itosM/C и форматирование X/Y через CursorString. Это реализовано в новом изолированном модуле, без изменения существующего Qt графического курсора и приборных AUX4700. Приватный сравнитель с оригинальным TXT/пикселем предоставляет диагностические ошибки и SHA, но **не подтверждает Delphi parity** без оригинального эталона. [Архивный source report Stage111L](STAGE111L_MULTISERIES_CURSOR_PARITY_RU.md).

## Stage111K — исходные отступы, пиксели и форматная маска

Декомпилированный TQGrapher:007CA4C8 по входным TextWidth(0), TextWidth(0.000000), TextHeight(0), ScrLeft/Width и Series.XStart/XScale создаёт исходные PixelRect и независимые Single itos/stoi; точные font metrics реальной Delphi формы ещё не получены. DFM проектный pbSpectrum 767×716 динамически масштабируется и не может служить фиксированным оригинальным графиком. Num-format 007B2090 динамически формирует маску 0.0..., но Delphi RTL FormatFloat и x87 текстовую строку следует принять только по оригинальному Copy/CursorString. Код, тесты и безопасная инструкция приватной сверки: [Stage111K](STAGE111K_TQGRAPHER_CANVAS_COORDINATES_FORMATFLOAT_RU.md).

## Stage111J — разделение исходного буфера, отображения и полного спектра

Найден принципиальный источник ложных расхождений: для исходного FAdcDataType==1/float-ring оригинальный 007D2228 читает значение / FRange **перед** FFT; один только post-FFT множитель Stage111I не эквивалентен этому пути. Native BIN с физической калибровкой не приравнивается к оригинальному PAdcFloatData без эталона. В исследовательской Qt версии оба варианта выбираются явно; AUX4700 не меняется. Сравнительные CLI имеют --input-domain, не подбирают коэффициент и не публикуют исходные числа.

Также исходная видимая серия Spectrum — только N/2.56 бинов, тогда как полный FFT N/2 и интегральный GetSpectrum не уменьшаются. Исходный CursorString переносит X/Y через CRLF; реальный Delphi RTL округления и оригинальный pixel rectangle остаются незакрытыми. Источник и тесты: [Stage111J](STAGE111J_ORIGINAL_FRANGE_RING_TQGRAPHER_CURSOR_RU.md).

## Stage111I — калибровка, порядок накопления и оригинальный Copy

Числовая точность отделена от доказательства оригинального источника: `FRange=1` в конструкторе — не фактическая калибровка архива. В `calibration_candidate.py` операторский FRange хранится как `Single` с явным `OPERATOR_SUPPLIED_UNVERIFIED`; значения из исходного AUX4700 не изменяются. Исходное суммирование спектральной мощности заменено с NumPy pairwise на последовательные `Single + qword → qword` по `007D1807`. Отдельный локальный стенд сравнивает оригинальные TAB-поля **по числу и по точному тексту**, но не подбирает масштаб и не выдаёт результаты за Delphi-паритет. Подробности [Stage111I](STAGE111I_FRANGE_X87_NUMERIC_TEXT_REFERENCE_RU.md).

## Stage111H — отдельный Narrowband и доказательная сверка Copy

Точный исходный `GetNarrowbandValue` не равен графическому `GetSpectrum`: отдельный `OutputValue` и опциональный `GetNoisePeak=True` (шумовой пик с окном 3 бина и исключением области ±20 ширин). Кандидат реализован в `narrowband_idr_candidate.py`, публичный `OfflineSession.narrowband` и исследовательские органы Qt. Приборные `MVK_DSP_AUX4700` по-прежнему не подменяются.

`triplet_reference_compare.py` принимает **одну локально скопированную строку** оригинальной MVKView (3 TAB-поля, явная десятичная запятая/точка) и сравнивает с тремя `GetSpectrum` полями исходного BIN. Без оригинального эталона и доказанной идентичности параметров численная Delphi-паритетность **не принята**, независимо от synthetic PASS. Подробнее [Stage111H](STAGE111H_NARROWBAND_NOISE_PEAK_TRIPLET_PARITY_RU.md).

## Stage111G — пиковые и интегральные значения

Отдельный `mvk_compatible/core/spectrum_metrics_idr_candidate.py` принимает **полную мощность FFT N/2**, не графические прореженные точки. Оригинальные `OutputPeakX` / `OutputPeakY` — **не простой максимум амплитуды**. По `_Unit115:007D21A8` частота пика находится как энергетически взвешенный центр ±2 соседних FFT-бинов вокруг максимальной мощности, при пике в бине <=2 возвращает нулевые peak. При `SpectrumType=2/3` сначала интегрируется исходная **мощность** `007D2164`, а уже потом получаются амплитуды и суммарные показатели. Статус source-confirmed structure, synthetic tested; **не** оригинальные приборные AUX4700 и **не** принят Delphi численный паритет.

## Stage111F — отдельная точка численной сверки

Для приватного сравнения с исходной MVKView реализован `mvk_compatible/reference_compare.py`. Результат строго диагностический: запрещены интерполяция несовпавших частот, автозамена окна, подгонка коэффициента; возвращаются количество несовпадающих бинов, максимум/СКО разностей и SHA256 **локального** CSV. Даже при совпадении вывод содержит `original_app_parity_certified=false`. На момент Stage111F **настоящий оригинальный CSV на тех же параметрах ещё не предъявлен**; допускать только SYNTHETIC CI и частный IDP sanity. Порядок операций подтверждён в `_Unit115` (DC→FIR/IQ→FFT, без двойного DC).

## Обязательная последовательность приёмки
1. Проверить Windows Preview, безопасность локального чтения и целостность реального *частного* экспортного ZIP (файлы не публиковать).
2. Сделать скриншоты оригинальной MVKView для всех трёх вкладок и фиксированных настроек; сравнить структуру элементов.
3. Использовать **одинаковый** BIN/окно/N/mode для NumPy кандидата и оригинальной `GetSpectrum`; оценить частоту, амплитуду, log helper, dc/Nyquist, порядок, масштаб и RMS.
4. Переносить в ядро только доказанную семантику; обновлять отдельные тесты и статус матрицы.
5. Не объявлять Compatible 1.0 до закрытия всех обязательных строк; экспериментальные расширения Web отдельно от совместимости.


## Stage111N — дополнительная совместимость TQGrapher

| Проверка | Уровень | Доказательство / открыто |
|---|---|---|
| Signed/reversed ScrWidth, tiny span, ScrHeight, Series.XScale | SOURCE_VERIFIED FORMULAS + IMPLEMENTED_TESTED CANDIDATE | Private _Unit115:007CA4F7–007CA571. Синтетические тесты, новая CI ожидается; Delphi x87 ещё нет |
| Inverted X native pixel+1 index order | SOURCE_VERIFIED STRUCTURE + CANDIDATE | Отрицательная stoiM допускается, диапазон не переставляется; исходная пиксельная сверка TODO |
| Canvas/Font/DPI offline batch | IMPLEMENTED_TESTED DIAGNOSTIC | Новый canvas_sweep_reference_compare.py: 14 метрик и оригинальные Pixels/affine по отдельным измерениям; эталонного Canvas пока нет |
| Stage111N full CI and Windows EXE | PENDING | SHA commit 54462f6c254bb802c603a81e0343d3344878fcf4, итог проверить в Actions; Stage111M SUCCESS относится к прошлому коду |


### CI BLOCKER Stage111N


## GitHub Actions validation blocked (29.10.2026 UTC)

Latest checked Stage111N Actions: https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40905305758, source SHA `9346557611fa1361bb43885859eba39d36d5fb9c`, `conclusion=failure`. Linux offline-core and Windows desktop-windows both reported `failure` **before a runner was assigned**: `runner_id=0`, empty `runner_name` and `steps=[]`, approximately 2–3 seconds after job creation. Windows EXE was `skipped`. Earlier Stage111N runs 40905127698 and 40905080313 also reported failure. No pytest failure or successful test execution can be inferred from these runs. Diagnose runner/account/repository Actions infrastructure or limits independently, re-run when runners are available, and accept Stage111N only after observing actual Linux/Windows/Qt jobs and an EXE artifact for the exact latest source SHA. Stage111M 40900170911 remains the most recent confirmed successful code CI and is **not** a Stage111N pass.


## Stage111N — CI-перенос: CircleCI

| Проверка | Статус | Условия |
|---|---|---|
| CircleCI Linux Core | CONFIGURED, NOT RUN/NOT VERIFIED | `.circleci/config.yml`: cimg/python:3.11, все core тесты без Qt |
| CircleCI Windows Core | CONFIGURED, NOT RUN/NOT VERIFIED | Windows Server 2022, Python 3.11+, отдельный junit |
| CircleCI Windows Qt | CONFIGURED, NOT RUN/NOT VERIFIED | QT_QPA_PLATFORM=offscreen, Qt smoke pytest |
| CircleCI Windows Preview EXE + SHA | CONFIGURED, NOT RUN/NOT VERIFIED | Только после Linux+Windows pass; dist/EXE, SHA256SUMS, BUILD_INFO |
| GitHub Actions push (research ветка) | DISABLED AUTOMATIC, MANUAL AVAILABLE | workflow_dispatch сохранён; причина Stage111N не выделялись runners |

[CircleCI handoff](STAGE111N_CIRCLECI_FALLBACK_RU.md). Исходная Delphi parity по-прежнему НЕ принята.


## Stage111O — восстановление оригинального MouseMove

| Элемент | Статус | Подтверждение / ограничение |
|---|---|---|
| `pbAdcMouseMove` | SOURCE_VERIFIED + IMPLEMENTED_TESTED | `_Unit128:0084B4AC`, текущая вкладка «Временной сигнал» использует Qt sigMouseMoved; временная ось оригинала не сверена |
| `pbSpectrumMouseMove` | SOURCE_VERIFIED + IMPLEMENTED_TESTED | `_Unit128:0084C918`, Qt обновляет полную FFT-серию при движении X, без клика |
| Пропуск повторного целого X | SOURCE_VERIFIED + IMPLEMENTED_TESTED | `_Unit115:007CA75C`, отдельные Qt-координаты, но не настоящий PixelLeft/Right Delphi |
| Оригинальный GDI XOR / clGreen | SOURCE_VERIFIED STRUCTURE, PIXEL PARITY TODO | `_Unit115:007CA793–7B0`: цвет 0x00008000, pmXor=14, восстановление pmCopy=4; Qt InfiniteLine не соответствует оригинальному пиксельному результату |
| Кэш Time GetSignal | IMPLEMENTED_TESTED CANDIDATE | Без повторного чтения ZIP каждый пиксель; AC/AC+DC/reversed; входная ориентация оригинального TQGrapher не доказана |
| Неподтверждённая огибающая / 2 ряда | FAIL-CLOSED / TODO | Без фантомного второго ряда, без подмены FIR/OG |
| CI Stage111N | VERIFIED SYNTHETIC | Код 11f022925a407495d7bf4b3b7dcb94b21afe7ced, CircleCI [Linux #15](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/15), [Windows/Qt #16](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/16), [EXE #17](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/17): SUCCESS |
| CI Stage111O | VERIFIED SYNTHETIC | Код aa3a0dd0a11e9821dfbfd350f16dfbb8bcc19fde, CircleCI [Linux #30](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/30), [Windows/Qt #31](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/31), [EXE #32](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/32): SUCCESS |

**Не закрыто:** настоящий Delphi FormatFloat/RTL/x87, Font/DPI, Canvas, оригинальные BIN/FFT/спектральные показатели на одном окне и пользовательская приёмка. [Stage111O](STAGE111O_ORIGINAL_MOUSEMOVE_CURSOR_RU.md).


## Stage111P — GDI XOR raster / source-derived pixel behavior

| Совместимость | Статус | Доказательство / непроверенное |
|---|---|---|
| `TPen.Color=clGreen`, `TPen.Mode=pmXor` и возврат pmCopy | SOURCE_VERIFIED STRUCTURE | Приватный `_Unit115:007CA793–007CAB03`, enum VCL `0x0E/0x04`; GDI mode 7 проверен по Win32 документации |
| Порядок erase-old-X → erase-old-Y0/Y1 → draw-new-X/Y | SOURCE_VERIFIED STRUCTURE + IMPLEMENTED_TESTED CANDIDATE | `core/tqgrapher_gdi_xor_idr_candidate.py`; независимая 1/2-line state machine, same X no-op |
| `LineTo` конечный пиксель исключается | WIN32_SOURCE_VERIFIED + IMPLEMENTED_TESTED | Документ Microsoft, синтетический RGB XOR-пиксельный тест, Windows GDI on host test; исходный Delphi Canvas parity TODO |
| Win32-native R2_XORPEN vs raster candidate | IMPLEMENTED_TESTED, ORIGINAL PARITY TODO | `tests/test_tqgrapher_gdi_xor_win32.py`, CreateDIBSection/MoveToEx/LineTo; Windows Core+Qt CI PASS; это **НЕ оригинальное окно MVKView** |
| Приватная before/after bitmap сверка | IMPLEMENTED_TESTED DIAGNOSTIC | `gdi_xor_reference_compare.py` с ограниченными локальными .npy + JSON, SHA256/ошибки без raw pixels; оригинальный эталон не предоставлен |
| Перенос XOR на реальный Qt PlotWidget | TODO | Qt InfiniteLine пока работает как исследовательская UX-линия, GDI/Canvas/Font/DPI реальные пиксели НЕ приняты |
| Stage111P CI | SYNTHETIC LINUX + WINDOWS CORE/Qt + EXE SUCCESS | Program SHA `38a895fd797e300fbc967f7e97700828c4330106`; [Linux #39](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/39) SUCCESS, [Windows Core+Qt #40](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/40) SUCCESS, [EXE #41](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/41) SUCCESS (hash of downloaded artifact not independently verified) |

[Технический отчёт](STAGE111P_GDI_XOR_RASTER_RU.md). Все проверки synthetic/offline, никакого original Pascal/IDP/BIN или реального прибора в CI. Оригинальный x87/FormatFloat/FFT/FRange и пиксельный parity ещё TODO.


## Stage111Q — исходная регистрация PaintBox, шрифтов и полос прокрутки

| Возможность | Уровень / результат | Доказательство и что ещё не принято |
|---|---|---|
| Margin двух исходных TPaintBox | SOURCE_VERIFIED + IMPLEMENTED_TESTED | _Unit128:0084B40F–42D, 0084C840–864: min(Width div 53, Height div 30), потом минимум 10 (_Unit115:007CA4DB). Qt Canvas-preview исправлен |
| PixelRect и scrollbar anchors | SOURCE_VERIFIED + IMPLEMENTED_TESTED | _Unit115:007CA4E8–007CA62F; _Unit128:0084C8A6–8F8: H Left/Width и V Top/Height, без выдуманных остальных координат |
| TCanvas.TextWidth/TextHeight и TFont.Assign | SOURCE_VERIFIED STRUCTURE; ORIGINAL FONT TODO | _Unit115:007CA4E8–5FA и 007CACE4–CACFC. Новый Win32 GetTextExtentPoint32W инструмент подбирает независимый HFONT, НЕ доказывает исходную гарнитуру MVKView |
| DPI и происхождение Qt | IMPLEMENTED_TESTED DIAGNOSTIC | Qt viewport devicePixelRatioF, logical DPI, QFont family показаны отдельно. Не считать Qt font исходным Delphi |
| Исходные снимки Canvas на нескольких DPI | TODO | Приватные TPaintBox размеры, оригинальные Font/PixelRect/двухрядный CursorString/скриншоты одного окна ещё не предоставлены |
| Stage111Q CI | Linux+Windows SUCCESS; EXE PENDING в момент отчёта | Программный SHA 1baf980e611f55d38618b4dc170e8662089eaf62; [Linux #49](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/49) SUCCESS, [Windows Core/Qt #48](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/48) SUCCESS; фактический Windows Preview EXE/SHA проверять в Artifacts |

[Технический отчёт Stage111Q](STAGE111Q_PAINTBOX_FONT_DPI_RU.md). Реальный Delphi x87/FormatFloat, CursorString, FFT/FRange, GDI XOR пиксели и UX оригинальных трёх вкладок НЕ приняты. Instrument/AUX4700 и main/v0.3.40 не менять.


## Stage111Q — подтверждён проектный DFM (дополнение)

| Проверка | Статус | Подтверждение |
|---|---|---|
| Form design-time Font | SOURCE_VERIFIED DFM STRUCTURE | Приватный mvkform.dfm: Tahoma, Height=-13, Style=[], PixelsPerInch=96; оригинальный DFM не опубликован |
| pbAdc/ pbSpectrum design-time bounds | SOURCE_VERIFIED DFM STRUCTURE + IMPLEMENTED_TESTED | pbAdc 791×740; pbSpectrum 767×716; оба Align=alClient. Margin по исходной формуле равен 14 у обоих при проектных размерах |
| Существующие исходные scrollbars | SOURCE_VERIFIED DFM vs runtime | DFM H.Left=24,Width=553,Height=24; V.Top=0,Width=24,Height=400; исходный Draw позднее переназначает H Left/Width и V Top/Height |
| Получение runtime Font/DPI | TODO | Форма/DFM дизайн не является измерением живого TPaintBox.Canvas; font substitution, Windows DPI и runtime resize ещё не проверены |
| DFM-derived baseline + Win32 Tahoma probe | IMPLEMENTED_TESTED CANDIDATE | Новый tqgrapher_dfm_design_idr_candidate.py и Windows GDI probe на выбранном HFONT, без передачи оригинальных ресурсов |
| Stage111Q latest program CI | Linux SUCCESS, Windows/EXE awaiting | Code SHA d8c44318a09d328ecfd14a3a92f1bb987209999b; [Linux #55](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/55) SUCCESS, [Windows #54](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/54) проверить, Preview EXE/SHA не принят |

[Технический отчёт Stage111Q](STAGE111Q_PAINTBOX_FONT_DPI_RU.md); дальнейшая оригинальная Canvas/RTL/FFT-паритет остаётся неподтверждённым.


## Stage111R — Qt/native Canvas bridge и строгая проверка EXE

| Модуль / свойство | Статус | Проверенное / ограничения |
|---|---|---|
| Исходные Delphi PaintBox/Canvas/Font/DPI | SOURCE_VERIFIED STRUCTURE, RUNTIME TODO | Старый оригинальный _Unit115/_Unit128 и приватный DFM; новый runtime оригинальный TCanvas пока **не измерен** |
| Qt ViewBox→TPaintBox coordinate bridge | IMPLEMENTED_TESTED RESEARCH CANDIDATE | `core/tqgrapher_qt_canvas_bridge_candidate.py`, явные границы Qt/native PixelRect; режим DPR записывается, но не умножает native coordinates; оригинальный паритет FALSE |
| Проверка независимых совпадающих landmark X/Y | IMPLEMENTED_TESTED DIAGNOSTIC | `compare_measured_landmarks` сообщает **только ошибки** и не публикует координаты; без эталона реальной MVKView нельзя считать паритет доказанным |
| Исследовательский GUI Canvas | IMPLEMENTED_TESTED CANDIDATE | Qt показывает scaleX/scaleY с предупреждением. Основные курсоры графиков не подменены предположением |
| Windows Preview PE/EXE/manifest | INTEGRATED FAIL-CLOSED BUILD CHECK | `verify_windows_preview_artifact.py` повторно читает PE и считает SHA256, проверяет BUILD_INFO SHA/branch и SHA256SUMS; `BUILD_VERIFICATION.json` перед `store_artifacts`. Тесты порчи EXE/манифестов |
| Программный Stage111R CircleCI | Linux+Windows PASS, EXE CHECK REQUIRED | Code SHA `aa8e3b87671034636a4a63dc6486d0432c3b72c3`; [Linux #61](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/61) SUCCESS, [Windows Core+Qt #60](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/60) SUCCESS; [EXE #62](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/62) проверить |

Интеграция проверяет **сборочный артефакт внутри CircleCI**, но отдельно скачанный EXE не сверён: `separate_download_integrity_verified=False`. Original Delphi/FFT parity не доказана. [Отчёт](STAGE111R_QT_GDI_REGISTRATION_AND_EXE_INTEGRITY_RU.md).


### Stage111R — безопасная публикация verified-dist (последнее исправление)

**Финальный программный SHA:** `8c9f0d29895a8a2ae68ad09c42e678cfffe01bee`. CircleCI `store_artifacts` выполняется даже после неудачного `run`; публикация непосредственно `dist/` была недостаточно безопасной. Теперь исходный EXE и SHA проверяются, затем файлы копируются в `verified-dist.tmp`, проходят вторую полную проверку, и только после этого atomic rename создаёт `verified-dist`; CircleCI публикует только `verified-dist`. [Linux #64](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/64) SUCCESS; [Windows #63](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/63) итог проверить, EXE job после Core. **Побитовая проверка скачанного EXE и original Delphi parity всё ещё не подтверждены.** См. [Stage111R](STAGE111R_QT_GDI_REGISTRATION_AND_EXE_INTEGRITY_RU.md).

## Stage111S — восстановлены статические таблицы оригинальной MVKView

| Таблица оригинала | Статус | Результат |
|---|---|---|
| gvar_008D3428, H масштаб Tag 0..9 | SOURCE DATA VERIFIED + GUI CANDIDATE | 25600,12800,6400,3200,1600,800,400,200,100,50 Гц. bSpecHScale QToolButton имеет 10 source-пунктов; Qt H позиция абсолютная в Гц |
| gvar_008D3450, NFFT Tag 0..5 | SOURCE DATA VERIFIED, ORIGINAL FFT PARITY TODO | 262144,131072,65536,32768,16384,8192. В исходном меню шесть значений; текущие исследовательские 1024/4096 сохранены только ради коротких синтетических архивов |
| gvar_008D3468, физический Y divisor | SOURCE DATA VERIFIED, GUI APPLY TODO | 1,10,100,1000,10000,100000; оригинальные пользовательские единицы/dynamic GraphDefaultVScale ещё требуют сверки |
| gvar_008D3480, dB Y PageSize | SOURCE DATA VERIFIED, GUI APPLY TODO | 150,100,75,50,25,10; восстановлено в core, но Qt V scrollbar остаётся исследовательским |
| native H source scroll vs Qt | SOURCE STRUCTURE VERIFIED, IMPLEMENTED_TESTED CANDIDATE | Full=25600; VCL Max=Full−1, PageSize=Hz; Qt effective max=Full−Page, сохраняется native integer Position. Точная регистрация исходного PaintBox не измерена |
| CI original table/popup package | Linux SUCCESS; Windows Qt/EXE CHECK | Code SHA af036bdd1be4dfdf2481a416f73cc9759db355d4; [Linux #75](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/75) SUCCESS, [Windows/Qt #76](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/76) SUCCESS; [EXE #77](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/77) PENDING |

Приватные исходники и IDP не публиковались; только производные числовые константы и тесты. Это не доказательство Delphi x87/FFT/Canvas/CursorString. [Stage111S report](STAGE111S_SOURCE_SPECTRUM_SCROLLBARS_RU.md).

## Stage111T — источник dB/physical Y-Page и оригинальные шесть NFFT

| Возможность | Статус / исходное подтверждение | Что реализовано / что НЕ доказано |
|---|---|---|
| V mSpecVScale1Click full/page dB | SOURCE VERIFIED (_Unit128:0084C5DB–0084C607) | Full=150, Page=[150,100,75,50,25,10], исходные 6 Tag; native Qt ScrollBar хранит Source Position/Page/Max |
| V mSpecVScale1Click physical Y | SOURCE VERIFIED (_Unit128:0084C609–0084C652) | Full=100000, Page=100000/divisor, div=[1,10,100,1000,10000,100000]; 6 Tag; исходный ScrollBottom вычисляется в core |
| mSpecType1Click source default | SOURCE VERIFIED (_Unit128:0084C560–0084C597) | При dB сброс Tag=0, при остальных типах Tag=3; Qt V menu перестраивается |
| Qt Y viewport от original source V | IMPLEMENTED_TESTED **CANDIDATE** | Применяются source Page/Position и формулы, но `GraphDefaultVScale` и базовая шкала Y ПОКА из локального Qt; original Delphi runtime Y pixel parity=FALSE |
| bSpecLines оригинальные NFFT | SOURCE TABLE VERIFIED + IMPLEMENTED_TESTED | Шесть исходных пунктов: 262144,131072,65536,32768,16384,8192; Research 1024/4096 только явно отмеченные, не original |
| Достаточность настоящей BIN/FIR истории | IMPLEMENTED_TESTED OFFLINE FAIL-CLOSED | Недоступные NFFT отключены, нет нулевого дополнения. `fft_source_archive_gate`, `required_original_history` для частной огибающей; 4096→8192 запрещён, архив с 8192 реальными сэмплами разрешён |
| Stage111T CI | Linux/Windows Qt PASS, EXE PENDING | SHA `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`; [Linux #79](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/79) SUCCESS. [Windows Core+Qt #78](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/78) SUCCESS, [EXE #80](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/80) PENDING, downloaded SHA256 separately unverified |

Синтетические/CI тесты не подтверждают Delphi FFT/GetSpectrum/FRange/FormatFloat/x87, оригинальные TPaintBox Font/DPI/PixelRect или фактический GraphDefaultVScale. [Полный отчёт](STAGE111T_VERTICAL_AND_SOURCE_FFT_RU.md).


## Stage111U — источник GraphDefaultVScale и приватная численная сверка

| Компонент | Источник / статус | Точное условие приёмки |
|---|---|---|
| GraphDefaultVScale для спектра | **SOURCE STRUCTURE VERIFIED**, `_Unit128:0084B5D3–B882` | Исходный `TMvkChannelStorage.FRange` ×1(dB/acc) / ×10(velocity) / ×100(displacement), затем log10/TRUNC, Single и сравнение с log10(2)/log10(5); исходные x87 math-helper побитовые результаты НЕ измерены |
| FRange выбранного канала | Конструктор `_Unit115:007D0A61` **source verified** | Начальное FRange=1.0f; фактическое значение канала после конфигурации/обработки ещё НЕ подтверждено. UI FRange остаётся ручным/исследовательским |
| Нормализация «красивой» шкалы | IMPLEMENTED_TESTED **CANDIDATE** | `core/spectrum_graph_default_vscale_idr_candidate.py`: Single staged simulation vs независимое Decimal 1–2–5 ceiling; граничные 2/5 могут расходиться, поэтому `original_math_helpers_x87_rounding_verified=False` |
| Qt Spectrum Y/GraphDefault | GUI DIAGNOSTIC; ORIGINAL PIXEL PARITY FALSE | В GUI показан исходный кандидат по ручному FRange и отдельная Qt data-derived ось. Не подменять исходные пиксели Y без golden original |
| Частный numeric oracle | OFFLINE IMPLEMENTED_TESTED | `graph_vscale_reference_compare.py` принимает локальные mode/FRange/original GraphDefault и возвращает только агрегатную ошибку, без оригинальных значений, имён файлов или сетевых запросов |
| Stage111U regression | LOCAL 37 PASS, LINUX+WINDOWS QT PASS, EXE PENDING | Code SHA `a2a0651903c04638bc08fb983a415563df74c7f4`; [Linux #85](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/85) SUCCESS, [Windows Qt #84](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/84) SUCCESS, [EXE #86](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/86) PENDING; downloaded hash separately unverified |

[Stage111U technical report](STAGE111U_GRAPH_DEFAULT_VSCALE_RU.md). Stage111T code `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`: Linux #79, Windows Qt #78, EXE #80 SUCCESS. Эти CI-прохождения не делают независимую скачанную копию EXE сверенной и не подтверждают настоящий Delphi x87/Canvas/FFT паритет.


## Stage111V — x87 power/log10 helpers и влияние control word

| Объект | Уровень восстановления | Необходимое подтверждение |
|---|---|---|
| 00447DB8 log10(Single) | SOURCE INSTRUCTIONS VERIFIED | FLDLG2/FLD Single/FYL2X, возвращает x87 Extended, не эквивалент Python math.log10 по всем битам |
| 00447DF0 Power Extended, 00447EF8 Power Single | SOURCE INSTRUCTIONS VERIFIED | Целочисленная ветвь и FLDLN2/FYL2X/F2XM1/FSCALE восстановлены; окончательная битовая идентичность Delphi 32-bit ещё не принята |
| System.@FpuInit 00409570 и x87 CW | SOURCE STRUCTURE VERIFIED | FLDCW читает исходную глобальную переменную 008C2028; конкретное значение в работающем ORIGINAL процессе пока неизвестно |
| Native GCC x87 selftest | IMPLEMENTED, LOCAL SYNTHETIC 27 VALUES | x86/x86_64 GCC, real x87 instructions; результаты согласованы с Python-кандидатом на синтетике; НЕ оригинальные golden |
| x87 precision-control sweep | IMPLEMENTED TESTED 18 SYNTHETIC COMBINATIONS | PC24, PC53, PC64. Для x=2: 4.99999952 против 5.0; для x=20: 49.9999962 против 50.0. Восстанавливает CW после теста |
| Cross-platform Python ULP regression | IMPLEMENTED TESTED | Отдельная проверка соседних float32 ниже/на/выше 2, 5, 10, branch <=0 log10 и 4 режимов спектра |
| Stage111V последний кодовый CI | Linux/Windows Core PASS; EXE проверяется отдельно | Программный SHA f87ea7a38d3d62e1d91479a661b713a69d6bd8bf: [Linux #91](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/91) SUCCESS, [Windows Qt #90](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/90) SUCCESS. Оригинальная Delphi x87 runtime и скачанный EXE SHA256 не приняты |

Исходные PAS/DFM/IDP остаются приватными. Декодирование source-структуры и локальный тест на другом CPU/CW не дают фактического Original Delphi parity. [Отчёт Stage111V](STAGE111V_X87_MATH_HELPER_RU.md).

## Stage111W — исходное FPU CW 0x1332: проверено по самому IDP

| Составляющая | Статус | Источник / ограничение |
|---|---|---|
| `.data` VA008C2028 = `0x1332` | **SOURCE STATIC BYTES VERIFIED** | Приватный `mvkview.idp`, IDR v3: 11 сегментов, `.data` VA008C2000, RAW offset 004C1128; WORD расположен на 004C1150. Сам IDP не коммитился |
| `@FpuInit`, `Set8087CW`, `Get8087CW` | **SOURCE OPCODE VERIFIED** | В тех же приватных исходных секциях инструкции 00409570, 00407664, 00407674 прямо ссылаются на 008C2028 |
| Режим x87 при **исходной** инициализации | **SOURCE VERIFIED, RUNTIME TODO** | 0x1332: PC64, RC-nearest, exception mask 0x32. `Get8087CW` во время работы может отличаться после вызова `Set8087CW` |
| `TMvkChannelStorage.FRange` | **CONSTRUCTOR SOURCE VERIFIED, SELECTED CHANNEL TODO** | Конструктор 007D0A61 присваивает Single 1.0. Фактическое FRange выбранного канала/реального архивного измерения не установлено |
| Native hardware `FLDCW(0x1332)` | **IMPLEMENTED SYNTHETIC, ORIGINAL RUNTIME TODO** | Тестовый CPU вернул 0x1372 после FNSTCW, reserved bit6; PC/RC остаются исходными; 28 synthetic combinations с восстановлением caller CW |
| x87 log10(1000) vs Python float64 | **INDEPENDENT LOCAL COUNTEREXAMPLE** | Synthetic mode3/FRange10: x87 2000, Python candidate 1000. Нельзя подменять результат без original Delphi golden; GUI подсвечивает опасные целые декады |
| Stage111W regressions | **LOCAL 79 PASS; LINUX/WINDOWS QT PASS; EXE PENDING** | Программный SHA `080dcddbb65a8d199ea444ac9ae8d3676ac5e57f`, [Linux #93](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/93) SUCCESS, [Windows Qt #94](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/94) SUCCESS, [Windows EXE #95](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/95) ещё проверяется |

[Технический отчёт Stage111W](STAGE111W_ORIGINAL_STATIC_FPU_CW_RU.md). **Границы:** исходный статический WORD и opcode не доказывают реальный runtime control word; локальный x87 тест не доказывает Delphi GetSpectrum/FFT/Canvas/FormatFloat parity; скачанный EXE не проверен независимо.

## Stage111X — FPU control-flow и приватный битовый golden

| Объект | Статус | Точное описание |
|---|---|---|
| Direct `Set8087CW` | **SOURCE STATIC VERIFIED** | 3 прямых code-aligned `CALL rel32`: `0041BD84`, `0041BDDA`, `00448296`. Первые два — сохранение/восстановление CW через внешний вызов; третий — только 6 младших битов exception mask |
| Direct `Get8087CW` и `@FpuInit` | **SOURCE STATIC VERIFIED** | 4 прямых Get и 5 прямых FpuInit в исходных `.text/.itext`; не доказывают отсутствия непрямых вызовов |
| Парсер чисел `0042EBC8` | **SOURCE STATIC VERIFIED** | Временное `FLDCW [008C45F0]` = `0x133F`, PC64/RC-nearest/mask 0x3F; `0042EBC1` сохраняет и `0042EC68` восстанавливает прежнее CW |
| Runtime CW при спектре | **NOT VERIFIED** | В `.data:008C2028` источник `0x1332`, но текущее CW непосредственно до `0084B631` не измерено. Не приравнивать исходный файл к оригинальному runtime |
| Private original audit | **OFFLINE IMPLEMENTED+TESTED** | `private_x87_callsite_audit.py`; проверка исходного приватного IDP локально, без копирования байтов/путей в отчёт и GitHub |
| Runtime numeric golden contract | **OFFLINE IMPLEMENTED+TESTED, REAL GOLDEN TODO** | `private_x87_runtime_reference_compare.py`: Single FRange+Y в hex, runtime CW и mode; агрегаты по ULP/PC/RC; происхождение реального снимка не аутентифицируется автоматически |
| Stage111X регрессия | **100 LOCAL PASS, LINUX+WINDOWS CORE PASS; EXE PENDING** | Code SHA `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`, [Linux #97](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/97) SUCCESS, [Windows Qt #96](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/96) SUCCESS, [Windows Preview EXE #98](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/98) PENDING |

**Значимое ограничение:** исходный x87-код и его статические прямые вызовы — не доказательство работы с реальными приборами, Delphi FPU CW в конкретной сессии, побитовой FFT/FormatFloat или координат Canvas. [Отчёт Stage111X](STAGE111X_ORIGINAL_X87_CALLSITES_AND_GOLDEN_RU.md).

## Stage111Y — исходный Windows EXE и IDR3 доказанно относятся к одному коду

| Проверка | Статус | Основание |
|---|---|---|
| Original EXE identity | **PRIVATE PE32 VERIFIED** | SHA256 `585bcd4aeafa14d77780d4c74134ee98c1653df1dc37a2d2d4db7904754435c5`, PE x86, базовый VA 00400000, 18.08.2021 12:51:58Z |
| PE `.text` vs IDR `.text` | **BYTE IDENTICAL** | 4 969 156 байт сравнены, 0 расхождений |
| PE `.itext` vs IDR `.itext` | **BYTE IDENTICAL** | 11 844 байта сравнены, 0 расхождений |
| PE `.data` vs IDR `.data` | **BYTE IDENTICAL** | 76 596 байт сравнены, 0 расхождений |
| Runtime breakpoint source | **SOURCE VERIFIED** | До rounding `0084B631`, после `0084B882` (RVA 0044B631/0044B882). FRange channel +0x04, output `[ESI+0x62C]` |
| Original Windows x87 CW/FRange/Y | **NOT YET MEASURED** | Подготовлен x32dbg script и private golden capture kit, ожидаются 2 снимка оригинала на сохранённом офлайн-измерении |
| Предыдущая CI | **3/3 SUCCESS** | Stage111X программный SHA `0d1c36f4...`: Linux #97, Windows Qt #96, EXE #98 SUCCESS |

[Stage111Y технический отчёт](STAGE111Y_ORIGINAL_EXE_IDENTITY_AND_RUNTIME_CAPTURE_RU.md). **Отсутствие live runtime наблюдений нельзя заменять совпадением секций EXE/IDP**. EXE/IDP/архив и пользовательские оригинальные данные не публиковать.


## Stage111Z.3 — источник x87 Spectrum GraphDefaultVScale (30.10.2026)

| Узел | Подтверждение | Оставшийся барьер |
|---|---|---|
| Original Spectrum source handler + 3 math helper | **SOURCE-VERIFIED** SHA256 приватного IDP в `0084B5D3..0084B882`, `00447DB8`, `00447DF0`, `00447EF8` | Нельзя считать статическую реконструкцию полным runtime parity |
| Source mode FRange | **SOURCE-VERIFIED** Tag0/1/2/3 = ×1/×1/×10/×100; 8 FSTP Single в scale field | Фактический FRange других архивов неизвестен |
| Оригинальные 4 режима runtime | **OPERATOR-REPORTED GOLDEN** (Stage111Z); нативный source-derived x87 при CW1372 совпал 4/4 битово | CW других 3 режимов отдельно не измерялся, другие FRange и границы TODO |
| Оригинальные пограничные 2/5/10/1000 | **UNVERIFIED**; Python vs native x87 известное различие на 1000 | Нужен оригинальный офлайн golden; без него не менять рабочую Qt Y-ось |
| Privileged source audit | **IMPLEMENTED + SYNTHETIC TESTED** `private_spectrum_x87_path_audit.py` | Полный original IDP только локально, не в CI |

[Отчёт Stage111Z.3](STAGE111Z3_SOURCE_SPECTRUM_X87_AUDIT_RU.md) · [Источник runtime Stage111Z](STAGE111Z_FIRST_RUNTIME_X32DBG_GOLDEN_RU.md). Цель остаётся: автономная Windows-программа, не Web.


## Stage111Z.4 — FFT исходная точность и знак (30.10.2026)

| Функция | Статус | Примечание |
|---|---|---|
| Спектральный FFT wrapper и знак | **SOURCE-VERIFIED** | GetSpectrum по 007D2083 вызывает +2π (007CC3F8); противоположный wrapper 007CC404 отдельно |
| Twiddle recurrence Single-store | **SOURCE-VERIFIED + IMPLEMENTED_TESTED** | temp real записан Single на 007CC325; imaginary intermediate НЕ записывается; Wi/Wr final Single на 007CC33A/007CC344 |
| Hann × Sample, DC running mean | **SOURCE-VERIFIED STRUCTURE** | Исходные окна SHA сверены, но битовое совпадение runtime Hann и sinus table пока TODO |
| FFT Float32 power | **SOURCE-DERIVED CANDIDATE + SYNTHETIC TESTED** | После source-aligned intermediate округления синтетика изменилась; настоящий Delphi FFT/архивный спектр всё ещё TODO |
| Private FFT auditor | **IMPLEMENTED + SYNTHETIC TESTED** | Семь локальных SHA fingerprint; IDP/EXE/измерения не в CI |

[Stage111Z.4 технический отчёт](STAGE111Z4_ORIGINAL_FFT_TWIDDLE_SINGLE_STORE_RU.md) · [Известный runtime scale golden](STAGE111Z_FIRST_RUNTIME_X32DBG_GOLDEN_RU.md).


## Stage111Z.5 — original Hann FFT window (30.10.2026)

| Узел | Статус | Основание и следующий шаг |
|---|---|---|
| Runtime Hann generator | **SOURCE-VERIFIED** по 5 SHA оригинального IDP | .itext 008C1064: 262144 Float32, x87 FCOS/FSQRT, 2π Extended и деление sqrt(1.5); actual CW at init still unknown |
| Таблица Hann BSS | **SOURCE-VERIFIED STRUCTURE, RUNTIME BITS TODO** | base `0096DA48`, берётся каждый `262144/N` элемент; original Win32 memory нужно считать через x32dbg |
| Синтетический native x87 oracle | **IMPLEMENTED/TESTED, NOT DELPHI GOLDEN** | полный N=262144: 4 × 1 ULP расхождения против NumPy на i=1,5,262139,262143; N<=131072 power-of-two локально совпадает |
| Исходный Python Hann/FFT в приложении | **CANDIDATE, НЕ ПОДМЕНЕН** | ожидать четыре runtime Single HEX из original; нет автоматической смены максимальных N |
| Private IDP Hann audit | **IMPLEMENTED + SYNTHETIC CI TESTED** | пять code/const SHA и helper/call/stride/final Single, без original content в CI |

[Отчёт Stage111Z.5](STAGE111Z5_HANN_SOURCE_AND_X87_PROBE_RU.md) · [Stage111Z.4 FFT](STAGE111Z4_ORIGINAL_FFT_TWIDDLE_SINGLE_STORE_RU.md).


## Stage111Z.6 — оригинальные Hann runtime Float32 (30.10.2026)

| index | Оригинал x32dbg | Source-derived native x87 | Existing NumPy | Статус |
|---:|---|---|---|---|
| 1 | `2F80EF9C` | `2F80EF9C` | `2F80EF9D` | **USER-REPORTED ORIGINAL RUNTIME VERIFIED FOR THIS POINT** |
| 5 | `31C97664` | `31C97664` | `31C97663` | **USER-REPORTED ORIGINAL RUNTIME VERIFIED FOR THIS POINT** |
| 262139 | Не снят | `31C97664` (гипотеза) | `31C97663` | **TODO original x32dbg** |
| 262143 | Не снят | `2F80EF9C` (гипотеза) | `2F80EF9D` | **TODO original x32dbg** |

Исходные наблюдения относятся к **отдельным коэффициентам**, а не к полной таблице или к FFT output. Нужно снять `dword:[A6DA34]` и `dword:[A6DA44]`; после подтверждения выполнить адресную коррекцию для N=262144, не затрагивая остальные размеры. [Отчёт Stage111Z.6](STAGE111Z6_ORIGINAL_HANN_RUNTIME_TWO_POINT_GOLDEN_RU.md).


## Stage111Z.6 — полный комплект четырех original Hann runtime точек (30.10.2026)

| Индекс original Hann | DWORD из x32dbg | Native x87 CW1372 | NumPy до исправления | Статус в кандидатном приложении |
|---:|---|---|---|---|
| 1 | `2F80EF9C` | `2F80EF9C` | `2F80EF9D` | **PATCHED EXACT BIT** |
| 5 | `31C97664` | `31C97664` | `31C97663` | **PATCHED EXACT BIT** |
| 262139 | `31C97664` | `31C97664` | `31C97663` | **PATCHED EXACT BIT** |
| 262143 | `2F80EF9C` | `2F80EF9C` | `2F80EF9D` | **PATCHED EXACT BIT** |

Четыре значения подтверждены оригинальной работающей MVKView (со слов оператора), не CI. Для FFT N<262144 эти нечётные индексы не используются; вне четырёх точек NumPy кандидатный массив **не аттестован**. Текущая реализация в `mvk_compatible/core/fft_idr_candidate.py`, строгие тесты в `mvk_compatible/tests/test_stage111z6_original_hann_runtime_golden.py`. [Итоговый отчёт Stage111Z.6](STAGE111Z6_FOUR_HANN_RUNTIME_GOLDEN_PATCH_RU.md). Следом Stage111Z.7 — численные original GetSpectrum/bin parity.


## Stage111Z.7 — оригинальные точки захвата FFT и компаратор (30.10.2026)

| Участок | Статус | Эталон / блокер |
|---|---|---|
| Original GetSpectrum preFFT `007D153D` | **SOURCE-VERIFIED** (4 private IDP code-window SHA) | `[ebp-2C]` = N × Float32 после DC и опциональной огибающей; original dump TODO |
| Original FFT complex `007D2088` | **SOURCE-VERIFIED STRUCTURE, OPTIONAL CAPTURE TODO** | `[[ebp-8]+48]` = N пар Re,Im Float32; origin Win32 не снимался |
| Original postFFT power `007D154B` | **SOURCE-VERIFIED** | в исходном buffer `N/2` Float32 powers до интегрирования режима и логарифмирования; original dump TODO |
| Python `private_getspectrum_power_compare.py` | **IMPLEMENTED/SYNTHETIC TESTED**, источник оригинальной пары ПОКА НЕ ПОЛУЧЕН | Вход: два .bin + private JSON, optional complex .bin; выход только bitwise/ULP/aggregate error; `remove_dc=False`; не аттестует Delphi |
| Read-only original capture source audit | **IMPLEMENTED + SYNTHETIC CI TESTED** | `private_getspectrum_capture_source_audit.py` четыре original SHA-окна, проверка rel32 calls, Float32 store, mode/N/ptr |

[Stage111Z.7 отчёт](STAGE111Z7_GETSPECTRUM_FFT_PREPOST_CAPTURE_RU.md) · [Операторская инструкция x32dbg](STAGE111Z7_X32DBG_FFT_POWER_CAPTURE_RU.md). Следом Stage111Z.8: **Оригинальная** runtime пара и сравнение нескольких режимов на одном архиве.


## Stage111Z.8 — оригинальная пользовательская ненулевая FFT power пара (30.10.2026)

| Элемент | Статус | Содержание |
|---|---|---|
| Original-claimed `before_fft(1).bin` | **OPERATOR-SUPPLIED NONZERO CAPTURE**, no independent process provenance | N262144 Float32, перед source Hann/FFT, повторное DC удаление выключено |
| Original-claimed `after_power(1).bin` | **OPERATOR-SUPPLIED NONZERO CAPTURE**, same invocation not independently authenticated | 131072 Float32 мощности, без mode integration/логарифмирования |
| Source-derived `idr_float32` | **BITWISE MATCHES THIS PAIR 131072/131072, MAX ULP=0** | Первый нетривиальный полный FFT power golden для одного user-reported оригинального capture, **не** universal Delphi parity |
| NumPy `rfft` | **733/131072 exact** | Высокая спектральная корреляция, но побитовое отличие в 130339 power bins |
| Старый twiddle без intermediate Single | **4068/131072 exact** | Демонстрирует роль исправления Stage111Z.4; не основной текущий алгоритм |
| Четыре Hann edge patches | **SOURCE-REPORTED ORIGINAL BITS PATCHED**, на этой паре power не изменяются | Важны для точной таблицы, но этим capture их влияние на FFT power не доказано |
| Raw pair comparator без manifest | **IMPLEMENTED + SYNTHETIC CI TESTED** | `private_getspectrum_raw_pair_compare.py`: проверка input quality, bitwise/ULP, нет угадывания метаданных и raw values в отчёте |

[Отчёт Stage111Z.8](STAGE111Z8_FIRST_NONZERO_ORIGINAL_FFT_262144_BITWISE_GOLDEN_RU.md). NEXT — независимые capture с другим FFT N, затем оригинальный GetSpectrum OutputMean/Peak и TQGrapher.


## Stage111Z.9 — original summary fields, source and runtime (31.10.2026)

| Узел | Статус | Подтверждение и следующий блокер |
|---|---|---|
| Original GetSpectrum summary code | **SOURCE-VERIFIED** по 6 SHA окон приватного IDP | `007D17E7..007D1900`, band lower/upper, Double sum, strict max, weighted ±2, Single outputs |
| Power sum & mean | **SOURCE-VERIFIED STRUCTURE; RUNTIME GOLDEN TODO** | `[EBX+30]` Single, FRange исходного канала, x87 sqrt; нет живого оригинального DWORD |
| Weighted peak X | **SOURCE-VERIFIED STRUCTURE; RUNTIME GOLDEN TODO** | `[EBX+34]` Single в BIN; raw пользовательский peak ≈15200.1455 (hex `466D8095`) — лишь CANDIDATE до настоящего x32dbg |
| Peak Y | **SOURCE-VERIFIED STRUCTURE; RUNTIME GOLDEN TODO** | `[EBX+38]` Single, сумма пяти бинов и FRange |
| Post-mode summary power | **CAPTURE SITE VERIFIED, USER DATA TODO** | `007D17E7` N/2 Float32, режимы 2/3 меняют power после `007D154B` |
| Private summary triplet compare | **IMPLEMENTED + SYNTHETIC TESTED** | `private_getspectrum_summary_triplet_compare.py`, strict JSON/filename/IEEE754, 3 ULP metrics; никогда не выдавать synthetic match за оригинальный runtime |
| Original source structural auditor | **IMPLEMENTED + SYNTHETIC TESTED** | `private_getspectrum_summary_source_audit.py`, private IDP read-only, 6 SHA windows |

[Полный Stage111Z.9](STAGE111Z9_GETSPECTRUM_ORIGINAL_SUMMARY_AUDIT_AND_COMPARE_RU.md) · [Инструкция оригинального x32dbg](STAGE111Z9_X32DBG_SPECTRUM_SUMMARY_CAPTURE_RU.md). Далее original 3 output DWORD + Fs/FRange/Tag/N в одной сессии; не менять Qt core без оригинальной численной сверки.


## Stage111Z.10–Z.11 — original GetSpectrum summary full triplet & Copy text (01.11.2026)

| Узел | Статус | Основание / открытый блокер |
|---|---|---|
| Original Tag0 OutputMean | **OPERATOR ORIGINAL X32DBG + SOURCE CANDIDATE 0 ULP** | `[EBX+30]`=`40DC8F5E`, N262144 Fs65536 FRange`43FF4853` |
| Original Tag0 OutputPeakX | **OPERATOR ORIGINAL X32DBG + SOURCE CANDIDATE 0 ULP** | `[EBX+34]`=`466D8095`; FFT бин 15200.1455078125, не Гц |
| Original Tag0 OutputPeakY | **OPERATOR ORIGINAL X32DBG + SOURCE CANDIDATE 0 ULP** | `[EBX+38]`=`3F475279`, Single |
| Original post-mode summary power | **OPERATOR CAPTURE CROSSCHECK 131070/131072** | `summary_power.bin` vs прежний `after_power(1).bin`: бины 0,1 → 0, остальные 131070 одинаковы |
| Summary source code | **UNCHANGED SOURCE-DERIVED FORMULA** | три побитовых совпадения на одном реальном operator-claimed случае; не обобщать на другие режимы, x87 border, архивы |
| Private Stage111Z.10 regression | **PUBLIC METADATA TESTS + OPT-IN ORIGINAL PRIVATE DUMP TESTS** | `test_stage111z10_original_summary_runtime_golden.py`; нет original raw files в CI |
| Delphi bSpecCopyValue TAB и 007B2090 | **SOURCE STRUCTURE VERIFIED, ORIGINAL CLIPBOARD RUNTIME TODO** | `private_spectrum_copy_runtime_compare.py` сравнит оригинальную строку с `spectrum_triplet_text` без повторного FFT; текущее `6,89<TAB>3800<TAB>0,7786` только ПРОГНОЗ |

[Stage111Z.10 полный отчёт](STAGE111Z10_GETSPECTRUM_ORIGINAL_SUMMARY_3OF3_RU.md) · [Stage111Z.11 Original Copy Text](STAGE111Z11_ORIGINAL_COPY_TEXT_REGRESSION_GATE_RU.md). Дальше настоящий original Clipboard, CursorString, точные графические подписи и GDI/Qt сравнение.


## Stage111Z.12 — оригинальная Copy selection vs backend summary (01.11.2026)

| Узел | Статус | Обоснование / следующий шаг |
|---|---|---|
| Две оригинальные Clipboard-строки | **OPERATOR-REPORTED ORIGINAL TEXT**, NOT SAME AS PREVIOUS BACKEND | Два соседних спектра: `6,15 / 19,93 / 6,096` и `5,57 / 19,94 / 5,522`; формат TAB 3/4/4 совместим с source |
| Original Copy selection `0084EADC` | **SOURCE-VERIFIED** 3 SHA private IDP windows | Выбор record: single-pane index0, иначе текущий index control; именно выбранный record копируется |
| Original Copy record `0084BC8C` | **SOURCE-VERIFIED, RUNTIME DWORD TODO** | ESI = Form EBX+0x908+index*72; `ESI+30` mean, `+34` peak bin, `+38` peak Y |
| Original graph XScale Copy | **SOURCE-VERIFIED, RUNTIME DWORD TODO** | `dword:[dword:[dword:[ebx+FF4]+40]+14]`, не использовать слепо Fs/N другого GetSpectrum call |
| Формат 007B2090 | **SOURCE VERIFIED 3/4/4; FULL RTL TEXT PARITY TODO** | У оригинальных соседних чисел нет согласованных Single input DWORD для побитовой RTL сверки |
| Новый same-click comparator | **IMPLEMENTED + SYNTHETIC CI PASS** | `private_spectrum_copy_selected_record_compare.py`, source audit + tests; без FFT/BIN, только 4 original DWORD + TXT |

[Stage111Z.12](STAGE111Z12_COPY_SELECTED_RECORD_SOURCE_AND_TWO_OPERATOR_TEXTS_RU.md) · [x32dbg инструкция](STAGE111Z12_X32DBG_COPY_SELECTED_RECORD_RU.md). Дальше снять одну Copy кнопку с 4 DWORD, подтвердить строку, курсоры и Canvas; сохранять ранее установленные численные FFT/summary доказательства без повторной подгонки.


## Stage111Z.14 — original screenshot visual reference (01.11.2026)

| Проверяемый элемент | Статус | Оригинальный evidence / Qt action |
|---|---|---|
| Original Spectrum screenshot | **OPERATOR-REPORTED ORIGINAL RUNTIME PNG; DERIVED REFERENCE** | 1920×1080, полный PNG хранится приватно, не в GitHub/CI; вкладка «Спектр» |
| Original plot cursor position | **SCREENSHOT-CONSISTENT <1 px** | Plot global `L605,T193,R1639,B911`; observed magenta `X758,Y458`; from 3800Hz/−55.32dB prediction `X758.484375,Y457.7984` |
| Original graph X domain | **SCREENSHOT-CONFIRMED THIS CASE** | DataSize=102400, XScale=.25, last data bin25599.75Hz, **axis endpoint 25600Hz**, not 32768Hz Nyquist |
| Original log Y axis and cursor hint | **SCREENSHOT-CONFIRMED TEXT, NOT RAW INTERNAL FLOAT32** | Y 0..−150dB; `3800 Гц`, `−55,32 дБ`; separate physical summary `6,89;3800;0,7786 м/с2` |
| Source GDI XOR color model | **SCREENSHOT COLORS + PREVIOUS SOURCE STRUCTURE CONSISTENT** | `clGreen (0,128,0)` XOR white `(255,255,255)` → `(255,127,255)`; over black → `(0,128,0)` |
| Standalone Qt Spectrum line | **FIXED COLOR TO BLACK**, CI code SHA `5bab4e26` Linux/Win Core PASS | Previously teal `#176c92`, now black `#000000`; no UI parity claimed |
| Standalone Qt plotted X axis | **FIXED AXIS-END MODEL**, CI code SHA `5bab4e26` Linux/Win Core PASS | UI uses `grapher_axis_end_frequency_hz` 25600 while retaining original 102400 data bins |
| Original top task tab caption | **QT TEXT FIXED** | Source screenshot shows `Задачи`, not prior Qt `Расчётные данные`; newest CI needs separate verification |
| Original vs Qt screenshot pixel parity | **TODO** | Need same archive/session & same screen size Qt 1920×1080 image with cursor 3800Hz, compare plot rect / font/DPI / line and axes |
| Same-click original Copy 3/3 | **REGRESSION PUBLISHED** | `tests/test_stage111z13_original_same_click_golden.py`, only 4 Single words and three visible columns; no original binary assets |

[Полный Stage111Z.14](STAGE111Z14_ORIGINAL_SPECTRUM_SCREENSHOT_PIXEL_REFERENCE_RU.md). Следом Stage111Z.15 — одна сравнительная Qt screenshot или native CursorString/PixelRect original x32dbg от того же окна для точной GDI/Qt совместимости.


## Stage111Z.15 — перенос на GitHub Actions (01.11.2026)

| Блок | Статус | Основание |
|---|---|---|
| GitHub Actions availability | **CONFIRMED Linux manual** | `offline_static_checks` 12s SUCCESS, 01.11 |
| Stage111 workflow on default main | **YAML INSTALLED, NO PRODUCT SOURCE CHANGES** | `.github/workflows/stage111-desktop-offline.yml`, manual UI discoverability; runs gated to research ref |
| Stage111 Linux all core | **GitHub Actions run #161 SUCCESS** | SHA `685b4119...`, `linux-core`, full core pytest |
| Stage111 Windows Core+Qt | **FIRST RUN IN PROGRESS at initial poll** | `desktop-windows`, offscreen Qt; verify final run #161 |
| Stage111 verified Windows EXE artifact | **BUILD QUEUED behind both test jobs; not published yet** | PyInstaller + independent PE/SHA twice, `BUILD_INFO` source commit and branch; upload only verified |
| CircleCI | **MANUAL BACKUP, AUTO DISABLED** | `run_circleci_backup=false` default, switch true via CircleCI API only when required |
| Qt current UI screenshot | **USER OBSERVED CLIPPED LEFT PANEL, TODO** | Distinct dataset from original screenshot; not a valid Qt/Delphi pixel diff yet |
| Original BIN/TSXML direct open | **TODO next Stage** | Current Desktop preview expects Native R6.1 export ZIP; user wants original no-conversion archives |

[Отчёт GitHub Actions migration](STAGE111Z15_GITHUB_ACTIONS_CI_MIGRATION_RU.md) · [Первый workflow run #161](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41282496457). Next verify actual artifact availability, then resume UI/layout and original source parity work.


## Stage111Z.16 — самостоятельный BIN/TSXML и GUI (01.11.2026)

| Функция | Статус | Границы и источник |
|---|---|---|
| Direct local BIN + TSXML | IMPLEMENTED + SYNTHETIC LINUX/WIN PASS | Строгий Single Float32 little-endian, DataOffset/DataLength/Frequency, SHA256; нет универсального original-format decoding |
| Multi ADC one recording | IMPLEMENTED + SYNTHETIC PASS | Только распознанные MVK...-ADC имена одинаковых serial/timestamp, прочие файлы не примешивать |
| R6.1 Native ZIP | UNCHANGED, TESTED | EXPORT_AUDIT + VALUES/AUX SHA required как раньше |
| Original DSP on direct BIN | UNAVAILABLE BY DESIGN | Нельзя синтезировать DSP/третьоктавы, табличные приборные значения явно отсутствуют |
| Physical calibration for direct BIN | NOT VERIFIED | Source Single заявлен как uncalibrated/unknown, число на графике не объявлять м/с² без FRange эталона |
| Qt Spectrum left panel | IMPROVED, WINDOWS QT TESTED | 244px + wrap + no horizontal scroll; pixel-exact original DFM geometry не заявлена |
| GitHub Actions new Preview | LINUX/WINDOWS QT SUCCESS, EXE BUILD PENDING | [Run 41283560470](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41283560470), source SHA 8a36077d |
| FFT source-derived original goldens | PRESERVED | Прежний Stage111Z.8 131072/131072 power и Z.10 OutputMean/Peak 3/3 одного оригинального захвата, алгоритм не менялся |

[Stage111Z.16 полный отчёт](STAGE111Z16_DIRECT_BIN_TSXML_QT_SIDEBAR_RU.md). NEXT — пользовательский real BIN/TSXML и Qt-side-by-side screenshot.


## Stage111Z.16 — финальное подтверждение CI и артефакта

**Stage111Z.16 — ОКОНЧАТЕЛЬНО ПОДТВЕРЖДЁННЫЙ GITHUB ACTIONS WINDOWS EXE (01.11.2026):** run 41283560470, source commit SHA **8a36077da1f0bf5df5c4ea4337d26895f202c8a2**, workflow COMPLETED/SUCCESS, все три job SUCCESS: Linux all offline core; Windows Core+Qt; Windows verified autonomous EXE. Артефакт GitHub Actions **MVKViewCompatible_Stage111_Windows_Preview**, ID **13074248511**, 66 970 774 байт, не истёк; PyInstaller EXE, SHA256SUMS.txt, BUILD_INFO.txt, BUILD_VERIFICATION.json. **[Скачать новый EXE из Artifacts](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41283560470)**. Исследовательская ветка source code и doc-only handoff commits различаются: именно source SHA 8a36077d... был собран и протестирован. CircleCI остаётся ручным резервом. Следом протестировать конкретные оригинальные BIN+TSXML, НЕ заявлять универсальную поддержку форматов или проверенную физическую калибровку.



## Stage111Z.17 — полный UI/UX-аудит оригинала vs Qt, без изменения программного кода

Источник: оригинальный приватный mvkform.dfm (только прочитан локально; SHA256 192c0ebaf1bf722292a9b64497493a1de6af52a4bf8ffbe2ea28d0fe0b68c2d4), скриншот пользователя MVKView 1.0.47 и Qt исходники Stage111Z.16. Исходные DFM/PNG в GitHub НЕ публикуются. **18 задач: P0=2, P1=10, P2=6**. Это аудит, а не новая Qt сборка.

| Функция/экран | Original MVKView | Текущий Qt | Гейт / следующий этап |
|---|---|---|---|
| PageStart «Задачи» | Большие кнопки действий (connect/view/settings), только 3 видимые вкладки на screenshot | Крупная DSP таблица под названием «Задачи» | P1, Stage111Z.19: offline start, DSP оставить внутри |
| Spectrum controls | 5 кнопок меню + 2 label + Copy + Save, pnSpecTools177px | 35 stack.addWidget в левой колонке 244px (Z16) | **P0 Stage111Z.18:** только 9 первичных, исследования в expandable Inspector |
| Spectrum labels | Без фильтра, Логарифмич., 1/4 Гц/лин, 25600 Гц, 150 дБ | Коды 0…3, NFFT, Горизонталь+/Вертикаль+ и provenance | P1 Z18: фактические active captions и 3/4/4 Copy candidate |
| Cursor and info | 3800Hz/-55.32dB, отдельные СКЗ6.89/peak3800/0.7786 в одном оригинальном состоянии | verbose debug text, orange InfiniteLine | P1 Z18/Z20: короткий info и оригинальный XOR overlay, не менять FFT |
| Calibration/direct BIN | Original physical metrics требуют источник и калибровку | Direct BIN Single может быть структурно valid без verified physical units | **P0 Z18:** без fake физического статуса в UI/Copy/CSV |
| Time signal | Исходные 4 кнопки и две величины слева; PageAdc; условный pnView | Горизонтальные исследовательские controls, другой выбор времени | P1 Z19 |
| Screenshot Qt-vs-original | Original screenshot 1920×1080, plot rect/crosshair известны | Последний user Qt screenshot был ДО Z16, другой архив/scale | **NOT VERIFIED** pixel parity; сравнить лишь при same data/DPI |
| Режим офлайн | Device pages исходной DFM — отдельная функциональность | Нет аппаратных команд; direct BIN/R6.1 ZIP есть | Без fake hardware, никаких сетевых команд |
| Последний verified EXE | — | Stage111Z.16 run41283560470 Linux/WindowsQt/EXE SUCCESS | Z17 docs-only, НЕ объявлять новый EXE |

[Stage111Z.17 аудит](STAGE111Z17_UI_UX_AUDIT_ORIGINAL_VS_QT_RU.md) · [18 пунктов JSON](STAGE111Z17_UI_UX_AUDIT_BACKLOG.json) · [ТЗ Z18](STAGE111Z18_SPECTRUM_COMPATIBILITY_UI_IMPLEMENTATION_PLAN_RU.md). Сохранять source-derived FFT 131072/131072 и 3/3 original Copy/summary goldens, не возвращать Web и не изменять main.



## Stage111Z.18–Z.20 — integrated UI/UX fixes and main development return (02.11.2026)

| Block | Status | Evidence / Remaining |
|---|---|---|
| P0 Spectrum primary panel | **CODE IMPLEMENTED + WINDOWS QT PASS** | 9 source-ordered controls, original 177px sidebar, research QDock keeps all prior controls, no primary scrolling at 1024x704 |
| P0 direct BIN calibration | **CODE IMPLEMENTED + CORE/WIN PASS** | Explicit condition/consent before Copy, extra source warning, CSV uncalibrated header and append incompatibility guard |
| Tasks PageStart offline | **CODE IMPLEMENTED + QT PASS** | Offline start with Open/Signal/Spectrum/metrics, original DSP tables retained; no spoofed connect/IP/calibration |
| Waveform panel | **CODE IMPLEMENTED + QT PASS** | 4 original-inspired primary controls at 177px, wave research dock, source GetSignal models unchanged |
| Spectrum Hz/line and ranges | **CODE IMPLEMENTED + QT PASS, VISUAL ORIGINAL PARITY TODO** | Fs/N caption, source Tag0 25600Hz X / 0..−150dB Y display default; other modes/source windows to compare |
| GDI XOR spectrum cursor | **SOURCE-BASED QPAINTER RASTEROP + QT TEST PASS; ORIGINAL PIXEL PARITY TODO** | clGreen XOR white→magenta, black→green, uses raw FFT Y/selected bin without new FFT calculation |
| Original source-derived FFT + summary | **UNCHANGED** | Earlier single-user capture FFT 131072/131072 and summary 3/3 preserved; UI changes do not alter core FFT |
| CI Linux / Win core / Qt | **SUCCESS** | [GitHub Actions run 41376521808](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41376521808): Linux 899 passed/3 skipped, Windows 900 passed/2 skipped, Qt 34 passed |
| New Windows EXE | **VERIFY FINAL ARTIFACT** | Source SHA b6a2f7018af36ca13b69dbd6437ddb9bcfe56c50, PyInstaller job was in-progress at first review |
| Remaining UI UX items | **TRACKED OPEN/PARTIAL** | 9 code-implemented, 5 partial, 4 open; same-data/dpi screenshot, full time scroll, source fonts/grid, worker/cache |

[Полный отчёт](STAGE111Z20_UI_UX_FIXES_AND_MAIN_TRACK_RETURN_RU.md) · [Актуальный backlog](STAGE111Z17_UI_UX_AUDIT_BACKLOG.json). Следующая ОСНОВНАЯ задача — аттестация настоящих BIN/TSXML и восстановление FRange/Source measurement chain без Web или реального прибора.


## Stage111Z.20 — verified Windows EXE release gate

**FINAL VERIFIED CI BUILD (02.11.2026):** source SHA b6a2f7018af36ca13b69dbd6437ddb9bcfe56c50, [GitHub Actions #41376521808](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41376521808) COMPLETED/SUCCESS, все 3 jobs SUCCESS: Linux 899 passed, 3 skipped, 30 subtests passed; Windows Core 900 passed, 2 skipped, 30 subtests passed; Windows Qt GUI **34 passed**. Windows verified autonomous EXE artifact **MVKViewCompatible_Stage111_Windows_Preview** создан, **ID 13111233765**, ZIP **66 985 239 байт**, ещё не истёк. Содержит MVKViewCompatible_Stage111_PREVIEW.exe, SHA256SUMS.txt, BUILD_INFO.txt, BUILD_VERIFICATION.json. PE/SHA проверены через Windows Actions; реальный исходный app original screenshot pixel parity требует отдельной пары изображений. **Все исправления Stage111Z.18–Z.20 собраны в этой версии.**



## Stage111Z.21–Z.22 — original TSXML source calibration and independent original FFT memory proof

| Компонент | Статус | Основание |
|---|---|---|
| Original TSXML writer | **SOURCE-VERIFIED STATIC** | _Unit125.pas 00806A8C; CP1251; DataLength BYTES, DataOffset0; Single ADC/Byte Count; per-channel gain from GetFloatByAddr(0x0E) |
| Original BIN reader metadata | **SOURCE-VERIFIED STATIC + SYNTHETIC CI** | _Unit128.pas 0084622E..4655E; InternalChannelGain Single → FRange; fallback vs no ApplyRange, original runtime BIN physical domain still unknown |
| DirectBinSession | **IMPLEMENTED + CI CORE/WIN PASS** | CP1251/full/minimal, exact DataFileName/channel matching, no wrong-ADC, strict NaN/Inf, Byte not accepted as acceleration |
| Byte original channel | **METADATA INSPECTION ONLY** | Read-only CLI; no false time-acceleration/FFT for 8-bit counter bytes |
| Direct BIN physical FRange | **STATIC CANDIDATE ONLY** | TSXML gain visible in inspector; no automatic multiplication; no same-run original BIN→FRange runtime verification |
| Independent original FFT power | **REAL ORIGINAL INPUT/OUTPUT + NUMPY COMPARED** | N262144→131072, Hann RMS, original peak bin15200 50461.0078125 vs NumPy 50460.99609375; <=0.1% 120308/131072, <=1% 130241/131072; only 721 bitwise matches |
| Original exact Float32 FFT parity | **SEPARATE PRIOR SOURCE-DERIVED EVIDENCE, NOT VERIFIED BY NUMPY** | Preserve prior Stage111Z8/10 goldens and special single store twiddles |
| Privacy/source evidence | **VERIFIED PRIVATELY** | Projects.7z PAS and user FFT files remain local; public repo only aggregate/source locations+SHA and synthetic CI fixtures |
| GitHub Actions after core code | **LINUX+WINDOWS+QT PASS; EXE NEEDS FINAL VERIFICATION** | [Run 41378515208](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41378515208), source SHA 808aa9, core 935 Linux/936 Windows, Qt35 |

[Source report](STAGE111Z21_ORIGINAL_TSXML_GAIN_FRANGE_SOURCE_RU.md) · [Independent original FFT report](STAGE111Z22_ORIGINAL_FFT_MEMORY_PAIR_INDEPENDENT_REFERENCE_RU.md). **Next Stage111Z.23**: actual original BIN+TSXML same-run storage and GetSignal/GetSpectrum, trace TmpStream aliasing; never reintroduce Web.


## Stage111Z.23 — original native live BIN memory alias (02.11.2026)

| Source element | Verified scope | Consequence |
|---|---|---|
| Storage.AllocBufferChunk (007D1B08) | ORIGINAL STATIC IDR | Возвращает ptr внутреннего Float32 ring buffer |
| TRecordMemoryStream.FMemory = ptr (008020A8) | ORIGINAL STATIC IDR | Нет второй копии; SetSize также не аллоцирует другую память |
| TIdIOHandler.ReadStream → stream.Write | ORIGINAL STATIC IDR | Пишет frame по тому же ptr |
| Storage.ProcessBufferChunk(true), Float32 | ORIGINAL STATIC IDR | In-place single multiply на Storage.FRange |
| ChannelFile.Write(TmpStream.FMemory) | ORIGINAL STATIC IDR | Сохраняет изменённый массив после scaling при активной записи |
| Точный original runtime Storage.FRange | **NOT VERIFIED** | Требуется same-run x32dbg и channel source provenance |
| Original BIN vs TCP one-session bytes | **NOT VERIFIED** | Не утверждать полный runtime byte-parity |
| Windows stage Z21/Z22 | **3 JOBS SUCCESS** | [Actions 41378916106](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41378916106), artifact 13112990057, 66992754 bytes |

[Stage111Z.23 full analysis](STAGE111Z23_ORIGINAL_LIVE_BIN_POINTER_ALIAS_FRANGE_RU.md). Stage111Z.24 focuses on all runtime writes to FRange and same-session capture, without changing earlier FFT/UI correctness.
