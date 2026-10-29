# Stage 111L — синхронизация с GitHub и подтверждённая офлайн-регрессия

**Дата:** 29.10.2026. **Статус:** файлы локального `MVKVIEW_STAGE111L_CURSOR_SOURCE_LOCAL_HANDOFF_20261029.zip` перенесены в рабочую ветку `research/stage111-mvkview-desktop-20261029` приватного репозитория `shonentez-afk/MVK-Reader-Web`. Это отдельный **исследовательский этап**, не доказательство полной численной/визуальной идентичности оригинальной MVKView.

## 1. Восстановление после сбоя GitHub connector

Соединение, недоступное во время подготовки локального Stage111L, **восстановлено**. GitHub подтвердил права чтения/записи для аккаунта. В пять файлов опубликована **побайтово точная копия** локального архива — проверено сравнением GitHub blob SHA с `git hash-object` тех же локальных файлов:

| Файл | Контрольный Git blob SHA |
|---|---|
| `mvk_compatible/core/tqgrapher_multiseries_idr_candidate.py` | `249f20bb0759fe607b9dd21495615e8feca5721f` |
| `mvk_compatible/cursor_reference_compare.py` | `bbd102a13633adf453a3ccaa204f4d8130b01618` |
| `mvk_compatible/tests/test_tqgrapher_multiseries_idr_candidate.py` | `4f6e05b2c88203182dfba9cc917257d41680516b` |
| `mvk_compatible/tests/test_cursor_reference_compare.py` | `7c1be1106f7205f25b4b88e918d075b73b06c20e` |
| `docs/research/STAGE111L_MULTISERIES_CURSOR_PARITY_RU.md` | `fd066141d80a5bce70813ee759ef4b66cd0e05af` |

Исходный отчёт `STAGE111L_MULTISERIES_CURSOR_PARITY_RU.md` сохранён в неизменном виде: его вступление о «ещё не опубликованном архиве» — **исторический статус в момент создания архива**. Текущий статус — в этом файле.

## 2. GitHub Actions — проверенные результаты

- [Run #40895765293](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/40895765293) — **SUCCESS**.
- Проверенный source HEAD: `01956c13e5f29e165cf28f974aecc24dc8380714`.
- Linux core: **347/347 PASS**.
- Windows core: **347/347 PASS**.
- Windows offscreen Qt: **12/12 PASS**.
- Windows PyInstaller EXE + SHA256SUMS: **SUCCESS**.
- Windows artifact: `MVKViewCompatible_Stage111_Windows_Preview`, ID **12906482967**, ZIP **66 513 363 байта**, истекает **12 ноября 2026 года в 14:55:03 UTC**.

Файлы Stage111L добавлены в обе команды Core workflow `.github/workflows/stage111-desktop-offline.yml` без удаления прошлых тестов. После указанного source HEAD менялась только проектная документация; проверенный исполняемый код не переписывался.

## 3. Что теперь есть и чего пока нет

Новый **изолированный** `original_multiseries_cursor` восстанавливает два ряда из исходных `_Unit115.pas:007CA76C–007CAAFB`: общая `YName`, независимый signed-максимум для каждого ряда, три разных величины pixel/index/snapped-line, исходное averaging 1/3 и защитный отказ при выходе за границы. `cursor_reference_compare.py` выполняет локальную проверку оригинальных `CursorString` и линии по private JSON/NPY/TXT без выхода в сеть, с SHA-256 и без публикации оригинальных строк/массивов. Это **не** приборные DSP/AUX4700.

**Важно:** новый двухрядный кандидат пока специально **не заменяет** рабочий Qt-курсор без подтверждённого оригинального Canvas. Точные оригинальные шрифтовые метрики, пиксельное начало, TFormatSettings/x87, входной BIN/окно и сравнение на реально запущенной оригинальной MVKView не подтверждены. Windows EXE — исследовательский Preview, а не релиз полного клона.

## 4. Продолжить Stage111M

1. Сначала читать оба ADR, `START_NEW_CHAT_RU.md`, `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md`, отчёт Stage111K, [Stage111L source report](STAGE111L_MULTISERIES_CURSOR_PARITY_RU.md) и этот подтверждённый GitHub QA.
2. На одинаковых исходных данных получить **оригинальный** TCanvas `PixelLeft/Right`, `TextWidth/Height`, `CursorString` при 1 и 2 рядах, высоту/ширину графика, локаль и DPI. Сравнить в приватном CLI без подгонки.
3. Только при совпадении исходного окна и координат интегрировать новый `original_multiseries_cursor` в Qt-обработчик; сохранять явную маркировку качества.
4. Продолжить восстановление Delphi `FormatFloat` (`007B2090`), FFT, вкладок и архивов. Live исключительно после отдельного разрешения, через один Native R6.1 Collector.
5. **Не менять** `main` и стабильную v0.3.40, не подключать прибор, не загружать оригинальные PAS/DFM/IDP/FIR/RAW/BIN/PCAP в GitHub.

Тесты синтетические; окончательный оригинальный численный и визуальный Delphi-parity **НЕ принят**.
