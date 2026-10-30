# MVKView Compatible — актуальный статус Stage111V (30.10.2026)

**Цель:** полноценная автономная Windows MVKView Compatible на Qt/PySide6 в папке mvk_compatible/. Рабочая ветка research/stage111-mvkview-desktop-20261029. Замороженные main и старая Web v0.3.40 не менять.

**Последний программный SHA:** f87ea7a38d3d62e1d91479a661b713a69d6bd8bf.

## Сохранённое состояние

- **Stage111U полностью прошёл CircleCI** на исходном SHA a2a0651903c04638bc08fb983a415563df74c7f4: Linux #85 SUCCESS, Windows Qt #84 SUCCESS, Windows Preview EXE #86 SUCCESS. Скачать и независимо проверить байты EXE по SHA256SUMS ещё не удалось. Артефакт внутри CircleCI опубликован только из verified-dist.
- Stage111V: из оригинальных приватных Delphi реконструкций Projects.7z прочитаны тела математических helpers 00447DB8 (FLDLG2/FYL2X), 00447DF0 (Power Extended), 00447EF8 (Power Single, целая ветвь/FSCALE). System.@FpuInit по адресу 00409570 загружает управляющее слово из 008C2028. **Настоящий original runtime FPU CW неизвестен.**
- Добавлен source-derived native x87 C-пробник без сети, без ввода реальных данных и без подключения МВК. Он выполняет команды x87 на x86/AMD64 и проверяет 27 синтетических комбинаций mode/FRange и 18 контрольных комбинаций PC=24/53/64. Пробник в пользовательский Windows EXE не включён.
- При синтетическом Linux CW=0x037F обнаружено совпадение Python-кандидата с аппаратным x87 по 27 случаям. PC24 изменяет младшие биты степенного расчёта: x=2 → 4.99999952 вместо 5.0 при PC53/64; x=20 → 49.9999962 вместо 50.0. Это НЕ эталон оригинальной MVKView.
- Локально 56 PASS на наборах Stage111U+111V (37 прежних и 19 новых). Новые Windows/Linux Core regression тесты проверяют ULP/режимы; native pytest SKIP без GNU x87.
- Последний source SHA f87ea7a38d3d62e1d91479a661b713a69d6bd8bf: [Linux #91](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/91) SUCCESS, [Windows Core+Qt #90](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/90) SUCCESS. Windows Preview EXE/скачанный SHA256 проверить по этому SHA отдельно.
- Qt-Y по-прежнему использует исследовательский ViewBox/data-derived GraphDefaultVScale; реальная source-driven калибровка не включена без оригинального golden.
- AUX4700/VALUES не заменялись локальным FFT; реальный прибор не подключался. Приватные PAS/DFM/IDP/BIN/PCAPNG не копировались в репозиторий.

## Непроверенное / следующий этап Stage111W

1. В приватной работающей оригинальной MVKView прочитать Get8087CW перед _Unit128:0084B631, исходное word 008C2028, оригинальное TMvkChannelStorage.FRange (+0x04) и реальный GraphDefaultVScale [esi+62C] по режимам 0–3. Доступ к прибору без отдельного разрешения запрещён.
2. Сопоставить частные Delphi golden с x87 helper-кандидатом при точных CW и FRange; затем проверять побитовый FormatFloat/x87/TRUNC, особенно вблизи 2/5/10. Пока original_math_helpers_x87_rounding_verified=False.
3. Проверить исходный runtime TPaintBox Canvas.Font/TextExtent/PixelRect/DPI, CursorString, GetSpectrum/GetNarrowbandValue/FRange/FFT, реальную вертикальную калибровку и UX трёх вкладок.
4. Для Stage111V/будущего HEAD проверить Windows Preview verified-dist EXE, BUILD_VERIFICATION.json и независимую копию по SHA256SUMS.

[Отчёт Stage111V](STAGE111V_X87_MATH_HELPER_RU.md) · [матрица](STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md) · [handoff](STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md) · [новый чат](../../START_NEW_CHAT_RU.md).

**Не утверждать полной исходной численной/пиксельной идентичности, пока оригинальный golden не проверен.**
