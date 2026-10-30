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
| Stage111P CI | Linux+Windows PASS, EXE pending at writing | Program SHA `38a895fd797e300fbc967f7e97700828c4330106`; [Linux #39](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/39) SUCCESS, [Windows Core+Qt #40](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/40) SUCCESS, [EXE #41](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/41) CHECK |

[Технический отчёт](STAGE111P_GDI_XOR_RASTER_RU.md). Все проверки synthetic/offline, никакого original Pascal/IDP/BIN или реального прибора в CI. Оригинальный x87/FormatFloat/FFT/FRange и пиксельный parity ещё TODO.
