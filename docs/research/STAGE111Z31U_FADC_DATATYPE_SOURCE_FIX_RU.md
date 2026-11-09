# Stage111Z31U — source-derived FAdcDataType 0, восстановление B на EIP 14AA

Дата: 09.11.2026. Приоритет: **только СПЕКТР**, оригинальная огибающая/Y на одном окне BIN. Рабочая ветка `research/stage111-mvkview-desktop-20261029`, без изменений `main` / основного Native R6.1.

## Полученное наблюдение пользователя

После Stage111Z31T пользователь (x32dbg paused, EIP `007D14AA`, ранее `[EBX+8]=0x14`) выполнил B из того же `C:\MVK_CAPTURE\Z31R_20261109_115102_88200486`. Скрин:

```text
Z31R_PREFLIGHT_OK: original image instruction anchors match IDP
Z31R_B_RESUME: continuing from CURRENT EIP=007D14AA with code20
Z31R_FAIL_STORAGE: invalid storage pointer or FAdcDataType not 1 (float ring).
Z31R capture aborted safely.
```

Скрин **не содержит фактического значения `dword:[dword:[ebp-4]+0C]` и не доказывает**, что хранение действительно Float32. Однако теперь скрипт проходит старый buggy `bpc` и останавливается на **ошибочной проверке enum**: ранее авторство синтетики требовало type1 без анализа original Constructor.

## Непосредственная проверка оригинального Delphi-дизассемблированного исходника

`Projects.7z`, `_Unit115.pas` (только локальная проверка; не коммитить PAS/IDP):

- `TMvkChannelStorage.Create` `007D0A04..007D0A2F`: `mov eax,[esi+0C]`, `sub eax,1`, `jb 007D0A11` (**только исходный тип 0**, выделение Float32 `[esi+34]`); `dec eax`, `je 007D0A22` (**только исходный тип 2**, выделение Byte `[esi+30]`); иначе `Invalid data type`. **Вывод: код 0 = Float32, код 2 = Byte, код 1 не Float32.**
- `007D2228..007D22FD` использует такую же развилку на `FAdcDataType` при чтении исходной кольцевой истории. `007D13E4` сохраняет `TMvkChannelStorage*` по `[EBP-4]` в `GetSpectrum` — это подтверждает позицию указателя для x32dbg.
- Прежняя Z31R v1.4 неверно требовала `dword:[storage+0C]==1` и имела **те же ложные значения 1 в `Verify-Capture.py` и синтетических тестах**. Их зелёный CI не доказывал правильность enum. Для byte type2 требуются другие критерии и интерпретация ring; текущая задача сохраняет reject type2, не обманывает Float32.

## Реализовано

Исходный коммит [`fcbbca15`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/fcbbca150bf53eb3f8ba65f8b6e2e9d3b0c387e7), исправленный workflow [`3e8dfac1`](https://github.com/shonentez-afk/MVK-Reader-Web/commit/3e8dfac10278aa2230ffecd4137f4405e0fe8691).

- A и B шаблоны: проверяют **type0**; до чтения полей хранилища усилена валидация `mem.base(storage)` и последнего байта объекта (56 байт); добавлен `Z31R_B_STORAGE_PROBE` с PTR/тип/Fs, отдельный `Z31R_FAIL_STORAGE_TYPE` вместо объединённого `FAIL_STORAGE`. Остальные ptr/EBP/EBX/TID/ring/no-zero-padding/отсутствие bpc сохранены.
- `Verify-Capture.py`: читает type0; типы 1/2/3 заведомо отклоняет, добавлена отметка `source_ring_adc_datatype=0`.
- `Fix-Existing-Storage.ps1`: исправляет **ранее подготовленный** `RESUME_B_FROM_14AA.txt` только при точном старом состоянии, соответствии `capture_config.json`/SHA и коде20, создаёт резервную копию B и предыдущего B-лога, сохраняет A и исходный архив, обновляет SHA. Выдаёт `Z31R_STORAGE_PATCH_OK`. Не запускает x32dbg и не возобновляет программу. v1.4 `Fix-Existing-B.ps1` уже выполнен на ПК ранее; повторно запускать его нельзя.
- Новые тесты используют исходный тип0; добавлены отрицательные кейсы для type1, type2, type3. Локально **21/21 PASS**.
- Пакет `MVK_STAGE111Z31R_TWO_MODE_X32DBG_CAPTURE_v1_5_STORAGE_FIX.zip`, **32 543 байта**, SHA256 `7aff9e0546bff112f5e7001e089a9c975ce996bd9350b1529049328b2fbead5d`. В ZIP оригинальные измерения/EXE/IDP отсутствуют.
- [GitHub Actions #42566735159](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42566735159) **2/2 SUCCESS**: Linux 21 PASS, Windows 21 PASS, физический Windows PowerShell5.1 smoke `Z31R_STORAGE_PATCH_OK` и проверка прежнего состояния/backup/SHA/A untouched. Это **не original x32dbg runtime PASS**.

## Следующий операторский шаг, НЕ терять EIP

Если оригинальный MVKView/x32dbg ещё **Paused EIP=007D14AA** и код фильтра `[EBX+8]=0x14`:

1. В командной строке x32dbg прочитать **без продолжения процесса** `dword:[ebp-4]` (адрес Storage), затем `dword:[dword:[ebp-4]+0x0C]` (FAdcDataType). **Если не `00000000` или указатель недоступен, прислать результат и не запуска́ть B**.
2. Если тип0, распаковать ZIP v1.5 в `C:\MVK_TOOLS\Z31R_V15\` и выполнить PowerShell патчер с реальным путём:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\MVK_TOOLS\Z31R_V15\MVK_STAGE111Z31R\Fix-Existing-Storage.ps1" -RunFolder "C:\MVK_CAPTURE\Z31R_20261109_115102_88200486"
```
3. После `Z31R_STORAGE_PATCH_OK`, только когда x32dbg всё ещё Paused на 14AA/code20:
```text
scriptexec "C:\MVK_CAPTURE\Z31R_20261109_115102_88200486\RESUME_B_FROM_14AA.txt"
```
4. При `Z31R_FAIL_*` сохранить полный лог/строку `Z31R_B_STORAGE_PROBE`, не нажимать F9 и не отключать guards. При успешном B сохранить физические B снимки; `Z31R_BOTH_COMPLETE` **не означает**, что A уже снят. Позже добрать обычный A и сравнить same-window/полный Y.

Приватные PAS/IDP/BIN/оригинальные дампы **не публикуются в GitHub**, desktop/app math/Native/FRange/FFT/FIR/Tag0–3 не менялись. Приоритет `СПЕКТР -> ВРЕМЕННОЙ СИГНАЛ -> РАСЧЁТЫ -> ОСТАЛЬНЫЕ СТРАНИЦЫ`.
