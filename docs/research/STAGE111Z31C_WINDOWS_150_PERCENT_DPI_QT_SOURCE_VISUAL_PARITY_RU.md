> **ACTUAL OPERATOR GUI CANVAS DIAG RECEIVED 05.11.2026:** user supplied two original private PNG 1920x1080 (not committed), `2026-11-05_10-17-53.png` SHA256 `25587a06d833ef1b9cb187c4ccdbe1b1adf88b66da9c773bfcaa93b480d47173` shows Tag0 and open research dock; `2026-11-05_10-18-08.png` SHA256 `b672d84bb64680c94f1ad0cf9755ee9cfd8cd6bad1a25b588c68f38fb7a22a5c` shows the Qt `TQGrapher Canvas — только исследовательская геометрия` modal at Windows 150%. **Actual observed Qt info:** virtual canvas **789x522** (Qt units), source-derived margin **14** from min(W/53,H/30), resulting source-derived predicted PixelRect **L68 R775 T14 B464**, candidate `itosM=0.00690429704`, `itosC=68`, `stoiM=144.837341`, `stoiC=0`, `ytosM=-3`, `ytosC=14`; source-scroll candidates H.Left68/H.Width707, V.Top14/V.Height450. Qt font **Segoe UI**, `devicePixelRatioF=1.5`, `logicalDpiX/Y=96/96`. Original **DESIGN-TIME DFM ONLY**: `Tahoma Height=-13`, `PPI=96`, `pbSpectrum=(767,716)` — NOT measured original TPaintBox runtime. Qt→TPaintBox bridge **candidate** `scaleX=0.964134733`, `scaleY=0.934967796`, **NOT calibrated actual Delphi runtime**. Right Research dock open reduces available Qt spectrum viewport; do **not** directly compare 789x522 with the separate original StageZ14 runtime plot 1034x718, or assert a 1.5 direct source scale. Underlying original x32dbg Tag0 and original summary still confirmed screenshot `3800Hz / -55.32dB`, `SKZ6.89 / peak3800Hz / amp0.7786`, `3/3 original HEX`. **Geometric diagnostic task is DONE**; no more x32dbg dumps/screen captures needed NOW. Next practical source-layer work: disentangle Qt viewport/logical/device physical px and original Delphi TCanvas at user scale 150%, check fonts/ticks/grid & plot layout with dock open/closed separately. UI inspector still says `TSXML/FRange: источник не открыт` and shows independent research FRange=1.0 even when original Y reference has `FRange Single bits 43FF4853` — this may confuse users; **label research TSXML FRange distinct from x32dbg reference FRange in future UX audit**, not an error in verified Tag0 Float32 math. Do not publish PNG or private Power/Y.

