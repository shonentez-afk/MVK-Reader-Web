# STAGE111Z31AW — восстановление геометрии PageAdc/PageSpectrum, диаграммы PageStatus и панели PageConfig из оригинальной DFM

**Дата:** 2026-11-11. **Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`.
**База:** Stage111Z31AV, исходный коммит `1052ffe9175f8c84699c456c17e78e065ca09117`; проверенная автономная Windows-сборка AV [#42941474687](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42941474687) SUCCESS.
**Новый код:** `57efef000f44444f0337e6f5748c63f66e820f62`, исходные промежуточные коррекции `6fd1fd505607efc143f98e09005afef72ba669f6`, **итоговый проверенный source commit `52490051137ca3e0c09e3e435e7827a44b67e40c`.**

## 1. Оригинальные приватные источники — изучены, НЕ выложены

Прочитана собственная пользовательская `Projects.7z`, непосредственно `Projects/mvkform.dfm`, восстановленная из `mvkview.idp`: 7 TTabSheet оригинала, подписи Caption='$' runtime-локализованные. Для этого этапа особое значение имеют:

- `PageSpectrum/tcSpectrum/pnSpecTools`, ширина 177; девять исходных контролов **с абсолютной DFM геометрией (x,y,width,height)**: `bSpecEnvelopeType=(9,9,162,41)`, `bSpecType=(9,56,162,41)`, `bSpecLines=(9,103,162,41)`, `bSpecHScale=(9,150,162,41)`, `bSpecVScale=(9,197,162,41)`, `lbSpecHint=(9,257,162,64)`, `lbSpecMean=(9,327,162,145)`, `bSpecCopyValue=(9,464,162,41)`, `bSpecSaveValue=(9,511,162,41)`. **Источник допускает перекрытие**: `lbSpecMean` до y472, `Copy` начинается y464. Ранее обычный Qt VBox изменял реальную геометрию. `bSpecType` — split-button из `popSpecType` с `mSpecType1..4` и `Tag=0..3`; не `QComboBox` в главном виде.
- `PageAdc/tcAdc/pnAdcTools`: `bAdcEnvelopeType=(9,9,162,41)`, `bAdcType=(9,56,162,41)`, `bAdcHScale=(9,103,162,41)`, `bAdcVScale=(9,150,162,41)`, `lbAdcHint=(9,207,162,64)`, `lbMean=(9,277,162,164)`.
- `PageStatus/tcStatus`: исходный `chResult:TChart` **(4,42,400,720)**, `splResult:TSplitter` **(404,42,8,720)**, `MinSize=320`; справа `TStringGrid` с результатами. `SpecSeries:TBarSeries`, BarWidthPercent100; исходный runtime dispatcher имеет 15 режимов `tcStatus`, уже восстановленных в `original_pagestatus_source.py` Stage111Z28B.
- `PageConfig/pnConfigButtons`: 5 исходных кнопок **48×48 icon-only**, x=(6,60,122,184,238), y=6, `ImageName` соответственно `Open/Save/Zap/DevUpload/DevDownload`; длинных текстовых надписей DFM нет, их подставлял Qt и обрезал на скриншотах пользователя. `tcConfig` содержит **две** записи Tabs.Strings ('$','$'); `tabConfigBasic` — отдельный `TStringGrid`, а не третья вкладка.
- Оригинальные Bitmap/ICNS/IDP/DFM **остаются локальными, не публикуются**. Runtime-тексты, шрифт Tahoma/WIN GDI, образ оригинальных иконок и pixel-perfect график пока не аттестованы. На Windows 150% DFM размеры являются логическими пикселями и НЕ умножаются вручную на 1,5.

## 2. Реализовано одним крупным пакетом

1. `mvk_compatible/core/original_ui_form_contract.py`: расширен только компактный производный исходный layout-контракт (панель Config, splitter/BarChart Status, число оригинальных Config вкладок).
2. `mvk_compatible/desktop/source_control_canvas.py`: новый source-control canvas, размещающий контролы в **точные DFM прямоугольники**, включая перекрытия, без зависимости от x32dbg, без BMP. В штатном окне Qt `pnSpecTools=177px`, а содержимое имеет точные x9..171; при минимальной высоте стандартная вертикальная полоса Windows сокращает доступную ширину и `SourceControlCanvas` пропорционально сжимает ТОЛЬКО X-геометрию, сохраняя оригинальные DFM rectangles как неизменяемые свойства. Горизонтальная полоса не требуется; в обычном окне все размеры точны.
3. `mvk_compatible/desktop/main_window.py`: 6 Wave и 9 Spectrum видимых контролов теперь source-positioned, с прежними callback-контрактами `self.spec_mode/spec_n`. `bSpecTypePresenter` — меню 4 Tag (0..3), синхронизируется с моделью `self.spec_mode`; основная кнопка `bSpecLinesPresenter` использует прежнюю единую FFT модель. Исследовательские поля остаются в QDockWidget, рабочее вычисление не изменено. Верхняя source-панель сигнала 177px, спектра 177px, полоса канала 36px и источниковые полосы прокрутки графика сохранены.
4. `mvk_compatible/desktop/original_shell.py`: `PageStatus` реально содержит исходную **левую TChart/43-band Qt BarGraphItem** и правую таблицу с разделителем 8px. Столбцы строятся **ТОЛЬКО** если Stage28B `StatusTable.bands_for_plot` содержит ровно 43 подтверждённых оригинальных полос; при простом BIN+TSXML и отсутствии AUX/VALUES диаграмма скрыта, DSP/RPM не выдумываются. Для Config пять кнопок вернулись к **48×48 image-only** с стандартными безопасными Qt fallback-иконками, полными русскими подсказками и disabled аппаратными командами. `tcConfig` теперь 2 режима, `tabConfigBasic` сохранён отдельно и скрыт до подтверждённого штатного режима.
5. Qt и source-only regression: `test_desktop_qt.py`, `test_stage111z31ao_original_qt_shell.py`, новый `test_stage111z31aw_idp_dfm_ui_geometry_source.py`. В том числе exact rectangles, four mode Tags, fail-closed 43-bar chart, original Config image buttons, minimum-size no-horizontal-scroll и сохранение лабораторных моделей.

**Не изменялись:** `fft_idr_candidate.py`, `envelope_idr_candidate.py`, `envelope_spectrum_idr_candidate.py`, `spectrum_display_source.py`, `spectrum_metrics_idr_candidate.py`, source `original_pagestatus_source.py`, Native R6.1, BIN/TSXML reader, исходные проверенные расчёты Code20/LOG0. Сам оригинал MVKView и x32dbg не запускались.

## 3. Проверка и приёмка

[Stage111Z31AW workflow](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42944965100) для commit `6fd1fd505607efc143f98e09005afef72ba669f6`.

****CI ПРИНЯТ.** [GitHub Actions #42945486718](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42945486718) = **SUCCESS**: Linux полный офлайн Core PASS; Windows Core PASS; Windows Qt (включая 150% DPI, исходный спектр/курсор и новый DFM control/status UI) PASS; verified autonomous Windows EXE PASS. Точный собранный source SHA = `52490051137ca3e0c09e3e435e7827a44b67e40c`. Artifact = **`MVKViewCompatible_Stage111_Windows_Preview` #13822467494**, archive 68 591 796 bytes, [скачать из Actions](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42945486718).

Две ранние попытки CI `#42944567698` и `#42944965100` выявили **настоящую регрессию узкого окна** — горизонтальный Qt overflow 14/8 px при нативной вертикальной полосе. Исправлено в `52490051137ca3e0c09e3e435e7827a44b67e40c`: `SourceControlCanvas` использует динамическую горизонтальную адаптацию **только если** доступное окно уже оригинального правого края x171, а при обычном размере DFM координаты 1:1. Последняя проверка SUCCESS.**

