# STAGE111Z31CK — сквозной Core+Qt по семи страницам и трём исходным формам, редактор и карта 95 DFM событий

**13 ноября 2026. Статус: этап CK принят (3/3 GitHub Actions SUCCESS); оригинальная Win32 MVKView 1.0.47 НЕ воспроизведена 1:1.**

## Доказательная база (сохраняется приватной)

Операторский `Projects.7z` с `mvkform.dfm`, `mvkeditform.dfm`, `WindowManForm.dfm` разобран локально. Их события `On*`:
- Главная форма `mvkform` — **89 назначений**: FORM 19, Pages 1, PageStart 7, PageConfig 15, PageStatus 7, PageAdc 7, PageSpectrum 12, PageFile 7, PageCalib 14.
- `mvkeditform` — **5 назначений**: FormCreate, FormShow, bOkClick (два источника — кнопка и список), bRecalcClick.
- `WindowManForm` — **1 назначение**: bOkClick.
- Всего **95 DFM bindings / 53 уникальных имени**. Повторное использование общего `tcAnyChange` и других имён учтено. Внутренние динамические menu handlers могут не входить в 95 DFM назначений — эта цифра **не** равна числу всех возможных runtime событий оригинала.

**Ни исходные PAS/DFM/IDP/BIN, ни bitmap-ресурсы оригинальной Win32 программы в публичный GitHub НЕ выгружались.**

## Изменения одним связанным пакетом в Core + действующем Qt

1. **Автономный `core/original_event_fidelity.py`**: точная source-derived структурная таблица 95 привязок `form/page/object_name/On*/handler`, строгая приёмка 7 страниц, 3 форм, 53 уникальных имён, default-deny классификации по существующему `core/original_event_access_control.py`. Не содержит исполняемых указателей, приватных процедур, идей автоматического device dispatch и утверждений о 95 реализованных функциях.
2. **`desktop/source_event_runtime_audit.py`**: реально инспектирует живые QWidget objectName для событий и возвращает точные present/missing counts для 3 форм, **не** выдавая наличие QObject за полностью работающий обработчик. Проверяет 7 вкладок, 15 режимов PageStatus, 49 шагов PageCalib, по два исходных режима Config/FileActions/CalibResult и закрытые аппаратные кнопки. Никаких USB/serial/network вызовов.
3. **`core/original_value_recalc.py`**: source-derived `mvkeditform.bRecalcClick` по `_Unit128.pas:008404E8`: исходный текст → безопасная числовая проверка (одна точка или запятая) → Float32 → multiplication extended literal 0.00010194 → Float32 → кандидат текста. В результате неизменяемый `SourceSensitivityConversion` с явно НЕпроверенными Delphi RTL/x87 parity flags и `instrument_write_sent=false`. Ни файлов, ни приборных регистров не меняет.
4. **`desktop/original_value_edit_dialog.py`**: связывает эту Core-функцию с `bRecalc` только по явному `sensitivity_conversion=True` в редактируемом text-mode; исходный DFM Visible=False по умолчанию, read-only и list-mode остаются невосприимчивы; некорректный ввод не принимается и не записывается. Обнаруженный новым сквозным тестом прежний баг исправлен: `cbVal` не должен использовать `.isVisible()` **после** принятия диалога для определения режима. `_source_list_mode` теперь сохраняется после `bOk`, DoubleClick и закрытия; `selected_value()` возвращает реально выбранную строку.
5. **`core/original_offline_view_state.py` и действующий `desktop/original_shell.py`**: три безопасных новых Core-перехода `select_config_tab`, `select_file_action_tab`, `select_calibration_result_tab`. Подключены к `tcConfig`, `tcFileActions`, `tcCalibResult` в настоящем Qt. `tcFileActions.OnChange` обновляет локальный режим/подсказку `pnFileAdc`, но **НИКОГДА** не вызывает `TMVKThread.WriteData/WriteValues`. Все опасные `bConfigUpload/Download/Reset`, `bCalibStart`, первоначально скрытый `bTaskConfigCalib` остаются выключенными.
6. **Тесты** `test_stage111z31ck_event_ledger_and_editor_core.py` и `test_stage111z31ck_qt_95_event_routes.py`: исчерпывающий структурный ledger, строгая default-deny оригинальных handlers, бракованные числовые входы, safe immutable state, фактический обход 7 исходных страниц с одним проверенным synthetic ZIP, независимость SHA исходных данных, локальный PageFile checkbox toggles, 49 Calib steps, три формы и реальный Win32/Qt edit/list accept-result. Qt E2E включён в обязательный Windows DPI150 workflow. Это тесты **программы-копии**, а не оригинальной MVKView.

