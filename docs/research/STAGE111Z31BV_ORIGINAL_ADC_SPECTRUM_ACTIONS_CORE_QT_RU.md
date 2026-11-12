# Stage111Z31BV — функциональные обработчики PageAdc / PageSpectrum

**Цель:** один функциональный пакет ядра и Qt, восстановление оригинальных событий, не новый цикл сравнения FFT/PNG.

## Оригинальные источники (приватные)

Операторский Projects.7z / Projects/mvkform.dfm и Projects/_Unit128.pas:
- PageAdc: tcAdc, pnAdcTools (4,6,177,756), pbAdc (8,8,791,740); четыре кнопки по 162×41 (y=9,56,103,150). Обработчик pbAdcMouseMove 0084B4AC вызывает ADCGrapher.UpdateCursor(Canvas, X). Исходный Delphi не блокирует его для огибающей.
- PageSpectrum: tcSpectrum, pnSpecTools (4,6,177,756), pbSpectrum и пять меню; bSpecCopyValue (9,464,162,41) и bSpecSaveValue (9,511,162,41).
- 0084EADC выбирает активный канал как 0 в исходном Mode1 либо tcSpectrum.TabIndex. Нельзя копировать прошлый ADC или пиксельный курсор вместо результата канала.
- bSpecCopyValueClick 0084BC28: текущий канал — поля OutputMean (+0x30), OutputPeakX (+0x34) умножить на SpecGrapher.Series.XScale, OutputPeakY (+0x38). Три числа через TAB, формат 3/4/4 знака.
- bSpecSaveValueClick 0084BD7C: путь edLibraryPath + SPEC-FREQ-yyyy-mm-dd.csv; новый файл начинается sep=| и трёхпольным локализованным заголовком, каждый клик добавляет три поля, разделитель |, CRLF. Оригинальные строки TLanguage и Win32 кодировка НЕ аттестованы.
- pbSpectrumMouseMove 0084C918 передаёт X в SpecGrapher.UpdateCursor, Y не используется.

## Реально восстановленный автономный Core

Новый core/original_adc_spectrum_actions.py: OriginalSpectrumAction проверяет текущие BIN SHA, ADC, режим, NFFT, VALUES tick, полные N/2 FFT и Float32 произведение OutputPeakX*XScale. clipboard_text выдаёт три подтверждённые локальные цифры с TAB. spectrum_source_daily_path/append_source_spec_freq_csv реализуют источник имени и поведение source grammar sep=| + 3 поля + CRLF + append, независимый readback/SHA. Нельзя дописывать в чужой или исходный vendor CSV. Для Direct BIN без подтверждённой физической калибровки исходно выглядящий SPEC-FREQ заблокирован, сохраняется только явно исследовательский CSV.

Также OriginalEnvelopeCursor использует **полный ф32 массив после FIR**, настоящий output Fs и SHA. Изменение core/offline_export.py передаёт полные отфильтрованные отсчёты только В ПАМЯТИ для cursor: графический LOD больше не подменяет реальные отсчёты. По-прежнему нельзя выдавать относительное время выходного буфера за доказанное Win32 абсолютное время.

## Рабочий Qt

desktop/main_window.py: исходные bSpecCopyValue и bSpecSaveValue связаны с тем же GetSpectrum, АЦП и выбранной записью, что отображены на графике. Копирование действительно пишет буфер обмена; сохранение пишет дневной CSV в явно выбранный на PageStart каталог edLibraryPath или открывает Save As. pbAdcMouseMove показывает реальный отсчёт FIR при Code 1..31, не запрещает курсор, если исходные коэффициенты загружены и источник проверен. Переход к новому АЦП/BIN или к обычному GetSignal сбрасывает прежний курсор.

## QA / Windows

Новые синтетические Core и Windows Qt DPI150 тесты проверяют source triplet, FFT/ADC и source tick, TAB, SPEC-FREQ по дням/append/отказ чужого файла, FIR hover из полного обработанного сигнала при прореженном графике, расщепление калиброванного Native ZIP / Direct BIN. Интеграционный тест проходит все семь исходных страниц и три исходные формы (основная, mvkeditform, WindowManForm). Ни один приватный оригинальный объект не публикуется.

## Ограничения

Точная Win32 исходная кодировка, TLanguage строки, Delphi RTL FloatToStr и 1:1 GDI/Canvas, x87 0 ULP для всех режимов и живой аппаратный TMVKThread НЕ доказаны. Новые действия только локальные и не отправляют команды МВК. Следующий функциональный пакет — реальные ADC H/V source menus, завершение целого маршрута операторской работы; для приборной записи отдельно требуется подтверждённый протокол и разрешение.
