> **FINAL CI/EXE ACCEPTANCE 05.11.2026:** Code revision `733a9d0cdcf5ab112ac80dcf663b32e29584cd1f` [GitHub Actions #41961957315](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41961957315) **all 3 jobs SUCCESS**. Linux Core **1265 passed / 17 skipped / 30 subtests**; Windows Core **1278 passed / 4 skipped / 30 subtests**; ordinary Windows Qt **49 passed**, separate effective-DPR=1.5 Windows Qt **10 passed**. Existing Go Native R6.1 built/tested unchanged; Windows PyInstaller EXE separately integrity-verified. [Artifact #13385394862](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41961957315/artifacts/13385394862) ZIP 68,501,367 bytes; inside `MVKViewCompatible_Stage111_PREVIEW.exe` 68,500,017 bytes, SHA256 **`c3a4fd8fa588f83c0a69bab5ec58df48f69b95b53941ed80abf77a73aebbdf05`**, plus `SHA256SUMS.txt`, `BUILD_INFO.txt`, `BUILD_VERIFICATION.json`. GitHub uploaded artifact ZIP digest `cc8a7a573a3479e20bc6a84560f3f9f2b9ef958ffa920baa6838549266299c59`. Note: first CI failure was a synthetic invalid point inside valid bounds, fixed; second was a test assuming source is TSXML even though fixture was R6.1 ZIP, also fixed. No source failure remained after fixes. This numerical+Qt acceptance **does not** certify original Win32 TCanvas runtime physical plot pixel parity.

# Stage111Z31D — фактическая Qt ViewBox, DPR 150% и раздельные источники FRange

**Дата:** 05.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.
Цель — сделать следующий шаг TQGrapher/Qt UI приёмки, не теряя уже доказанный численный паритет GetSpectrum Tag0..3.

## 1. Основание и границы

Пользователь предоставил два изображения Windows 1920x1080 при системном масштабе **150%**, с открытым настоящим исходным x32dbg Tag0 и исследовательской Qt-панелью. Уже проверено: `N262144/Fs65536`, исходный `FRange Single=0x43FF4853` (~510.565033), полный оригинальный Y **131072/131072 Float32 bitwise**, курсор **3800 Hz / -55.32 dB**, summary `6.89 / 3800 Hz / 0.7786`, 3/3 оригинальных HEX. Старые массивы/хеши Tag1/2/3 не пересчитываем.

Диагностика Qt с открытым правым dock сообщила `virtual viewport Qt 789x522`, `DPR=1.5`, `logical DPI 96x96`, Qt font `Segoe UI`; расчёт источника на размерах Qt дал **модель** `PixelRect=(L68,R775,T14,B464)` и исходную DFM-модель `Tahoma -13/96PPI/pbSpectrum(767,716)`. Это не измеренная в original 32-bit MVKView runtime PixelRect и не доказательство любой физической координаты пикселя. Открытие Research dock изменяет ширину viewport.

## 2. Исправлено в source

В `desktop/main_window.py` теперь:
- При импортированном original Power/Y отдельная read-only строка показывает **оригинальный FRange из JSON** и исходное Single слово, например `FRange=510.565033 · Single 0x43FF4853`; отдельная ручная настройка `FRange гипотезы архива · НЕ x32dbg` остаётся 1.000000, не подменяет оригинальные FFT/Y.
- Поле `TSXML / FRange: источник не открыт` относится **только** к TSXML и остаётся независимым от оригинального x32dbg. Это не ошибочное утверждение, что original FRange неизвестен.
- `GraphDefaultVScale` в режиме оригинала больше не пишет `FRange архива НЕ ПОДТВЕРЖДЕН` применительно к оригинальному слову: подтверждён именно фрагмент Single FRange из JSON, а графическая формула/x87/Delphi Canvas остаются исследовательской гипотезой.
- После закрытия эталона read-only строка возвращается в состояние `эталон не открыт`; ручное значение FRange архива не изменяется.

Для геометрии добавлен `core/qt_spectrum_viewport_observation.py`, работающий **с независимо измеренными Qt координатами**, а не с подобранной original PixelRect. Qt `ViewBox.sceneBoundingRect()` проецируется через `QGraphicsView.mapFromScene` в реальные **Qt logical viewport pixel** координаты, явно привязывается к `QWidget.mapToGlobal`, `devicePixelRatioF`, `logicalDpiX/Y` и признаку видимости Research dock.

Новая `MainWindow._collect_canvas_geometry_candidate()` возвращает оба независимых набора:
- `qt_measured_runtime_geometry` — текущие Qt viewport, actual ViewBox rectangle (viewport/global **логические**, не screenshot physical), nominal device size лишь при умножении размера на DPR.
- `source_paintbox_registration` — старое source-derived TQGrapher преобразование и PixelRect, вычисленные **на Qt font metrics** (не runtime Delphi).

Окно `Геометрия Canvas` теперь явно подписывает фактические Qt координаты и **МОДЕЛЬ PixelRect (не оригинал!)**, чтобы старое сообщение не трактовалось как реальная Win32 GDI геометрия.

## 3. Контрольные тесты

- `tests/test_stage111z31d_qt_geometry_observation.py`: проверка типов, DPR1.0/1.25/1.5/2.0, логических и device-size координат, отрицательной координаты второго монитора, fail-closed неверных границ; отдельная проверка нормализованного cursor из двух имеющихся screenshot (приблизительно 0.53 px по X и 0.21 px по Y при проекции на ширину текущего Qt; **не** исходный runtime/parity).
- `tests/test_stage111z31a_qt_original_reference.py`: две дополнительные GUI-проверки **с архивом и без него**, original FRange vs ручной FRange, GraphDefaultVScale provenance, фактическая Qt viewbox в открытом/закрытом Research dock, возврат эталона без утечки состояния.
- Границы: никакой PNG/BIN/EXE/IDP не публиковался в GitHub; исходный Go Native R6.1, main/Web, прошивка, DSP/FFT/Y/summary не изменены.

Первый CI-прогон по исходному коду `f21be762eb1ebebb0e43445586ca7c28e8e4e24c` выявил ошибку **только в синтетическом QA-векторе**: тестовый cursor `(200,30)` фактически попадал внутрь прямоугольника `(10,20,210,120)`. Тест исправлен на `(220,30)`, новый исходный тест-коммит `828f9748dc80ab204da2ce1eba98c43ba786ac0c`. Заключение полной CI и SHA Windows EXE необходимо проверить по последнему workflow, до SUCCESS этап UI не объявлять принятым.

## 4. Что закрыто / что остаётся

**Stage31D code:** источник x32dbg FRange отделён от ручной TSXML/BIN гипотезы; собраны фактические Qt геометрические координаты отдельно от исходной математической модели; добавлен контроль DPR150/dock. **Это не сертификация pixel-perfect MVKView.**

**Далее Stage31E**: сравнить actual Qt viewport rect и оси при закрытом/открытом Research dock на одних и тех же оригинальных Y и XScale; затем источник TQGrapher grid/tick/pen и Tahoma vs Segoe UI. Для полного фактического original TPaintBox runtime необходимо независимое подтверждение DPI awareness VCL/Win32 и native Canvas/font metrics. Самому пользователю на этом шаге **не нужны новые x32dbg GetSpectrum дампы**.