CI/PySide6 headless проверяет модель и геометрию; это **не визуальная приёмка пользовательского Windows-клона** и не proof точного GDI TextOut/Original TQGrapher pixels. Пользователь лично делал 14 скриншотов предыдущего Stage111Z31AP, **GigaCode их не должен создавать** (зависает). Локальную прежнюю копию `C:\mvk_log\mvkview_exe\` не изменяли.

## 4. Дальнейший приоритет (другой чат)

1. **Оригинальный график TQGrapher/TCo2Draw**: восстановить источник осей X/Y, геометрию сетки 10×10, шрифт, min/max, scroll и курсор относительно Source float bins на подтверждённых RAW/Power/Y. Не подгонять FFT по скриншоту; на одном Code20 LOG0 окне уже 0 ULP, прочие режимы отдельно.
2. **Оригинальные TLanguage/Txt/ExTxt локализованные заголовки**, `PageStart` command-link images/runtime page visibility. DFM Caption='$' нельзя считать готовой русской подписью.
3. **Config/Calib read-only формы**: точные grid rows/компоненты и безопасные офлайн-данные; аппаратные действия запрещены, пока нет подтверждённого протокола. `PageFile` — верификация оригинальных сценариев архива, сохранение имеющегося BIN/TSXML.
4. **Envelope/FIR offline UX**: оригинальные локальные профили и полная независимость от ручной IDP загрузки без публичной передачи приватных коэффициентов, только после source-based проверки и честной маркировки неподтверждённых режимов.
5. Windows ручная визуальная приёмка новой сборки пользователем на DPI 150%; GigaCode и x32dbg GUI не запускать.

**Перед продолжением** прочитать `START_NEW_CHAT_RU.md`, `CURRENT_STATUS_RU.md`, данный Stage111Z31AW отчёт, [Stage111Z31AV report](STAGE111Z31AV_SAFE_IDP_DFM_UI_INTEGRATION_RU.md) и GitHub Actions. Работать только в `research/stage111-mvkview-desktop-20261029` без удаления старых модулей/цифровых паритетов; крупные функциональные пакеты, не микро-PR.
