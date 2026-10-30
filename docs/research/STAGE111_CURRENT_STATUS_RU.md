# MVKView Compatible — Stage111Z.5 (30.10.2026): original Hann source + native x87 comparison

**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. Цель: полноценная автономная Windows Qt/PySide6 MVKView Compatible, не Web/сервер. [Полный отчёт Stage111Z.5](STAGE111Z5_HANN_SOURCE_AND_X87_PROBE_RU.md).

Оригинальный `mvkview.idp` локально read-only подтверждён по пяти SHA окна Hann-init `.itext:008C1064`, constants `008C10D0`, RTL FCOS `00407C00`, FSQRT `00407C58`, FFT consumer `007D2044..007D2088`. Таблица 262144 Float32 в BSS `0096DA48`: на индекс i — (1−x87.cos(2π*i/262144))/x87.sqrt(1.5), Extended temp, Single result, FFT stride=262144/N. Нативный source-derived GCC/x87 CW0x1372 vs текущий NumPy полный 262144 float32: **4 × 1 ULP различия** только i=1,5,262139,262143; на меньших FFT N с stride>=2 локально нет различий. **Original Delphi Windows runtime table и CW на её инициализации пока НЕ измерены**, поэтому автоматического изменения FFT candidate не делали.

**Новые файлы:** `private_hann_source_audit.py`, `native_probe/x87_hann_table_probe.c`, `tests/test_private_hann_source_audit.py`, `tests/test_stage111z5_native_hann_probe.py`. `Linux Core #172` SUCCESS на code SHA `3089c1c0e29dbedd05b847dba2a5c8324e8ac8be`; Windows Core+Qt/EXE и финальный docs commit отдельно проверять.

**NEXT Stage111Z.6:** x32dbg original read-only `dword:[96DA4C]` (index 1), `dword:[96DA5C]` (5), `dword:[9ADA48]` (65536), `dword:[9EDA48]` (131072). Сверить native/NumPy с true Delphi и только тогда при необходимости уточнить максимальный N=262144. Затем actual original FFT power/get-spectrum/cursor из архива; стабильные исходники и прибор не менять.

---

# MVKView Compatible — Stage111Z.4: original FFT twiddle rounding (30.10.2026)

**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`; цель автономная Windows Qt/PySide6. [Полный отчёт Stage111Z.4](STAGE111Z4_ORIGINAL_FFT_TWIDDLE_SINGLE_STORE_RU.md).

Оригинальный приватный FFT source по 7 окнам SHA подтверждён; GetSpectrum вызывает **+2π** wrapper `007CC3F8`, другой `−2π` wrapper не перепутан. Twiddle recurrence: intermediate **real** `FSTP Single` 007CC325, imaginary intermediate остается extended, финальные Wi/Wr Single 007CC33A/007CC344. Исправлен локальный `fft_idr_candidate.py` без изменения оригинальных файлов; добавлены bitwise synthetic tests и private IDP audit. Синтетический тест half=8192 показывает 989/8192 отличий коэффициентов от прежнего Double-пути, FFT N8192 имеет 1857/4096 изменений power. Это не исходная runtime FFT golden.

**CI:** SHA `0e231f2f59bd7f9ef6003f10f524b79a94d267f1` Linux #147 и Windows Core+Qt #148 — SUCCESS; SHA `5ae3c87737b4721a8e4f5d0564384cfad9373fd5` Linux #154 — SUCCESS, Windows и EXE отдельно проверять. Следующий этап Stage111Z.5: Hann table source/sin, x87 FFT и оригинальные архивные спектры, курсор, Canvas; никакой подмены Qt Y-оси без true golden. `main`, Web v0.3.40, прибор и приватные материалы не затрагивать.

---

# MVKView Compatible — Stage111Z.3 (30.10.2026): оригинальный x87-путь спектра проверен

**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`; автономная Windows Qt/PySide6, не Web v0.3.40. **Последний исходный отчёт:** [Stage111Z.3](STAGE111Z3_SOURCE_SPECTRUM_X87_AUDIT_RU.md).

По приватному оригинальному IDP локально криптографически проверены исходный spectrum handler 0084B5D3..0084B882 и три math helper окна. Внутри 16 вызовов log10, 7 TRUNC, 4 Power Extended, 2 Power Single, восемь FSTP Single и multiplier 1/1/10/100. Добавлены безопасный приватный аудитор и synthetic-only tests; приватные bytes/measurement paths не публикуются. Четыре user-reported x32dbg golden Stage111Z (FRange=43FF4853, CW1372 при Tag0) совпали с нативным GNU x87 replay при этом CW, **это не всеобъемлющий оригинальный Delphi паритет**.

