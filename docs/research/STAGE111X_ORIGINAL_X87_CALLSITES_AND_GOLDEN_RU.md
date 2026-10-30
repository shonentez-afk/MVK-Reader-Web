# Stage 111X — контроль путей изменения FPU и битовая сверка приватного эталона

**Дата:** 30.10.2026  
**Рабочая ветка:** `research/stage111-mvkview-desktop-20261029`  
**Программный SHA:** `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`  
**База Stage111W:** `ec3f370dde8b107a9e8881a402f63b198877e244`.

## 1. Приёмка Stage111W

Для программного SHA `080dcddbb65a8d199ea444ac9ae8d3676ac5e57f` через GitHub статус CircleCI **подтверждено SUCCESS** для [Linux #93](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/93), [Windows Core+Qt #94](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/94), [Windows Preview EXE #95](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/95). EXE собирался через `verified-dist`, дважды проверялся до публикации. **Независимую сверку скачанной копии EXE по SHA256SUMS не выполняли.**

Цель остаётся прежней: полноценная автономная Windows MVKView Compatible, не старая Web v0.3.40.

## 2. Установлено непосредственно по приватному оригиналу

В `mvkview.idp` (не публиковать) повторно проверены исходные машинные инструкции, а не только названия реконструированных процедур `System.pas`.

| Категория | Подтверждённые адреса / смысл |
|---|---|
| Начальное статическое CW | `.data:008C2028` = **0x1332**, PC64, RC-nearest, mask 0x32 |
| Прямые обращения к `Set8087CW` | **0041BD84**, **0041BDDA**, **00448296** — 3 code-aligned `CALL rel32` |
| Прямые обращения к `Get8087CW` | **0041BD4A**, **0041BDA2**, **00448261**, **00448281** — 4 |
| Прямые обращения к `@FpuInit` | **0040AADC**, **0040AC02**, **0040B02A**, **0040B61B**, **008BF072** — 5 |
| Две обёртки внешних вызовов | Сначала `Get8087CW`, затем внешний вызов, затем `Set8087CW` с ранее сохранённым CW (`0041BD84`, `0041BDDA`). Поэтому нельзя считать любой внешний вызов необратимой сменой FPU |
| Помощник масок исключений | `00448288–00448296` сохраняет старшие 10 бит CW (`AND AX,0xFFC0`) и меняет младшие шесть; **не должен менять PC/RC** |
| Преобразование строк в числа | `0042EBC1`: сохраняет прежний CW; `0042EBC8`: загружает `FLDCW [008C45F0]` = **0x133F** (PC64, RC-nearest, mask 0x3F); `0042EC68`: восстанавливает прежний CW локальной переменной |

**Ключевой новый вывод:** даже при исходной инициализации `0x1332` в оригинальном процессе существуют временные переключения CW, хотя в двух изученных видах вызовов прежнее значение восстанавливается. Более того, исходная программа содержит пути с вызовом `Set8087CW`, поэтому **нельзя утверждать**, что в момент `_Unit128:0084B631` всегда активно `0x1332`, не измерив `Get8087CW` непосредственно перед расчётом.

Поиск `E8 rel32` в `.text`/`.itext` строго проверен на известном бинарном образе. Это **поиск кандидатов инструкций**, не доказательство отсутствия непрямых вызовов, произвольных `FLDCW` и других изменений FPU среды. Аудитор намеренно сохраняет `all_indirect_calls_and_arbitrary_fpu_state_writers_excluded=False`.

## 3. Изменения в GitHub

- **`mvk_compatible/private_x87_callsite_audit.py`**: read-only офлайн-аудитор исходного локального IDP; сначала проверяет прошлый Stage111W `0x1332` + исходные сигнатуры, затем все прямые `CALL`/CW-восстановления/временное `0x133F`, отказывается от непроверенного дополнительного `CALL`. Наружу выводит только агрегаты и структурные флаги, не исходные байты или пути.
- **`mvk_compatible/private_x87_runtime_reference_compare.py`**: приватный офлайн-компаратор для будущей **настоящей** Delphi runtime записи. Контракт `MVKVIEW_RUNTIME_X87_GOLDEN_V1`: каждое наблюдение содержит `mode`, `f_range_bits` (восьмизначный IEEE Single hex), `graph_default_vscale_bits` (Single hex), `runtime_cw` (четырёхзначное hex). Рассчитывает побитовые совпадения, расстояние в ULP, группы PC/RC и статистику граничных значений.
- **Тесты `test_private_x87_callsite_audit.py` и `test_private_x87_runtime_reference_compare.py`**: только искусственные IDR-секции и искусственные числа, без копирования реального IDP/измерений; отказы при изменённых инструкциях, неизвестных `CALL`, недопустимых Single и ошибочной схеме.

**Локальная регрессия:** полный доступный набор офлайн-тестов Stage111U–X: **100 PASS** (`python -m pytest -q mvk_compatible/tests --ignore=mvk_compatible/tests/test_desktop_qt.py` в изолированной локальной копии). Проверено фактическое выполнение аудитора на приватном оригинальном `mvkview.idp`: 3 Set / 4 Get / 5 FpuInit, временное 0x133F и восстановления; в GitHub отправлен **только исходный текст новых инструментов и синтетические тесты**.

**Программный SHA** `0d1c36f431e23b0cf5eb58df839d92abbb1467e1`. [Linux Core #97](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/97), [Windows Core+Qt #96](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/96): **SUCCESS**. [Windows Preview EXE #98](https://circleci.com/gh/shonentez-afk/MVK-Reader-Web/98): PENDING. Windows EXE запускается после обоих успешных Core; `BUILD_VERIFICATION.json`/скачанную копию проверять отдельно.

## 4. Приватный контракт будущей runtime-сверки (синтетический пример)

```json
{
  "schema": "MVKVIEW_RUNTIME_X87_GOLDEN_V1",
  "records": [
    {
      "mode": 1,
      "f_range_bits": "0x3F800000",
      "graph_default_vscale_bits": "0x3F800000",
      "runtime_cw": "0x1332"
    }
  ]
}
```

**Это исключительно синтетический пример схемы, НЕ эталон оригинальной Delphi.** Для реальных наблюдений все числа и контрольное слово нужно снимать из **одной и той же оригинальной сессии** на одном канале, без подключения МВК. Команда локального запуска:

```powershell
python -m mvk_compatible.private_x87_callsite_audit "C:\Private\mvkview.idp"
python -m mvk_compatible.private_x87_runtime_reference_compare "C:\Private\original_runtime_x87_golden.json"
```

Никогда не публиковать реальный JSON или оригинальные IDP, PAS, DFM, BIN, PCAPNG. Компаратор не аутентифицирует происхождение введённых данных и **намеренно возвращает** `operator_provided_runtime_values_independently_authenticated=False`, `original_delphi_bitwise_parity_accepted=False`, даже при 100% совпадении синтетики.

## 5. Следующая точка — Stage111Y

1. Довести CI именно для Stage111X программного SHA до Linux, Windows Qt и Windows `verified-dist` EXE. Независимо скачать EXE и сравнить с SHA256SUMS (это не подтверждено предыдущими успешными проверками).
2. В приватном **работающем оригинале MVKView без прибора** получить `Get8087CW` непосредственно перед `0084B631`, фактический `TMvkChannelStorage.FRange` (+4), `GraphDefaultVScale` (+0x62C), тип спектра и окно. Если действующий оригинальный EXE/процесс недоступен — не выдумывать golden значения и не объявлять runtime паритет.
3. Сопоставить `FYL2X` и `Power Extended/Single` по битам в режиме действительно наблюдавшегося original CW, особенно для `log10(1000)`, границ 2/5/10 и их соседних float32. Уточнить x87 `@TRUNC` и `FormatFloat`.
4. Параллельно продолжить TPaintBox.Canvas.Font/DPI/PixelRect/CursorString и `GetSpectrum/FRange/Narrowband/FFT` на одном оригинальном офлайн-окне. Только при аттестованном численном совпадении заменять исследовательскую Qt Y-ось.
5. Stable `main`, Web v0.3.40, аппаратный прибор и оригинальные закрытые файлы не трогать.

**Статус:** подтверждённый **статический путь** управления FPU расширен; **live original FPU CW, FRange и GraphDefaultVScale остаются непроверенными**. 
