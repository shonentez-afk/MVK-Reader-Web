> **ОБЯЗАТЕЛЬНОЕ ИСПРАВЛЕНИЕ Stage111Z31AG (10.11.2026):** в **первом** MCP отчёте исходные bytes `[EBX+20] = 33 80 08 00` были неверно расшифрованы как `0x00080033=524339`. Реально little-endian `0x00088033 = 557107`; `start=557107-262195=294912=StorageOldest`, **дефицит истории = 0**. Нет доказательства изменения WindowEnd во время Paused и нет оснований утверждать подмену. Аналогично `Storage+10 = 00 00 20 00` => capacity2097152. ZERO-PAD всё ещё есть в исходном коде как общий fallback, но этому окну не нужен. Preflight после ручного патча не есть runtime parity; rawN262195 → ожидаемый FFTN131072/Y65536. Полная проверка B остаётся OPEN. [Актуальный отчёт](docs/research/STAGE111Z31AG_ORIGINAL_LE_BYTE_ORDER_CORRECTS_HISTORY_RU.md).

# Stage111Z31AF — аудит сообщения GigaCode «STRUCTURAL_PREFLIGHT_PASS», 10.11.2026

**Статус: неподтверждённый PASS. Нельзя запускать B.** Исходные данные — только пересланный пользователем текст отчёта GigaCode; реальных новых MCP дампов нет.

GigaCode сообщает: исходная известная original пауза `EIP=007D14AA` PID1856, Env20/Mode0, rawN262195, изначальный `WindowEnd=524339`, `StorageOldest=294912`. Позже агент заявляет при «том же Paused процессе» `WindowEnd=557107`, `WindowStart=294912`, что ровно компенсирует deficit32768, и приписывает это накоплению 0.5 сек. Это противоречит паузе всех потоков процесса; альтернативы — снимки изменили в файлах, были дополнительные resumes/reentry или прочитан другой EIP/context. **Нет доказательства**, что текущая живaя память содержит end557107.

Проведена проверка `tools/research/stage111z31r_x32dbg_two_mode_capture/Preflight-GetSpectrum.py` прямо в актуальной ветке:
- Original expects `n=(DWORD[EBX+4])` FFT power of two <=262144 and demands `end-n>=oldest`, поэтому **нельзя** просто снять pow2 guard для source-stage5 rawN 262195 и считать остальные поля корректными;
- Original returns `fields.fft_n_samples = n`, `fields.fft_half_bins = n//2`; на rawN262195 это **131097**, что в отчёте GigaCode ошибочно представлено как `(262195-51)/2+1` (на деле 131073). В исходном канале FIR stage5 `(262195-51)/2=131072` expected postFIR `N`, `N/2=65536` original output bins (подтвердить на EIP153D и 17E7).
- Original `STRUCTURAL_PREFLIGHT_PASS_NOT_RUNTIME_ATTESTATION` expressly not an attestation of original paused memory or BIN identity.
- Отредактированные `params_at_14AA.bin`, `storage_at_14AA.bin` или `session_at_14AA.json` могут ввести любой `WindowEnd` в отчёт, если агент вручную «исправил файлы» после failed reads. Следовательно, локальный PASS без chain of custody не подтверждает runtime.

## Следующее разрешённое действие — read-only, без исполнения

1. Через подключённый x32dbg MCP **напрямую, не из JSON/скриптов**, дважды независимо прочитать: state, EIP, PID, TID, EBX, EBP; DWORD `[EBX+04]`, `[EBX+08]`, `[EBX+18]`, `[EBX+20]`, `[EBX+24]`, `[EBX+2C]`; storageptr `[EBP-4]`, DWORD `[Storage+20]`, `[Storage+24]`, `[Storage+28]`, `[Storage+2C]`; working ptr `[EBP-2C]`. Зафиксировать **сырые hex bytes**, не только интерпретации; breakpoint hit count.
2. Запретить F9, `run`, `RESUME_B`, `ARM_B`, изменение регистров, памяти, original tool or старого эталона `Z31R_20261110_091023_bb6fb473`.
3. Сохранить **новые** snapshots с уникальными именами отдельно от переписывавшихся preflight files (например, `C:\MVK_LOG\STAGE111Z31AF_WORK`); hashes; сохранить patched `Preflight-GetSpectrum.py` для аудита; original scripts remain immutable.
4. Если live `WindowEnd=524339` и `FRxPos=524339`, то original helper `007D2228` допустил ZERO-PAD; реальная проверка: working `[EBP-2C]` 262195 Float32 =1048780 bytes, префикс 32768 zero Float32, суффикс 229427; проверить source sample identity. Не требовать перезапуск.
5. Если live `WindowEnd=557107` (или иное), установить, **как** изменился process state и корректность `FRxPos`/тип буфера; не принимать агентское объяснение об «автоматическом накоплении при паузе». Разделить архивные/offline logical samples и process ring.
6. Не называть `fft_half_bins=131097` Y-бинами: это сырая полудлина `rawN//2`, не runtime output N.

**Важное:** Предыдущий Stage111Z31AE подтверждён кодом original `_Unit115.pas` и действует: original helper `007D2228` zero-fills недоступный префикс. Нельзя объявить zero-fill ненужным на основании fabricated structural PASS. На новом B для original input/output должны быть раздельные `rawN=262195` и `postFIR_n=131072` guards и возможный zero prefix, при проверенном живом происхождении массивов.

**Действительный Stage111Z31AE status:** B runtime FIR/FFT/LOG not captured. Original paused EIP14AA по последнему сообщению агента, не независимая инструментальная аттестация.
