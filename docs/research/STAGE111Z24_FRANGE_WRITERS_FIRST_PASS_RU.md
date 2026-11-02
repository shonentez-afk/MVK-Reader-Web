> **ИСПРАВЛЕНИЕ / SUPERSEDED (02.11.2026):** Этот промежуточный вывод о том, что live writer `Storage.FRange` не найден, **ошибочен**. На Stage52 (28.10.2026) он УЖЕ установлен: `_Unit125:0080863D` вызывает `00806964` (канальный `GetFloatByAddr(0x0E)`), затем `_Unit125:00808653 fstp dword ptr [eax+4]` записывает в `TMvkChannelStorage.FRange`. Повторно сверено с приватным оригинальным `_Unit125.pas`. Источник архивного FRange отдельно проверен на Stage61/62 (`_Unit128:0084655E`). Полная актуальная сверка, включая готовый/проверенный Native R6.1: **[STAGE111Z24_RECHECK_STAGE52_FRANGE_AND_NATIVE_R6_1_RU.md](STAGE111Z24_RECHECK_STAGE52_FRANGE_AND_NATIVE_R6_1_RU.md)**. Нижеследующая часть сохранена как **исторический first-pass**, не как список открытых задач.

# Stage111Z.24 — первичная карта записи FRange (статический аудит)

Дата: 02.11.2026. Статус: **PARTIAL / не подтверждено runtime**.

## Источник и область

Локально прочитан приватный `Projects.7z`, включая IDR `_Unit115.pas`, `_Unit125.pas`, `_Unit128.pas`. Приватный архив, PAS, IDP и данные измерений **не добавляются в GitHub**. Проверка выполнена по тексту реконструкции; наличие комментария IDR не доказывает отсутствие других косвенных записей в поле.

## Подтверждённые статические присваивания

| Путь | Адрес | Действие | Уровень |
|---|---|---|---|
| `TMvkChannelStorage.Create` | `_Unit115:007D0A61` | `[esi+4] = 0x3F800000` ⇒ `FRange = 1.0f` при создании Storage | VERIFIED static |
| Оригинальный файловый loader | `_Unit128:0084653A..0084655E` | `TMvkChannelStorage.Create`; затем `[ebx+4] = [ebp-2C]`, где `ebx` — новый Storage | VERIFIED static |
| Original BIN processing | `_Unit115:007D23D5` | `fmul [ebx+4]` при `ProcessBufferChunk`; это **чтение**, не запись | VERIFIED static |
| Live data path | `_Unit125:00808284..008082DE` | `ProcessBufferChunk` до `ChannelFile.Write`, shared memory alias, как установлено в Z.23 | VERIFIED static |

Архивный loader вычисляет `[ebp-2C]` через ветвление `_Unit128:008464CB..00846513`: для fallback есть `0x42C80000` (100.0f) или деление значений cell list по адресам `0x20` и `0x02`; при другой ветке используется ранее разобранный `InternalChannelGain`. Эти ветви нельзя объединять в один физический коэффициент без проверки условий переходов.

## Важное ограничение

**Живой runtime writer `Storage.FRange`, отличающийся от инициализации конструктора, пока не аттестован.** Поиск по именованным IDR-комментариям показал записи конструктора и файлового loader, но не служит исчерпывающим alias-analysis всех инструкций `[reg+4]` во всех модулях. Не утверждать, что live FRange всегда равен 1.0, или что он обязательно равен TSXML gain.

## Следующая проверка

1. Построить индекс всех созданий `TMvkChannelStorage` и установок `[object+4]` в оригинальном IDR; разрешить алиасы указателей и стековые temporary references.
2. Для live канала проверить присваивания `FRange` после конструктора, перед `ProcessBufferChunk`, включая переходы по типу ADC, режиму и конфигурации.
3. Только после read-only same-run original BIN + TSXML + memory snapshots сопоставлять original `GetSignal`/`GetSpectrum` и TCP; до этого физические единицы оставить **не подтверждены**.
4. Сохранить Stage111Z.8/Z.10 FFT golden, текущий Windows Qt source и stable main без изменений.

Результат этапа: **подтверждены две явные точки инициализации/присваивания, но полный live FRange source-map ещё не завершён**.
