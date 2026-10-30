# MVKView Compatible — Stage111Y: оригинальный EXE совпал с IDP (30.10.2026)

**Ветка:** `research/stage111-mvkview-desktop-20261029`. Цель — автономная Windows Qt/PySide6 программа `mvk_compatible/`, **не** старый Web v0.3.40. Стабильная `main` заморожена.

**Подтверждение:** пользователь передал настоящий `mvkview.exe`, SHA-256 `585bcd4aeafa14d77780d4c74134ee98c1653df1dc37a2d2d4db7904754435c5`. Это PE32/i386 GUI, ImageBase=00400000, timestamp 2021-08-18T12:51:58Z. Приватный `Projects(1).7z` идентичен старому; ранее собранный `mvkview.idp` **точно совпадает по всем проверенным байтам** в оригинальных `.text` (4 969 156), `.itext` (11 844), `.data` (76 596). Другие исходные секции представляют imports/resources по-разному: полной байтовой идентичности всех секций не заявлять.

**Где брать runtime golden в x32dbg:** первая остановка `0084B631` — до log10, вторая `0084B882` — после записи `Single [ESI+0x62C]`. При базе 00400000 RVA 0044B631 / 0044B882. На первой остановке собрать реальный x87 Control Word с FPU панели, индекс канала `[EBP-4]`, FRange `[[ESI+0x21124+4*idx]+4]` (концептуальный путь, не буквальная x64dbg команда), тип спектра `[[ESI+0x5A8]+0x0C]`, входное значение `[ESI+0x62C]`. На второй — итоговый `GraphDefaultVScale` (`[ESI+0x62C]`), CW и тот же канал. Достаточно 2 скриншотов или приватного `MVKVIEW_RUNTIME_X87_GOLDEN_V1` JSON. **Реальный прибор не подключать.** x32dbg-инструкция/исследовательский verifier изначально собраны в ZIP-артефакт беседы, исходные EXE/IDP туда не включены.

**Предыдущая версия кода Stage111X:** `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`, [Linux #97](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/97), [Windows Core+Qt #96](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/96), [Windows Preview EXE #98](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/98) — **SUCCESS**. SHA-256 отдельно скачанного собранного EXE не сверялся.

**Открыто:** оригинальный Windows runtime `Get8087CW` при вычислении, фактический FRange выбранного канала и итоговый GraphDefaultVScale, Delphi x87/FormatFloat/CursorString/FFT/TCanvas. **Их не выдумывать**. Статический `0x1332` — лишь CW при исходной инициализации в файле; оригинальный runtime может меняться. После получения двух снимков сопоставить побитово через `private_x87_runtime_reference_compare.py`, затем двигаться к точной Qt Y-оси и остальным численным модулям.

[Stage111Y отчёт](STAGE111Y_ORIGINAL_EXE_IDENTITY_AND_RUNTIME_CAPTURE_RU.md) · [Stage111X отчёт](STAGE111X_ORIGINAL_X87_CALLSITES_AND_GOLDEN_RU.md) · [Матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [Продолжить в новом чате](../../START_NEW_CHAT_RU.md).

**Сохранять закрытые EXE/IDP/PAS/DFM/производственные BIN/PCAPNG только локально; в публичном GitHub только производные выводы и безопасный скрипт.**
