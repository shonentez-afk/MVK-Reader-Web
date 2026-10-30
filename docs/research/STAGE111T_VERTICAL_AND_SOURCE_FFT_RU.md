# Stage 111T — оригинальный вертикальный масштаб и FFT по реальной истории BIN

**Дата:** 30 октября 2026  
**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`  
**Программный SHA:** `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`  
**Предыдущий документационный HEAD:** `3c406775681e13b2403db73cae856f6c782e65b3`.

## 1. Контроль предыдущего состояния

Stage111S программный SHA `af036bdd1be4dfdf2481a416f73cc9759db355d4`: [Linux Core #75](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/75), [Windows Core+Qt #76](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/76), [Windows verified-dist EXE #77](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/77) — все **SUCCESS**. Артефакт проверялся **внутри CircleCI** на PE/MZ, SHA256SUMS, commit/branch, скопированные байты и публиковался только через verified-dist. Независимо скачанный пользователем EXE по байтам всё ещё **не сверялся**.

## 2. Исходная Delphi: теперь восстановлены Full/Page вертикальной шкалы и сброс при смене типа

Исследован приватный реконструированный `Projects.7z/_Unit128.pas` (без публикации Pascal/IDP/DFM):

- `0084C5DB–0084C607`: когда `bSpecType.Tag=0` (дБ), оригинальный полный вертикальный диапазон `0x96 = 150`; текущий PageSize — один из `gvar_008D3480 = [150,100,75,50,25,10]`.
- `0084C609–0084C652`: для других типов `Full=0x186A0 = 100000`, а `PageSize=100000/divisor`, где `gvar_008D3468=[1,10,100,1000,10000,100000]`, то есть PageSize `[100000,10000,1000,100,10,1]`.
- `0084C676–0084C748`: при полном размере V полоса скрыта. При увеличении масштаба `Max=Full-1` в VCL, `PageSize=выбранный`, `SmallChange=max(1,PageSize//10)`, `LargeChange=PageSize`; при смене V пресета новая позиция `clamp(OldPos+OldPage-NewPage,0,Full-NewPage)`. В Qt `QScrollBar.maximum=Full-Page`.
- `0084C560–0084C597`: при выборе другого типа спектра оригинал вызывает именно `mSpecVScale1Click`: **Tag=0 для дБ и Tag=3 для остальных единиц** (делитель 1000).
- `0084C789–0084C801`: для дБ `ScrHeight=Page`, `ScrBottom=-Height-Position*Height/Page`; для физических единиц `ScrHeight=GraphDefaultVScale/divisor`, `ScrBottom=GraphDefaultVScale-Height-Position*Height/Page` (правильный порядок x87 FSUBRP установлен в Stage111S).

Полные H(10), NFFT(6), Y-дБ(6), Y-физические делители(6) сверены с приватным `mvkview.idp` на предыдущем этапе. Ни оригинальный исходник, ни приборные коэффициенты, ни промышленные BIN в GitHub не размещались.

## 3. Реализовано в Windows-приложении

1. `core/mvk_spectrum_menu_runtime_idr_candidate.py` — новая самостоятельная чистая модель `source_default_vertical_tag`, `source_vertical_page`, `source_vertical_selection` и `fft_source_archive_gate`. Отказывается от неверных Tag, отрицательных/выходящих за границы позиций и `required_input_samples`, которые нельзя подтвердить реальной историей.
2. `desktop/main_window.py`: `bSpecVScale` теперь **QToolButton с шестью настоящими пунктами**. Для режима 0 показывает дБ, для 1–3 — делители, пересоздаёт пункты при смене типа, восстанавливает соответствующий исходный Tag 0/3. Полоса `sbSpecVScroll` при явном исходном пресете использует целочисленные Full/Page/Position, а не старую фиктивную шкалу Qt 0–1000.
3. Выделен **честный предел совместимости**: исходные Y-диапазоны и ScrollBottom формулы известны, но `GraphDefaultVScale` в работающей оригинальной MVKView, реальный Font/DPI/PixelRect и калибровка уже отрисованного local FFT не приняты. Поэтому Qt отрисовка вычисляет временный `GraphDefaultVScale` по диапазону **локальных данных**, отдельно ставит `qt_original_graph_default_vscale_estimated=True`, `original_delphi_y_canvas_parity_verified=False`; исходной пиксельной идентичности не заявляется.
4. `bSpecLines`: все **шесть исходных NFFT = 262144,131072,65536,32768,16384,8192** теперь реально присутствуют в выпадающем выборе. Исследовательские **1024 и 4096** сохранены *отдельными помеченными пунктами* для коротких синтетических архивов (они не являются original menu options).
5. До каждого пересчёта FFT выполняется `fft_source_archive_gate`: проверяется длина настоящего BIN, выбранная позиция начала/конца и необходимый source FIR-history для огибающей `required_original_history`. Недоступные пункты отключаются; попытка выбрать недостаточный размер отклоняется без пересчёта или затирки уже отображаемого FFT; дополнение нулями запрещено. Программа отдельно показывает источник пункта NFFT, предупреждение о численном паритете и подтверждённую длину истории.
6. Старые вкладки расчётных данных, временного сигнала, буферов AUX4700/VALUES, H-полоса и офлайн-архивная архитектура остаются без изменений. Не запрашивается прибор и не используется сервер.

## 4. Регрессия

- `tests/test_mvk_spectrum_menu_runtime_idr_candidate.py`: Full=150/100000, все 6 дБ и физические Page, дефолтные Tag, вертикальные переносы позиции, отдельная проверка 6 NFFT и 2 исследовательских, отсутствие нулевого дополнения, неподходящие sample_count/end/FIR значения.
- `tests/test_desktop_qt.py`: три новых Windows offscreen сценария — реальная V-полоса со сменой Tag и Position, блокировка NFFT≥8192 в **4096-отсчётном** синтетическом архиве, успешный реальный NFFT=8192 в синтетическом архиве **8192 настоящих отсчётов**.
- `tests/test_offline_core.py`: fixture_zip теперь принимает `sample_count` с прежним default 4096 — никаких оригинальных измерений и приватных ресурсов.

**Точный программный SHA:** `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`.  
[Linux Core #79](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/79) — **SUCCESS**. Windows Core+Qt и следующий Windows Preview verified-dist EXE проверять для **этого же SHA**. Отсутствие одного из статусов означает *непроверенно*, а не PASS. Упаковка EXE/CI не подтверждает оригинальный численный/пиксельный паритет Delphi.

## 5. Продолжение Stage 111U

1. Проверить Windows Core+Qt, EXE и `verified-dist/BUILD_VERIFICATION.json` точно на указанном source SHA; независимо сравнить скачанный EXE с SHA256SUMS.
2. Приватно восстановить/измерить фактический Delphi `GraphDefaultVScale` по тем же исходным BIN, режиму, датчику/типу и окну. Не подменять его диапазоном Qt.
3. Измерить оригинальные TPaintBox.Canvas.Font/Size, TextWidth/Height, DPI/PixelRect, курсор X/Y, оригинальные `CursorString`, сверить приватные pixel sweep и GDI XOR.
4. Довести численный `GetSpectrum/GetNarrowbandValue/FRange`, `FormatFloat`, x87 и паритет оригинальных шести NFFT на одном archive window.
5. Целевой продукт — автономный Windows Desktop; `main` и старый Web v0.3.40 заморожены, реальный прибор не подключать без отдельного разрешения. Не публиковать PAS/DFM/IDP, промышленные BIN/PCAPNG, реальные защищённые коэффициенты.
