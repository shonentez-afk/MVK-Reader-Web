# MVKView 1.0.47 — восстановление реальной последовательности GetSpectrum FIR → FFT
**Передача следующему чату — 24.11.2026. Ветка:** `research/stage111-mvkview-desktop-20261029`.

## 1. Текущий результат
Восстановлено важное несоответствие фактического DSP, а не только интерфейса. В оригинальной цепочке `GetSpectrum` значение `bSpecLines` задаёт **количество RAW Single отсчётов до FIR**; `GetAdjustedEnvelopeLength` добавляет необходимую историю. В `_Unit115.pas` по `007D1462`, `007D1C48`/`007D1E70` меняется `Params.Count`; `TDSXFastFourier` получает уже **количество отсчётов после FIR**. Ранее архивный UI передавал `bSpecLines` в исследовательскую функцию как *post-FIR FFT N*, выдавая неправильную историю, FFT N и частотную сетку.

### Восстановленная цепочка
`original menu bSpecLines (PRE-FIR N) → SHA-проверка выбранного BIN/Go кольца → GetAdjustedEnvelopeLength → RemoveMean Float32 один раз до FIR → original FIR decimators + final I/Q magnitude → post-FIR sample rate and post-FIR FFT N → Hann → FFT → Power → low-bin cutoff → optional power integration for ВС/ВП → 4-mode Y display → summary over full N/2 → TQGrapher cursor and view projection`.

**Примеры из исходных расчётов для Fs 65536 Гц**:
- Фильтр Code20, `bSpecLines=4096`: из 4147 RAW/FIR-history отсчётов получается `FFT N=2048` при `Fs_out=32768`, `Δf=16 Гц`, полный `N/2=1024`.
- Фильтр Code20, `bSpecLines=1024`: из 1075 входных отсчётов `FFT N=512`, `Fs_out=32768`, `Δf=64 Гц`.
- Code4, `bSpecLines=4096`: исходная история 4289, FFT после FIR=512; запрет `post-FIR N<1024` в исследовательском коде был ошибочным.
- Приняты короткие post-FIR radix-2 спектры `N>=8` при достаточной проверенной истории. Оригинальная FFT процедура может принимать `N>=2`; диапазон `N=2/4` остаётся **не аттестованным для полного summary / курсора**, поэтому в нашем общем пути сохраняется отказ.

**Режимы:** Tag0 — логарифмические дБ, Tag1 — ВУ (м/с²), Tag2 — ВС (мм/с), Tag3 — ВП (мкм). В ВС/ВП `007D2164` интегрирует именно power, после чего выводит Y. `FRange` исходного процесса и точное Float32/x87 округление по полной аппаратной сессии ещё не аттестованы. Нельзя считать единицы из локальных BIN физически проверенными по одному названию Tag.

## 2. Изменённый production-код
- `mvk_compatible/core/offline_export.py`: `OfflineSession.spectrum_envelope(...,source_selected_bspec_lines=True)` теперь выбирает точное **pre-FIR** окно и вызывает `source_selected_envelope_spectrum_candidate`; при `False` сохраняет старое исследовательское API с явно **post-FIR N**.
- `mvk_compatible/core/offline_measurement_flow.py`: передача флага через общий источник четырёх вкладок.
- `mvk_compatible/desktop/main_window.py`: оригинальное меню, gate полной истории, fallback, расчёт, длина вектора, отображение и курсоры используют фактический post-FIR `N/Fs`. `bSpecLines` остаётся пунктом до FIR. Нормальный `lbSpecMeanPrimary` не перегружать отладочной подписью; `spec_mean`/технический индикатор содержат обе длины.
- `mvk_compatible/core/envelope_spectrum_idr_candidate.py`: корректно допускается короткая FFT после FIR; отдельный явный исходный vs исследовательский контракт.
- `mvk_compatible/core/spectrum_metrics_idr_candidate.py`, `spectrum_display_source.py`, `tqgrapher_display_idr_candidate.py`: численный summary/режимы/серия при коротком настоящем post-FIR FFT (не ограничивать оригиналом N>=1024 после FIR).
- `mvk_compatible/core/original_live_envelope_provenance.py`: основанный на Go-кольце gate короткого post-FIR FFT; без SHA-проверки/достаточной истории это **не аттестованный live результат**.
- `mvk_compatible/core/original_spectrum_view_binding.py`: важный фикс: проверка принадлежности тому же BIN/АЦП, pre-FIR `bSpecLines` и реальных post-FIR `N/Fs` вместо неверного сравнения с исходным RAW `Fs`.