**Проверенный кодовый SHA теста:** `a1d5fb7976f322771c7e41339f976b95b94dce76`: [CircleCI Linux #123](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/123) SUCCESS, [Windows Core+Qt #124](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/124) SUCCESS. Windows EXE #125 и CI новых doc/комментариев — отдельно проверить. Подлинная Original Delphi на граничных FRange=2/5/10/1000 и Canvas/FFT/Cursor остаётся TODO; на 1000 native x87 vs Python кандидата имеются расхождения, не исправлять формулу вслепую.

**Следующий этап Stage111Z.4:** original runtime borderline golden без записи в прибор, потом точная проверка FFT/GetSpectrum/FormatFloat/TPaintBox; original и stable main/Web v0.3.40 не менять.

---

# MVKView Compatible — Stage111Z.2: native x87 CW1372 повтор четырёх runtime измерений (30.10.2026)

**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`. **Завершённый исследовательский шаг:** original x32dbg Tag0..3 ↔ нативный GCC x87; четыре выходных IEEE754 Single HEX совпали побитово с пользовательскими оригинальными наблюдениями при CW `1372`. Исходный x87 CW подтверждён у оригинала на Tag0, на остальных режимах CW ещё не снимался. **Это не аттестация всех x87 случаев или графики.**

**Новые файлы:** `mvk_compatible/native_probe/x87_graph_vscale_probe.c` (режим `--replay-hex`), `mvk_compatible/tests/test_stage111z2_native_cw1372_replay.py`, `docs/research/STAGE111Z2_NATIVE_X87_CW1372_REPLAY_RU.md`, предыдущие тесты Stage111Z/Z.1. **CI:** Linux Core #112 SUCCESS на программном SHA `e799842825cf7e7317a04d709b77be02f8ae0451`; последующие документационные коммиты и Windows/EXE проверять отдельно. **Граничный риск:** native CW1372 при exact FRange=1000 → 2000, Python →1000; original Delphi на этой точке НЕ измерен. Не заменять кандидата и не утверждать Delphi-паритет. [Полный отчёт](STAGE111Z2_NATIVE_X87_CW1372_REPLAY_RU.md).

**Далее Stage111Z.3:** независимый original boundary reference, source trace x87/FormatFloat/FFT/CursorString, Qt TPaintBox. Stable `main`, Web v0.3.40, промышленную сеть и приватные файлы не менять.

---

# MVKView Compatible — Stage111Y: оригинальный EXE совпал с IDP (30.10.2026)

**Ветка:** `research/stage111-mvkview-desktop-20261029`. Цель — автономная Windows Qt/PySide6 программа `mvk_compatible/`, **не** старый Web v0.3.40. Стабильная `main` заморожена.

**Подтверждение:** пользователь передал настоящий `mvkview.exe`, SHA-256 `585bcd4aeafa14d77780d4c74134ee98c1653df1dc37a2d2d4db7904754435c5`. Это PE32/i386 GUI, ImageBase=00400000, timestamp 2021-08-18T12:51:58Z. Приватный `Projects(1).7z` идентичен старому; ранее собранный `mvkview.idp` **точно совпадает по всем проверенным байтам** в оригинальных `.text` (4 969 156), `.itext` (11 844), `.data` (76 596). Другие исходные секции представляют imports/resources по-разному: полной байтовой идентичности всех секций не заявлять.

**Где брать runtime golden в x32dbg:** первая остановка `0084B631` — до log10, вторая `0084B882` — после записи `Single [ESI+0x62C]`. При базе 00400000 RVA 0044B631 / 0044B882. На первой остановке собрать реальный x87 Control Word с FPU панели, индекс канала `[EBP-4]`, FRange `[[ESI+0x21124+4*idx]+4]` (концептуальный путь, не буквальная x64dbg команда), тип спектра `[[ESI+0x5A8]+0x0C]`, входное значение `[ESI+0x62C]`. На второй — итоговый `GraphDefaultVScale` (`[ESI+0x62C]`), CW и тот же канал. Достаточно 2 скриншотов или приватного `MVKVIEW_RUNTIME_X87_GOLDEN_V1` JSON. **Реальный прибор не подключать.** x32dbg-инструкция/исследовательский verifier изначально собраны в ZIP-артефакт беседы, исходные EXE/IDP туда не включены.

**Предыдущая версия кода Stage111X:** `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`, [Linux #97](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/97), [Windows Core+Qt #96](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/96), [Windows Preview EXE #98](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/98) — **SUCCESS**. SHA-256 отдельно скачанного собранного EXE не сверялся.

**Открыто:** оригинальный Windows runtime `Get8087CW` при вычислении, фактический FRange выбранного канала и итоговый GraphDefaultVScale, Delphi x87/FormatFloat/CursorString/FFT/TCanvas. **Их не выдумывать**. Статический `0x1332` — лишь CW при исходной инициализации в файле; оригинальный runtime может меняться. После получения двух снимков сопоставить побитово через `private_x87_runtime_reference_compare.py`, затем двигаться к точной Qt Y-оси и остальным численным модулям.

[Stage111Y отчёт](STAGE111Y_ORIGINAL_EXE_IDENTITY_AND_RUNTIME_CAPTURE_RU.md) · [Stage111X отчёт](STAGE111X_ORIGINAL_X87_CALLSITES_AND_GOLDEN_RU.md) · [Матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [Продолжить в новом чате](../../START_NEW_CHAT_RU.md).

**Сохранять закрытые EXE/IDP/PAS/DFM/производственные BIN/PCAPNG только локально; в публичном GitHub только производные выводы и безопасный скрипт.**