### Важная регрессия и исправление

Первый CK commit `a14f3212ea198e5f32ef778d5f0a44dd0bf0b99e`: Windows Core **2102 PASS + 1 FAIL** в новом Qt тесте `test_editor_source_hidden_default_readonly_and_list_doubleclick`. Причина — список в закрывшемся диалоге Qt имеет `isVisible()=False`; метод `selected_value()` по ошибке возвращал текст скрытого `edVal` вместо выбранного `cbVal`. Исправлено в **`e81b37b76db442c74b3335b0ba0552846efb97b8`**, не изменяя проверок и не затрагивая численные модули FFT/FIR.

## CI и проверенный автономный EXE

[GitHub Actions #43406164479](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43406164479) **3/3 SUCCESS**, проверенный executable/source SHA `e81b37b76db442c74b3335b0ba0552846efb97b8`:
- Linux Core **1935 PASS / 106 SKIP** (21.88 с)
- Windows Core **2103 PASS / 7 SKIP** (202.08 с)
- Windows Qt smoke **49 PASS** (37.42 с)
- Windows Qt DPI150 **139 PASS** (147.48 с), **измеренный DPR 1.5**.

[Автономный Windows EXE artifact #14027977514](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43406164479/artifacts/14027977514), ZIP **69 011 883 байта**, до 27.11.2026; Go Native R6.1 встроен. ZIP SHA256 **`99f3130055f693be4a4ee4595dc43cdcc43d0f39017d816f38655006d3162740`**; EXE SHA256 по проверенному PE-манифесту **`84221827eceeb29d528671329ff5f84dcb92b999fc371a80e9b6f776a78b5856`**. PE header, build manifest и SHA EXE совпадают в Actions. Исходный флаг `original_delphi_compatibility_verified=false` (не выдавать за 1:1). [Synthetic Windows Qt screenshot artifact #14027348090](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/43406164479/artifacts/14027348090), **643 896 байт**, до 20.11.2026. Записанные длительности — длительности CI на runner, не FPS на операторском компьютере.

## Нерешённые проблемы и следующий большой, не раздробленный пакет

**Нельзя заявлять полную реализацию 95 оригинальных событий.** Ledger сообщает SOURCE event assignment и runtime-QObject coverage; типы `FormCreate`, `OnPaint`, `FormResize`, редакторские изменение регистров и приборные таймеры ещё требуют source-by-source проверки. Original hardware commands default-deny; оригинальный device Write/Upload/Reset без отдельного разрешения не запускать. По bRecalc исходная расширенная точность x87, RTL FloatToStr и то, какие конкретно исходные поля включали кнопку, требуют runtime приёмки; сейчас кнопка доступна только по явно указанному mode, что предотвращает неверные изменения. Структура, копия FFT/FIR/Power/Y/FRange и Win32 layout остаются источниковыми реконструкциями без полного dynamic same-window parity.

**Следующий P0** — опереться на уже проверенный [`MCP_VISIBLE_SPECTRUM_REFERENCE_20261113_RU.md`](MCP_VISIBLE_SPECTRUM_REFERENCE_20261113_RU.md), который зафиксировал оригинальный экран спектра 1942×1042 с рамкой `[416,196,1850,844]`, СКЗ **6,89 м/с²**, пик **3800 Гц / 0,7786 м/с²**, шкалы **25600 Гц / 150 дБ** (но НЕ идентичный доказанный BIN и не доказанные невидимые пункты меню). Закрыть сквозной путь **`DirectBinSession.open → refresh_spec → реальный dense/sparse zoom и pan → точный независимый курсор → Copy/Save`**, с immutable Float32, строгой проверкой пиков и отсутствием пересоздания DataSize/FFT. Уже принятые `131072/131072` source FFT и Power→Y битовые проверки **не повторять**. Для numerical 1:1 требуется ОДИНАКОВЫЙ локальный BIN/TSXML, source sample rate, H/V/Envelope/FRange, позиция и работающий оригинал; без оригинального пары честно отмечать `DATA_GATE`, не объявлять synthetic PNG заменой эталона.