> **FINAL verified autonomous Windows artifact, 05.11.2026:** [Actions run 41957719091](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41957719091) **SUCCESS in all three jobs** at exact tested source commit `fa31934ca4ab610d697c5fe3c675e000a83c7dc0`: Linux Core PASS; Windows Core 1251 PASS/4 SKIP/30 subtests; Windows ordinary Qt 49 PASS; explicit `QT_SCALE_FACTOR=1.5` actually measured `devicePixelRatioF()=1.5` and all 8 Qt original-reference tests PASS. Embedded Native Go R6.1 build/test PASS, PyInstaller onefile and separate integrity verification PASS. [Download artifact #13383069495](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41957719091/artifacts/13383069495) (GitHub ZIP size 68494424B), inside `MVKViewCompatible_Stage111_PREVIEW.exe` size 68493074B SHA256 `571b797291034db73efcac7262a8133e00912691b66c04426257b97063751b4f`, plus `SHA256SUMS.txt`, `BUILD_INFO.txt`, `BUILD_VERIFICATION.json`. GitHub ZIP artifact digest `bfc5800caf83307402d30d1eceb0a1252e1bfb4e240a67390418a65e5383e850`. Link to the artifact is GitHub, no EXE copied to this chat; previously uploaded actual user spectrum BINs remain private.

# Stage111Z31C — Windows масштаб 150%, DPI-aware визуальная проверка и исправления компактной панели

**Дата:** 05.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. Продукт — автономный Windows MVKView Compatible; не Web/main. Оператор уточнил, что масштабирование Windows на ЭТОМ текущем скриншоте оригинального x32dbg Tag0 в Qt равно **150%**.

## 1. Что уже фактически доказано

Изображение Qt пользователя 05.11.2026: 1920×1080 **физических пикселей**, в программе открыт настоящий операторский **Tag0 x32dbg original full Y** (`N=262144, Fs=65536, FRange=43FF4853`); UI подтверждает `131072/131072` полный Float32 Y, `1/4 Гц/лин`, `25600 Гц`, `150 дБ`, курсор `3800 Гц / −55.32 дБ`, а кнопки Copy/Save отключены. Предыдущий original Win32 MVKView screenshot Stage111Z14 с тем же исходным спектром также 1920×1080 физических пикселей, оригинальные надписи и данные совпадают. Это свидетельствует о корректной **численной** части Tag0 и локальном отображении курсора. Исходный оригинальный PNG и приватный RAW в GitHub не публикуются.

**Важная коррекция исследования:** пользователь сообщил Windows scale **150%**, но для старого исходного Delphi-скриншота отдельное значение Windows DPI awareness/Virtualization и прежний scale независимо не зафиксированы. НЕЛЬЗЯ утверждать, что 1517 px Qt plot против 1034 px оригинала обязательно «ошибка отступов», «здесь стоит 100%», или что одномоментное деление Qt width на 1.5 доказывает parity. Qt PySide6 и 32-bit VCL могут различаться по DPI-awareness.

Вместо абсолютных глобальных координат сравнивать **нормализованные позиции относительно своих видимых plot rectangles**, пока оба окна не выровнены по реальной DPI-aware Qt/Delphi canvas geometry.

### Уже полученная геометрия по оригинальному случаю (приближённые границы screenshot)

| | Оригинал MVKView StageZ14 | Qt оператор 05.11 |
|---|---|---|
| Plot border (физические PX) | L605 T193 R1639 B911 | L393 T195 R1910 B919 |
| Размер (физические PX) | 1034×718 | 1517×724 |
| Cursor global X / Y | 758 / 458 | 618 / 462 |
| `(cursorX−left)/width` | 0.1479690522 | 0.1483190508 |
| `(cursorY−top)/height` | 0.3690807799 | 0.3687845304 |

Указанные величины подразумевают приблизительную границу Qt Plot по PNG и округлённые UI координаты, **не прямой readback ViewBox/TPaintBox bounds**. Разница нормализованной позиции при переносе в размер Qt составляет около **0.53 px X / 0.21 px Y**, без предположения об одинаковой ширине/шрифтах или DPI. Уже достаточно близко для курсорной геометрии при данном размере; **не** доказательство пиксельной идентичности всей кривой, сетки, TCanvas pen, antialias и tick labels.

### Цвета XOR

Для Qt снимка подтверждены RGB magenta `(255,127,255)` на белом и green `(0,128,0)` на чёрном. Ранее те же два цвета наблюдались на оригинальном MVKView StageZ14. `pmXor` цветовое поведение принято на этих двух случаях. Другие цвета/pixel modes не аттестованы.

## 2. Исходные code-level UX изменения Stage31C

На скриншоте Qt текст главной левой панели от `ОРИГИНАЛ x32dbg` был 4+ lines и почти упирался в кнопку Copy, а длинный topbar `ЭТАЛОН x32dbg · Tag0 · N262144 · АЦП эталона не подтвержден` выходил за правую границу. Вместо принудительного изменения размеров графика:

1. В режиме загруженного original X/Y теперь topbar короткий `ЭТАЛОН x32dbg · Tag... · N... · АЦП ?`, полное предупреждение о непроверенном канале/исходном окне/калибровке вынесено в tooltip. После возврата к архиву прежний title и tooltip восстанавливаются.
2. Левая панель при наличии оригинальных **3 summary HEX** показывает ровно 4 короткие строки `СКЗ: 6,89`, `Пик: 3800 Гц`, `Ампл.: 0,7786`, `Ориг. HEX: 3/3` — это числа исходного операторского GetSpectrum, а не новые физические измерения, единицы НЕ удостоверены.
3. При отсутствии исходных `summary_hex` в JSON подпись показывает `Нет HEX: из Power`, **не** фиктивное 3/3. Внешние утверждения про физическую калибровку/сохранённые исходные значения запрещены.
4. Технические полные Y/Power/N/FRange остаются в исследовательском Qt доке и tooltip, а не вытесняют главные поля.
5. Изменения не касаются исходных измерений/FFT/интегратора/Tag0..3 Float32, Native Go R6.1/PCAPNG, main/Web или прошивки.

## 3. Подтверждено именно на Qt масштабе 150%

Веточный workflow `.github/workflows/stage111-desktop-offline.yml` дополнен независимым Windows шагом `Test original-reference Qt panel and cursor at 150 percent DPI`:
- `QT_QPA_PLATFORM=offscreen`, `QT_SCALE_FACTOR=1.5`;
- отдельный запуск Qt проверяет `QWidget.devicePixelRatioF()==1.5` и **фактически выводит `Qt effective DPR = 1.5`**;
- отдельный запуск `pytest test_stage111z31a_qt_original_reference.py`: **8/8 PASS**, включая отсутствие переполнения QLabel (QFontMetrics), реальный plot/cursor test, оригинальный title/tooltip и возврат на archive/no archive.

[Actions run 41957719091](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41957719091): Windows Core **1251 PASS**, Windows обычный Qt **49 PASS**, Windows Qt simulated DPI150 **8 PASS**; Linux Core PASS. На момент первичной записи документа EXE artifact job ещё выполняется, итог и SHA надо проверить отдельно. Это проверка **Qt high-DPI simulation**, не настоящего Delphi runtime и не аппаратного прибора.

## 4. Что будет дальше

Никаких новых x32dbg оригинальных GetSpectrum захватов для Tag0..3 не требуется. Следующая приёмка:
- operator запускает Qt сборку С ДАННЫМ CODE Stage31C из verified GitHub Actions; открыть приватный `Tag0/MVK_TAG0_x32dbg_reference.json` (парный x32dbg Power/Y из ранее подготовленного ZIP);
- проверить четыре компактные строки, полный summary 6,89/3800/0,7786, crosshair 3800Hz/−55.32dB, что `Copy/Save` disabled;
- при необходимости нажать `Исследование → Геометрия Canvas` (в инспекторе) и записать **actual Qt devicePixelRatioF/logicalDpi/viewport** при физическом Windows scale150. Это НЕ оригинальная Delphi PixelRect, а отдельный измеряемый Qt слой;
- для истинного original-vs-Qt пиксельного diff далее проверить original Delphi DPI-awareness/pixel geometry, matching plot rectangle, сетку, ticks, font metrics, canvas offset и rendering. Не компенсировать «150%» произвольным множителем оси X/Y или изменением амплитуд.

**Итог:** Stage31C исходные 4-модные Y полностью численно приняты на пользовательских захватах; source/Qt эти текущие 150%-регрессии прошли; оригинальный GDI↔Qt pixel-perfect full parity по-прежнему **OPEN**.