**Исходный Go/TCP приёмник, RAW, WriteValues/WriteData, Stop и ветка `main` не модифицировались этим пакетом.** Исходные приватные `Projects.7z`, `mvkview.idp`, `mvk_idr(1).sqlite` **не коммитить в GitHub**; использовать вместе локально для дальнейшего анализа.

## 3. Проверки и CI (не путать коммиты)
Новые тесты: `mvk_compatible/tests/test_stage111z31dw_original_bspec_prefir_archive.py`. Пересмотрены старые тесты `test_source_selected_envelope_ring_fft.py`, `test_stage111z31ca_qt_shared_envelope_popup.py`, `test_stage111z31cb_qt_envelope_two_column_real_ui.py`, `test_stage111z29c2_qt_envelope_domain.py`, `test_stage111z31p_shared_envelope_source_menu.py`.

Последний ПОЛНОСТЬЮ ЗАВЕРШЁННЫЙ перед исправлением тестов [Actions #45143441874](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45143441874) на SHA `30baa8c86d810e92e41ee740aa3cdfb90d2d1922`: Linux all core SUCCESS, Go RX SUCCESS, Windows native QPA/DPI SUCCESS; Windows core/Qt **2931 PASS, 15 SKIP, 3 FAIL**. Все три ошибки локализованы: одно новое тестовое ожидание метки в `spec_core_triplet` (эта метка преднамеренно принадлежит primary summary, а размер FFT находится в `spec_mean` и `spec_n_provenance`); ещё два старых теста ожидали прежнюю метку исследовательской функции и monkeypatch устаревшего `required_original_history`. Это **не было подтверждением численного сбоя**; исходный Qt DSP уже доходил до реальных вычисленных N=2048.

Исправления тестов внесены в коммиты `fe11210e08446acdfa4f544b99388c08778c49e5` и `aa3dd2ef425b743e0c0c9b564b16307464b97d5d`. Для последнего кодового SHA `aa3dd2ef425b743e0c0c9b564b16307464b97d5d` запущен [Actions #45233871699](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45233871699); **на момент записи полные 5/5 и новый автономный EXE НЕ подтверждены**. Проверять результат по последнему SHA, не переносить PASS другого SHA.

Последняя **ранее принятая автономная сборка до этого пакета**: SHA `f369fddb69641bc907946ee94a20d5ffbba5361c`, [Actions #45134184106](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45134184106), 5/5 SUCCESS, старый [EXE ZIP artifact 14800156170](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45134184106/artifacts/14800156170). В нём НЕ содержатся новые FIR/FFT исправления.

## 4. Незакрытая аппаратная приёмка
1. Подтвердить CI по точному кодовому SHA; затем принять Windows EXE только при полном зелёном workflow.
2. Проверить на **том же одном исходном приборном потоке MVK01 / MVKView 1.0.47**: IP → Измерить → Task2 → приём RAW → GetSignal / GetSpectrum (включая pre/post-FIR FFT и четыре Y) → WriteData / WriteValues → Stop, сравнить полные Float32 пары и контрольные суммы, курсоры, 7 страниц/3 формы. Различные BIN, TSXML, VALUES, TABLE из разных измерений не объединять как один runtime-golden.
3. Проверить FRange, исходные `x87` CW/промежуточные слова на Hann → FFT → Power → 4 режима, затем по одному и тому же RAW проверить запись и Stop.
4. Не выдавать synthetic CI за физический паритет оригинального Delphi/Win32, не менять имеющиеся таблицы исходных меню и не смешивать старую успешную сборку с новой непроверенной.

**Флаг завершения:** `original_delphi_runtime_bitwise_parity_verified=false`, `physical_mvk01_same_rx_e2e_verified=false`, `new_windows_exe_verified=false` (до новых GitHub Actions).

## 5. Старт новому чату
Открыть `START_NEW_CHAT_RU.md`, `CURRENT_STATUS_RU.md`, этот файл и актуальный SHA ветки. Не требовать повторно ранее переданные приватные оригиналы. **Не переписывать восстановленный алгоритм по памяти; продолжать проверяемую исходную логику и конкретные CI-расхождения**.
