# MVKView Compatible — текущий статус Stage111U (30.10.2026)

**Цель:** полноценная автономная Windows MVKView Compatible, Qt/PySide6, только `mvk_compatible/` на ветке `research/stage111-mvkview-desktop-20261029`. `main` и старую Web v0.3.40 не менять.

**Последний программный SHA:** `a2a0651903c04638bc08fb983a415563df74c7f4` (расчётный модуль, приватный компаратор и Qt-диагностика).

## Подтверждённые изменения

- Stage111T SHA `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`: [Linux #79](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/79), [Windows Core/Qt #78](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/78), [Windows verified-dist EXE #80](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/80) — все SUCCESS. **Отдельно скачанный** EXE не сравнивали по SHA256SUMS.
- Stage111U: приватный оригинальный Delphi (`Projects.7z`) подтвердил спектральный `sub_0084B4E8` / `0084B5D3..0084B882` и источник `TMvkChannelStorage.FRange` (+0x04). ADC `sub_0084AB98` — отдельный обработчик. Множители спектра: ×1 (0/1), ×10 (2), ×100 (3), затем log10/TRUNC, Single и ступени 1–2–5–10×10^k. Исходный конструктор задаёт FRange=1.0, **но фактический FRange архива неизвестен**.
- `core/spectrum_graph_default_vscale_idr_candidate.py`: явная исходная модель с независимым Decimal ceil и диагностикой граничного несовпадения; `original_math_helpers_x87_rounding_verified=False`.
- `desktop/main_window.py`: отдельный показатель `GraphDefaultVScale` по ручному `spec_f_range`. При выборе оригинального V scale рассчитывается параллельная исходная модель ScrollHeight/Bottom, а настоящая видимая Qt Y-ось пока по локальным спектральным данным — нельзя считать пиксельную идентичность доказанной.
- `graph_vscale_reference_compare.py`: офлайн-контроль пользовательских приватных эталонов, выводит только агрегатные ошибки, не публикует исходные числа.
- Локально 37 синтетических тестов расчёта/компаратора PASS, тест Qt дополнен. [Linux #85](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/85) SUCCESS; [Windows Qt #84](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/84) SUCCESS; [Windows Preview verified-dist EXE #86](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/86) PENDING.
- Прибор не подключался, AUX4700/VALUES не подменяются вычисляемым FFT; оригинальные PAS/DFM/IDP/BIN/PCAPNG/коэффициенты не публиковались.

## Открыто — точка Stage111V

Нужны независимые фактические оригинальные FRange и GraphDefaultVScale на одинаковом канале/режиме, особенно на точных границах 2/5/10 и значениях менее 1; семантика Delphi x87 helper `00447DB8/00447DF0/00447EF8`; оригинальные TPaintBox Canvas.Font/Size/DPI/PixelRect/CursorString, FormatFloat, GetSpectrum/GetNarrowbandValue/FRange/FFT. До золотой сверки не включать source-model как авторитетный Y Qt.

[Полный отчёт Stage111U](STAGE111U_GRAPH_DEFAULT_VSCALE_RU.md) · [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [новый чат](../../START_NEW_CHAT_RU.md).

Проверить все CI на SHA `a2a0651903c04638bc08fb983a415563df74c7f4`, `verified-dist/BUILD_VERIFICATION.json` и скачанную копию EXE по SHA256. Стабильный main/Web v0.3.40 и реальный прибор без разрешения не трогать.
