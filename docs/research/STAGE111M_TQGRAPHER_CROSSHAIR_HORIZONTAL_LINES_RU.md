> **STAGE111M — ПРОВЕРЕННАЯ ОФЛАЙН-РЕГРЕССИЯ И EXE (29.10.2026).** [GitHub Actions #40900170911](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40900170911) завершён **SUCCESS** на проверенном SHA `ba5efaf3e868365a58edaa828bdfbb7953f45fdd`: Linux Core **368/368 PASS**, Windows Core **368/368 PASS**, Windows Qt **14/14 PASS**. Windows PyInstaller Preview EXE с SHA256SUMS собран и опубликован; artifact `MVKViewCompatible_Stage111_Windows_Preview`, ID **12908104701**, ZIP **66 517 855 байт**, срок до **12.11.2026 15:21:59 UTC**. Синтетические/offline тесты НЕ доказывают идентичность оригинальной MVKView (Delphi TCanvas/font/DPI/x87, реальный Original CursorString и BIN-окно не аттестованы). По завершении этого исходного SHA редактировались только docs вне `mvk_compatible` и workflow; проверенный исполняемый код не менялся. Штатные AUX4700, прибор, `main` и v0.3.40 не затронуты.

# Stage 111M — исходный TQGrapher Crosshair: две горизонтальные линии

Дата 29.10.2026. Ветка research/stage111-mvkview-desktop-20261029. Цель — независимое исследование оригинальной Windows MVKView в автономной Qt-программе. Полный Delphi численный/визуальный паритет НЕ принят.

## 1. Прямое доказательство из приватного оригинала

Из пользовательского Projects.7z локально прочитан _Unit115.pas. Исходные PAS/DFM/IDP не загружались в GitHub. В TQGrapher.UpdateCursor (007CA76C–007CAAFB) найдено строгое различие между положением рисуемого перекрестия и отображаемым числом:

- 007CA7B6–007CA7CF: удаление предыдущей вертикальной линии CursorDrawnX, полный PixelTop..PixelBottom.
- 007CA7E8–007CA804: удаление ранее нарисованных горизонтальных линий двух TQGRSeries (у каждой собственное CursorDrawnY).
- 007CA8D4–007CA900: первичный selected FFT bin переводится в координату X через отдельные itosM/C, затем Round, после чего рисуется вертикальная линия.
- 007CA97B–007CA9B7: для каждого активного ряда отдельно определяется signed максимум в диапазоне исходного пикселя. Это НЕ максимум абсолютного значения.
- 007CA9BA–007CA9D3: Single(raw_peak * Series.YScale), затем sub_007CAC18 и Round — позиция горизонтальной линии.
- 007CAC18–007CAC5E: Single(scaled_Y * ytosM + ytosC), clipping PixelTop..PixelBottom; полученная координата независима от Y-текста.
- 007CA9D8–007CA9F0: Canvas.MoveTo(PixelLeft, CursorDrawnY) и Canvas.LineTo(PixelRight, CursorDrawnY), по одному отрезку на ряд.
- 007CA9F3–007CAAE5: лишь ПОСЛЕ рисования линии вычисляется Y-подпись: raw_peak * YScale при CursorAveraging 1, либо sqrt(sum raw_neighbor²) * YScale при averaging 3. Деления на 3 НЕТ.

Следствие: для averaging 3 horizontal line проходит через raw max, а подпись показывает иной показатель. Сводить их в одну Y-coordinate ошибочно и приводило бы к зрительному несовпадению оригинала.

## 2. Новые реальные исходники

- mvk_compatible/core/tqgrapher_crosshair_idr_candidate.py: оригинальные raw-Y horizontal линии, единое source-подобное float32 округление, защита границ, сохранение vertical line, отсутствие изменений исходных массивов.
- mvk_compatible/tests/test_tqgrapher_crosshair_idr_candidate.py: 9 новых синтетических тестов — один/два ряда, signed значения, bottom/top clamp, .5 nearest-even, независимость горизонтальной линии от averaging 3, отказ от overflow или подмены источника.
- mvk_compatible/cursor_reference_compare.py: новые необязательные приватные параметры --horizontal-pixels N или N,M и --y-scale0/1. Для каждой линии показывается только абсолютная ошибка и факт совпадения; ничего не угадывается, оригинальные пиксели, строки и данные не публикуются. При несовпадении exit code 1.
- mvk_compatible/tests/test_cursor_reference_compare.py: новые проверки private CLI, несовпадающего числа рядов и числовых ошибок, небезопасных параметров, отсутствия raw values в отчёте.
- .github/workflows/stage111-desktop-offline.yml: новый тестовый файл добавлен и в Linux, и в Windows Core. Windows Qt и EXE собираются прежними автоматическими шагами.

Новый двухрядный crosshair намеренно не подменяет существующий Qt графический курсор: источник TCanvas Font/DPI/PixelRect и оригинальная временная позиция не подтверждены. Никакого Live TCP/10230, DSP замены AUX4700 или изменения main/v0.3.40.

## 2.1. Функция уже включена в автономную Windows Qt программу

В main_window.py для обычной вкладки «Спектр» добавлен горизонтальный pg.InfiniteLine. При реальном клике на график пользователь теперь видит вертикальную линию выбранной частоты и горизонтальную — по **исходному signed raw FFT[selected_bin]**. При CursorAveraging=3 выводимый текст остаётся отдельно вычисленным RMS соседей, сама горизонтальная линия не перемещается к значению RMS. Проверка выполняется автоматически тестом test_qt_stage111m_raw_horizontal_crosshair_differs_from_rms_label. Актуальная серия одна: **вторую без фактических данных не имитируем**. Пиксельные координаты берутся из Qt, не из оригинального TCanvas, поэтому статус «original Delphi pixel parity» остаётся TODO.

## 2.2. Исходное очищение курсора при выходе за график

Из приватного _Unit115.pas:007CA811–007CA832 подтверждено: когда CursorPos находится слева/справа от PixelLeft..PixelRight, после стирания ранее нарисованных линий оригинал очищает CursorString. В Qt на Stage111M вертикаль и горизонталь теперь скрыты до первого щелчка; при щелчке вне рабочей области обе линии скрываются, сохранённый выбранный бин сбрасывается и появляется нейтральная надпись об отсутствии курсора. Отдельный тест test_qt_stage111m_original_outside_cursor_erases_x_and_y_crosshair подтверждает работу этого события и отсутствие оставшихся линий.

## 3. Как провести оригинальную приватную сверку

На компьютере с оригинальной MVKView необходимо подготовить локальный Canvas Metrics JSON (14 явных параметров), один или два native 1D .npy ряда, оригинальную CursorString TXT, абсолютный CursorPos и измеренные CursorDrawnX и один/два CursorDrawnY. Вызвать:

python -m mvk_compatible.cursor_reference_compare --metrics C:/private/canvas-metrics.private.json --series0 C:/private/series0.private.npy --series1 C:/private/series1.private.npy --reference C:/private/cursor.private.txt --pixel 250 --line-pixel 256 --horizontal-pixels 300,345 --averaging 3 --y-scale0 1 --y-scale1 1 --confirm-same-canvas --report-json C:/private/cursor-diff.private.json

Числа 250/256/300/345 здесь исключительно условные; настоящий эталон не предоставлен. CLI проверяет исходный текст, вертикальный и горизонтальные пиксели, различает число линий, не пытается подгонять масштаб или добавлять отсутствующие отсчёты. В отчёт входят SHA256 и только величины ошибок. Даже при нулевых ошибках внутри синтетики аттестация настоящей Delphi MVKView не заявляется.

## 4. Следующий Stage111N

1. Добиться оригинального одно- и двухрядного эталона того же FFT/временного окна с сохранением точных Canvas/TextWidth/Height/DPI, SampleRate и YScale.
2. Сравнить original CursorString, CursorDrawnX и оба CursorDrawnY через приватный CLI. Только после доказательства координат перейти к подключению нового original_multiseries_cursor и crosshair в графический Qt обработчик.
3. Отдельно работать над Delphi FormatFloat/RTL/x87 и исходными Full-FFT/OutputMean/OutputPeak, а не смешивать с AUX4700.
4. Проверить последний GitHub Actions SUCCESS и Windows EXE SHA; затем сохранить новый handoff и обновить матрицу.
5. Не публиковать исходники оригинальной MVKView, приборные BIN, TSXML, IDP или PCAPNG в GitHub. Stable main и v0.3.40 не трогать.

Статус: SOURCE STRUCTURE VERIFIED, CANDIDATE IMPLEMENTED TESTED; SOURCE FONT/DPI PIXELS, ORIGINAL EXE NUMERIC AND VISUAL PARITY TODO.
