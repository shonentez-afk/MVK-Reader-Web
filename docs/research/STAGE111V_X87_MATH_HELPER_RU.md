# Stage 111V — исходные математические помощники x87 и режим точности FPU

**Дата:** 30.10.2026
**Ветка:** research/stage111-mvkview-desktop-20261029
**Точный программный SHA:** f87ea7a38d3d62e1d91479a661b713a69d6bd8bf
**Первый программный SHA этапа:** cd045eb8c2474c0f73055c855194d32cc72fa62e
**Исходная база Stage111U:** 8fe1835f1288f502734eff585c2e8f5c618fdaa0

## 1. Проверка предыдущего этапа

Stage111U source SHA a2a0651903c04638bc08fb983a415563df74c7f4:
- [Linux Core #85](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/85) — SUCCESS.
- [Windows Core+Qt #84](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/84) — SUCCESS.
- [Windows Preview EXE #86](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/86) — SUCCESS.

Внутренний проверочный процесс CircleCI проверяет PE/SHA256/commit и публикует verified-dist. Скачанный EXE и его SHA256 отдельно пользователем не сверялись. CI не означает оригинальный численный или графический паритет Delphi.

## 2. Исходные оригинальные math helper — впервые восстановлены

В приватном архиве Projects.7z непосредственно прочитаны реконструированные Winapi.Messages.pas и System.pas. Исходные PAS/IDP/DFM, BIN/PCAPNG и коэффициенты **не копировались в GitHub/CI**.

| Исходный адрес | Прямо подтверждённая структура |
|---|---|
| 00447DB8–00447DC4 | FLDLG2 → FLD Single → FYL2X; log10(x) на x87, результат Extended в ST(0) |
| 00447DF0–00447E6F | Power(base, Extended exponent): FRNDINT и быстрый путь целого exponent; для дробного FLDLN2/FYL2X/FMULP/FLDL2E/F2XM1/FSCALE |
| 00447EF8–00447F77 | Power(base, Single exponent), отдельная целочисленная ветка возведения в степень через последовательное возведение в квадрат |
| 00407664 / 00407674 | Set8087CW / Get8087CW в System.pas |
| 00409570–00409579 | @FpuInit: FNINIT и затем FLDCW из глобального оригинального слова 008C2028 |

Дополнительная процедура 0044827C из Winapi.Messages.pas меняет младшие шесть битов маски исключений x87 через Get8087CW и Set8087CW, но сама не устанавливает PC=24/53/64. Исходные логарифм и степенные helper тоже непосредственно не устанавливают precision-control.

**Содержимое оригинального глобального CW 008C2028 и настоящий Get8087CW оригинальной MVKView перед спектральным обработчиком пока неизвестны**. Нельзя приравнивать CW Linux-пробника к Windows Delphi.

## 3. Реально работающий аппаратный x87-пробник

Добавлен независимый mvk_compatible/native_probe/x87_graph_vscale_probe.c, который строится только через GCC на x86/x86_64 и не входит в пользовательский Windows EXE. В нём используются настоящие инструкции x87 FLDLG2, FYL2X, FSTP Single, FRNDINT, FLDLN2, F2XM1, FSCALE. Целочисленный Power приближён к структуре исходного 00447EF8, но оригинальная побитовая идентичность не заявляется.

- --selftest: 27 фиксированных **синтетических** входов: 21 обычный/пограничный Single (включая ближайшие float32 ниже/выше 2, 5, 10), плюс 6 проверок режимов 0–3.
- --precision-sweep: шесть фиксированных синтетических значений для трёх precision-control (PC=24/53/64), всего 18 комбинаций. До и после пробы сохраняется/восстанавливается управляющее слово FPU.
- При отсутствии GCC или x87-совместимого процессора native pytest SKIP, чистые Python-тесты ULP продолжают проверяться.
- Пробник не принимает реальные параметры пользователя: нет открытия приборных файлов, подключения к сети или доступа к МВК.

Локально протестирована сборка (GCC x86_64) и оба режима. Локальное CW процесса до проб = 0x037F, PC=64. Исходная модель Python Stage111U совпала с результатом аппаратного x87 для 27 синтетических записей при обычном CW.

### Синтетические результаты около границ (mode 1, локальный PC=64)

| Вход | Выход x87 |
|---|---:|
| Single непосредственно ниже 2 | 2 |
| Ровно 2 | 5 |
| Single непосредственно ниже 5 | 5 |
| Ровно 5 | 10 |
| Ровно 10 | 10 |
| Single непосредственно выше 10 | 20 |

Благодаря сохранению промежуточного log10-разложения в Single пороги могут вести себя не как идеальный математический ceiling 1–2–5. Это подтверждено локальным x87, но **НЕ** эталоном оригинальной Delphi MVKView.

### Влияние режима точности

| Синтетическое значение | x87 PC=24 | x87 PC=53/64 |
|---|---:|---:|
| 2 | 4.99999952 | 5.0 |
| 20 | 49.9999962 | 50.0 |

Это наблюдение подтверждает, что совпадения операций и выбранной ступени недостаточно: для точного численного паритета требуется узнать **реальный FPU CW оригинального процесса**. Использовать указанные аппаратные числа для молчаливой подмены пользовательского GraphDefaultVScale нельзя.

## 4. Код и тестирование

- Новый native C: mvk_compatible/native_probe/x87_graph_vscale_probe.c.
- Новый pytest с компиляцией GCC и контрольным прогоном: mvk_compatible/tests/test_x87_graph_vscale_native_probe.py.
- Новый platform-independent чистый Python ULP/отрицательный log10 регресс: mvk_compatible/tests/test_graph_default_vscale_x87_boundary_regression.py.
- В существующем spectrum_graph_default_vscale_idr_candidate.py сохраняется флаг original_math_helpers_x87_rounding_verified=False, а в GUI оригинальная Qt Y-ось по-прежнему исследовательская: никаких неаттестованных замен.
- Локально в одном прогоне прошли **56 тестов** (37 ранее реализованных Stage111U + 14 новых Python ULP + 5 native x87). Windows-билд может отмечать native GCC-тесты SKIP без установленного компилятора.

## 5. CI

Первый SHA cd045eb8c2474c0f73055c855194d32cc72fa62e: [Linux #88](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/88) SUCCESS; [Windows Core+Qt #87](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/87) SUCCESS; [EXE #89](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/89) статус проверить.

Последний source SHA f87ea7a38d3d62e1d91479a661b713a69d6bd8bf: [Linux #91](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/91) **SUCCESS** и [Windows Core+Qt #90](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/90) **SUCCESS**. Windows Preview EXE проверять на том же SHA, отдельный пользовательский SHA256 не проверен.

Побайтовая приёмка скачанного EXE и оригинальная численная/пиксельная аттестация MVKView остаются отдельно не выполненными.

## 6. Следующий шаг — Stage111W

1. Проверить все CI последнего программного SHA, Windows Preview verified-dist EXE, BUILD_VERIFICATION.json и независимо скачанный SHA256.
2. В оригинальной офлайн Windows MVKView приватно получить **Get8087CW непосредственно перед 0084B631/0084B655**, глобальный исходный FPU CW 008C2028, FRange выбранного канала (TMvkChannelStorage +0x04) и результат GraphDefaultVScale [esi+62C] по режимам 0–3. Реальный прибор не подключать без разрешения, исходные значения и дампы в GitHub не публиковать.
3. Сопоставить Golden Delphi с Python/аппаратным x87 для float32 вокруг 2/5/10, затем доработать точный 00447DF0/00447EF8/@TRUNC и Qt Y viewport **только при доказанной идентичности**.
4. Продолжить Delphi FormatFloat, CursorString, TPaintBox Canvas.Font/DPI/PixelRect, FFT/GetSpectrum/FRange/Narrowband на одном приватном архивном окне.
5. Стабильные main, Web v0.3.40 и оригинальные приватные исходники оставить без изменений. Цель — единое автономное Windows-приложение MVKView Compatible, не Web/server.
