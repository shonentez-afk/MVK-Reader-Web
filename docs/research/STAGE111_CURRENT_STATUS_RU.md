# MVKView Compatible — текущий статус Stage111T (30.10.2026)

**Цель:** автономная Windows Qt/PySide6 MVKView Compatible, только `mvk_compatible/`, ветка `research/stage111-mvkview-desktop-20261029`. Стабильные `main` и Web v0.3.40 не менять.

**Проверяемый программный SHA:** `35f13a6fd0d420bb2b8f70eb7f9fe7495093c390`.

## Что реализовано

- Предыдущий Stage111S программный SHA `af036bdd1be4dfdf2481a416f73cc9759db355d4`: CircleCI Linux #75, Windows Core/Qt #76 и Windows verified-dist EXE #77 — **SUCCESS**. EXE после пользовательского скачивания отдельно не сверен по байтам.
- Stage111T: приватный источник Delphi `_Unit128` подтвердил вертикальный Full=150/Page 150…10 в dB; Full=100000/Page 100000…1 в физической шкале. Source mSpecType1Click сбрасывает V Tag=0/3 по режиму.
- В native Qt `bSpecVScale` теперь шесть исходных пунктов с правильным Page/Position/Max и обновлением Y-диапазона. **GraphDefaultVScale и Y-origin пока только Qt data-derived кандидат** с явными флагами parity=FALSE.
- `bSpecLines` теперь все шесть настоящих размеров FFT 262144,131072,65536,32768,16384,8192. Исследовательские 1024/4096 отдельно, не выдаются за оригинал.
- Недостаточная реальная история BIN или FIR/огибающей блокирует FFT до вычисления (без нулевого дополнения) и не затирает уже показанный спектр при недоступном выборе.
- Новая pure-core регрессия и Windows offscreen smoke tests на V Tag, Position/Max и синтетических BIN длиной 4096 и 8192, без оригинальных измерений.
- Stage111T CI: [Linux Core #79](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/79) SUCCESS; [Windows Core+Qt #78](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/78) **SUCCESS**; [Preview EXE #80](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/80) **PENDING**.
- Реальный прибор не подключался, AUX4700/VALUES не подменялись локальным FFT. Оригинальные PAS/DFM/IDP/производственные BIN/PCAPNG и закрытые коэффициенты не опубликованы.

## Не приняты / дальнейшие действия Stage111U

Исходный runtime `GraphDefaultVScale`, реальная калибровка Y, TPaintBox Canvas.Font/Width/Height/TextExtent/DPI/PixelRect, Delphi CursorString/FormatFloat/x87, оригинальные GetSpectrum/GetNarrowbandValue/FRange/FFT на том же архивном окне и полные UX трёх вкладок. Скачанный EXE SHA256 отдельно не проверен. CI pipeline — это техническая регрессия, не пользовательская приёмка аналога 1.0.

[Stage111T отчёт](STAGE111T_VERTICAL_AND_SOURCE_FFT_RU.md) · [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [новый чат](../../START_NEW_CHAT_RU.md).

Следующий шаг — подтвердить Windows Core/Qt/verified-dist EXE, затем приватный оригинальный GraphDefaultVScale, runtime Canvas, исходный FFT/RTL. `main`, Web и прибор без разрешения не изменять.
