# Stage111 — матрица приёмки точного аналога MVKView (три вкладки)

**Дата:** 29.10.2026. **Состояние:** Stage111C GetSignal NO-ENVELOPE IDR CANDIDATE (FFT Stage111B сохраняется), не MVKView Compatible 1.0. Обновлять при каждом техническом Stage. Базовые документы: ADR Compatibility First, ADR original DSP, Stage81c/d, Stage109, Stage110/110B.

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
| `bAdcEnvelopeType`, `GetAdjustedEnvelopeLength` | TODO | Выявлены таблицы коэффициентов `8CDA58` и квадратурная свёртка `007D1E70`, но коэффициенты и эталон не получены; код явно отвергает `envelope_code>0` вместо имитации |
| Цвета, подписи, СКЗ/среднее и копирование | CANDIDATE + IMPLEMENTED_TESTED | Stage111C: `OutputMean` по оригинальному `GetSignal` фактически СКЗ окна; фиксируем отдельно от DSP/прибора. Оригинальные оси/цвета/экспорт TODO |
| Live/Archive переключение | TODO | Сейчас только завершённый архив ZIP |

## Вкладка «Спектр»

| Функция оригинала | Статус | Условие приёмки |
|---|---|---|
| `PageSpectrum` + 8 ADC | IMPLEMENTED_TESTED | Qt spectrum tab, выбор всех каналов |
| Четыре режима `mSpecType` | CANDIDATE | 0 dB, 1 acceleration, 2 velocity, 3 displacement; IDR счёт не равен принятым оригинальным числам |
| Выбор FFT N 1024..262144 и df | IMPLEMENTED_TESTED | Выбор N и автоматическое уменьшение для короткого ZIP |
| Hann периодическое RMS `1/sqrt(1.5)` | CANDIDATE | Stage81c статическое IDR, NumPy FFT не битово оригинальна |
| FFT backend `TDSXFastFourier` | CANDIDATE + IMPLEMENTED_TESTED | Stage111B: собственный float32 radix-2 с bit reversal и twiddle по `_Unit115`, синтетически против NumPy; **x87 и оригинальный runtime ещё не сверены** |
| 0-й режим dB и `-180` | CANDIDATE | Stage81d/110B: `10*(fn(P)-2*fn(N/2))`; `fn=log10` не подтверждено |
| Безусловное вычитание среднего перед FFT | CANDIDATE + IMPLEMENTED_TESTED | Stage111B: `0x007D14B3→0x007D2344`, f32 running sum, регрессия по DC-offset; не путать с AC-сигналом |
| Нижние FFT-бин(ы): `max(2,round(N/(2fs)))` | SOURCE_VERIFIED + IMPLEMENTED_TESTED | Stage111B `_Unit115` + доказанный Max helper `_Unit114:007B1CF0`; при fs=65536 обнулить 2, в dB −180 |
| FFT IDR float32 / NumPy — два отдельных кандидата | IMPLEMENTED_TESTED | Qt переключатель, сравнение, exact cursor в выбранном backend; не оригинальный DSP |
| Исключение Nyquist `N/2` | IMPLEMENTED_TESTED | В Stage111A исправлено по Stage81d/110B |
| `bSpecLines`, частотное разрешение | CANDIDATE | N/df уже есть, оригинальные пресеты надо сверять |
| `bSpecHScale`/`bSpecVScale`, скроллбары | CANDIDATE | Qt zoom есть, оригинальные пределы/жесты нет |
| Точный курсор FFT-бина | CANDIDATE | Недецимированный локальный FFT; не исходный `TQGrapher.CursorString` |
| `bSpecEnvelopeType`, спектральные фильтры | TODO | Нужны оригинальные обработчики |
| `bSpecCopyValue`/`bSpecSaveValue` | TODO | Не копировать форматированный вывод без принятого эталона |
| Оригинальные подписи/сетка/логарифмическая ось | TODO | Нужны скриншоты / TQGrapher handlers |

## Обязательная последовательность приёмки
1. Проверить Windows Preview, безопасность локального чтения и целостность реального *частного* экспортного ZIP (файлы не публиковать).
2. Сделать скриншоты оригинальной MVKView для всех трёх вкладок и фиксированных настроек; сравнить структуру элементов.
3. Использовать **одинаковый** BIN/окно/N/mode для NumPy кандидата и оригинальной `GetSpectrum`; оценить частоту, амплитуду, log helper, dc/Nyquist, порядок, масштаб и RMS.
4. Переносить в ядро только доказанную семантику; обновлять отдельные тесты и статус матрицы.
5. Не объявлять Compatible 1.0 до закрытия всех обязательных строк; экспериментальные расширения Web отдельно от совместимости.
