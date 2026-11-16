# Stage111Z31CO — исходный TabOrder и управление спектром в компактном Windows 150%

**Дата:** 16.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`.
**Проверенный исполняемый SHA:** `f4fe8c77306cadf984efb0cbc205b8e461aaa781`.
[Actions #43792034352](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43792034352) **4/4 SUCCESS**.

## Исправления в рабочем коде

- Из приватного оригинального `mvkform.dfm` перенесены только публично
  описываемые **имена контролов и Delphi TButton.TabOrder**, без исходных
  приватных байтов/ресурсов/встроенных DFM: PageSpectrum `bSpecType=0`,
  `bSpecLines=1`, `bSpecHScale=2`, `bSpecVScale=3`,
  `bSpecCopyValue=4`, `bSpecSaveValue=5`, `bSpecEnvelopeType=6`.
  У Envelope исходная геометрия y=9, но он ПОСЛЕДНИЙ по TabOrder;
  визуальный порядок нельзя использовать вместо DFM TabOrder.
- PageAdc: `bAdcType=0`, `bAdcHScale=1`, `bAdcVScale=2`,
  `bAdcEnvelopeType=3`.
- `core/original_ui_form_contract.py` — исходный TabOrder обоих
  источников; `desktop/source_control_canvas.py` — реальный Qt
  `setTabOrder`, `FocusIn` с `QScrollArea.ensureWidgetVisible`;
  `desktop/main_window.py` — применение обоих Core контрактов;
  `desktop/original_shell.py` — возврат к верхним исходным кнопкам
  при повторном выборе PageSpectrum после перехода на другие страницы.
- Все Source DFM прямоугольники остались на местах, ширина `pnSpecTools`
  177 логических px, полноразмерные FFT, FRange, FIR, живой native
  приёмник и архивы не модифицированы.

## Проверки чисел и мыши, без подмены объекта

`test_stage111z31co_qt_compact_pointer.py`: открывает настоящий
`DirectBinSession` на синтетической BIN/TSXML с АЦП4, Fs=65536,
N=65536. При размере окна 960×580 логических px вертикальный
скролл идёт от 0 до 144. Проверяется отправка реального Qt
`QWheelEvent`, корректное изменение `QScrollBar` при Tab
(включая источник `bSpecEnvelopeType` ПОСЛЕДНИМ), координаты
реального видимого ребёнка `viewport.childAt`, затем
`QTest.mouseClick` **на видимой кнопке** Copy/Save, подтверждённые
три таб-разделённых значения буфера и реально созданный CSV
`НЕ КАЛИБРОВАНО`. `QToolButton.InstantPopup` H/Y открывается
реальным кликом без скрытого пересчёта или автоматического
циклического 1/10/100, а выбор Tag2 обновляет только Y viewport.
Dense→sparse→dense и source cursor по полным данным сохраняют
одинаковый SHA Float32
`9bd646b8f91f4ff8581afe511208d37466e13162f04aefd77bc2fddcb4fb987a`,
исходный BIN и `_spectrum_summary`.

`QApplication.widgetAt(global)` под неинтерактивным GitHub hosted
native Windows desktop может вернуть None **при корректно видимой
кнопке**; он не служит единственным доказательством доступности.
`viewport.childAt` рекурсивно проверяет Qt фактическую цель
с учётом clipped QScrollArea и z-order; если global-hit доступен,
его совпадение также проверяется. QTest.mouseClick симулирует Qt
мышь, **не оригинальный Win32 процесс/физический прибор**.

| Приёмка | Результат |
| --- | --- |
| Linux offline Core | 1954 PASS, 110 SKIP, 1 warning, 30 subtests |
| Windows offline Core | 2130 PASS, 7 SKIP, 1 warning, 30 subtests |
| Windows Qt smoke | 49 PASS |
| Qt offscreen DPR 1.0 | 4 PASS |
| Qt offscreen DPR 1.5 | 147 PASS |
| Native Windows QPA DPR 1.0 | 4 PASS |
| Native Windows QPA DPR 1.5 | 4 PASS |
| Windows onefile EXE + embedded Go R6.1 | SUCCESS |

[EXE artifact #14192209456](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43792034352/artifacts/14192209456):
ZIP **69 030 232 bytes** до **30.11.2026**. Manifest EXE SHA-256
`9b54ee8151bebc6f8fd145608e24ac2a3fd40707cc11893d15ff0b7c544d59c6`;
actual checksum=manifest (Actions logs).
[Native 100/150 GUI screenshots + receipts #14193156498](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43792034352/artifacts/14193156498),
**598 473 bytes**, до 23.11.2026. Этапы `05_compact_top`,
`06_wheel_scrolled`, `07_save_focus_visible`, `08_return_source_top`.
Native скриншот при 150% — физически **1440×870**, не user original **1942×1042**.

## Незакрытые задачи — не смешивать с уже принятым

- Только пользовательская исходная MVKView Win32 на одном BIN/окне/АЦП/
  режиме и тех же физических координатах может подтвердить 1:1
  TQGrapher пиксели, оригинальные оси, курсор, формат и физические
  значения. Native CI synthetic BIN не является таким эталоном.
- Source FIR envelope post-FIR/full Y и оставшиеся численные единицы,
  все семь страниц и три формы ещё НЕ завершены как полный оригинал.
  Принятые прежние FFT/Power→Y, Hann и FIR источник НЕ перепроверять
  заново вместо реального восстановительного шага.
- **Важный более свежий handoff другого осмотра:** оригинальный
  пустой PageStart («Задачи») обследован отдельно, но исходный PNG
  отсутствует. [Оригинальный empty Tasks audit](STAGE111Z31CO_ORIGINAL_EMPTY_TASKS_UI_EVIDENCE_20261116_RU.md),
  [новая инструкция](../../handoff/NEXT_CHAT_20261116_TASKS_UI_RU.md).
  Следующий пользовательский приоритет — получить два безопасных
  скриншота оригинала и Qt без измерений при одинаковых 1942×1042 /
  одинаковом DPI и **после** доказанной попарной геометрии исправить
  PageStart UI и Core маршруты единым пакетом. Ничего не нажимать
  на оригинальном приборе/в оригинальной программе до отдельного
  разрешения оператора.
