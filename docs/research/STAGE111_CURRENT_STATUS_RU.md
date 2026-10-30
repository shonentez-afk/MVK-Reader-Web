# MVKView Compatible — текущий статус Stage111W (30.10.2026)

**Архитектура:** единое полностью автономное Windows-приложение Qt/PySide6 в `mvk_compatible/`. **Единственная рабочая ветка:** `research/stage111-mvkview-desktop-20261029`, stable `main` и Web v0.3.40 НЕ ТРОГАТЬ.

**Последний программный SHA:** `080dcddbb65a8d199ea444ac9ae8d3676ac5e57f`.

## Подтверждено на этом этапе

- Предыдущий Stage111V code SHA `f87ea7a38d3d62e1d91479a661b713a69d6bd8bf`: [Linux #91](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/91), [Windows Core/Qt #90](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/90), [Windows verified-dist EXE #92](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/92) — все SUCCESS. Скачанная пользователем копия EXE по SHA256SUMS отдельно не проверена.
- Stage111W приватно проверил **сам `mvkview.idp`**, формат IDR proj v3, 11 исходных секций. Исходное глобальное WORD `.data:008C2028` = **`0x1332`**, исходные инструкции `@FpuInit`, `Set8087CW`, `Get8087CW` и инициализация `TMvkChannelStorage.FRange=1.0` сверены непосредственно по машинным байтам в оригинальной секции.
- `0x1332` означает начальные x87 PC64, RC-nearest, маску исключений 0x32. На тестовом CPU FNSTCW после FLDCW вернул 0x1372 из-за reserved bit6. **Настоящий CW работающей original Delphi в момент спектра НЕ измерен**; фактический FRange выбранного канала тоже неизвестен.
- Новый `private_original_cw_idr_audit.py`: локальный IDR-секционный аудитор, не печатает путь/данные приватного файла. В GitHub нет оригинального IDP; тесты используют только synthetic IDR, специально проверяют подделки.
- Native x87 C-probe расширен `--source-static-cw`: 28 synthetic cases на четырёх режимах, восстановление caller CW. Выявлено существенное расхождение `FRange=10`, mode3: x87 → **2000**, Python кандидат → **1000** на границе логарифма 1000. Синтетика не приравнивается к original Delphi runtime golden.
- В `spectrum_graph_default_vscale_idr_candidate.py` и Qt диагностике добавлены source CW, признаки рискованных границ и запрет ложной аттестации. **Фактическая Qt Y-ось и DSP AUX4700/VALUES не подменялись**.
- Локальный исследовательский набор Stage111U/V/W: **79 PASS**. Последний SHA `080dcddbb65a8d199ea444ac9ae8d3676ac5e57f`: [Linux Core #93](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/93) SUCCESS, [Windows Core+Qt #94](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/94) SUCCESS, [Windows Preview EXE #95](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/95) PENDING на момент записи.
- Прибор не подключался. PAS/DFM/IDP/BIN/PCAPNG остаются приватными; данные пользователя не попали в GitHub или CircleCI.

## Открыто — Stage111X

1. Для последнего SHA проверить Windows verified-dist EXE #95, `BUILD_VERIFICATION.json`; скачать файл и независимо сверить SHA256SUMS.
2. В приватной работающей **оригинальной MVKView без прибора** измерить живые `Get8087CW` перед `0084B631`, `TMvkChannelStorage.FRange` (+4) и `GraphDefaultVScale` (+0x62C), тот же канал и окно, режимы 0–3. Особенно проверить границы 2/5/10/1000 и ULP.
3. После golden-оригинала уточнить `FYL2X`/Power Extended/Single/`@TRUNC`, `FormatFloat` и Qt Y. Не заменять продакшен-оси на Python-кандидата без независимой аттестации.
4. Продолжить TPaintBox.Canvas.Font/DPI/PixelRect/CursorString и GetSpectrum/GetNarrowbandValue/FRange/FFT на одном исходном офлайн-окне. Не подключать реальный прибор без разрешения, не менять stable main/Web.

[Отчёт Stage111W](STAGE111W_ORIGINAL_STATIC_FPU_CW_RU.md) · [матрица совместимости](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [START_NEW_CHAT](../../START_NEW_CHAT_RU.md).

**Примечание:** статическое source WORD = 0x1332 подтверждено, но runtime original x87 precision/rounding, фактический per-channel FRange и полный пиксельный/численный паритет всё ещё не приняты.
