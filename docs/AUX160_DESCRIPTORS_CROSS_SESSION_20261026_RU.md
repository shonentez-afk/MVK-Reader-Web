# AUX160: межсеансовая проверка дескрипторов и опорных значений

Дата: 2026-10-26. Источники: сохранённый короткий RAW прибора A, полный PCAPNG подключения прибора A, короткий RAW и два PCAPNG прибора B. Все проверки офлайн.

## Проверенное наблюдение
В двух разных сеансах прибора A **младший байт дескриптора сохраняется**, а биты 0x400/0x800 в 43-секундном сеансе отсутствуют, но присутствуют в 12-секундном. Внутри каждой записи 12 или 43 последовательных AUX160 кадров каждый дескриптор сохраняется неизменным. Поле 0x212 каналов 1 и 5 сохраняется в обоих сеансах.

| ADC A | Коды в 12-с RAW (четыре записи) | Коды в PCAPNG (четыре записи) |
|---|---|---|
| 1 | 212 212 212 212 | 212 212 212 212 |
| 2 | 411 011 011 C15 | 011 011 011 011 |
| 3 | C14 011 011 C15 | 014 011 011 011 |
| 4 | 011 011 011 C11 | 011 011 011 011 |
| 5 | 212 212 212 212 | 212 212 212 212 |
| 6 | 411 814 C14 011 | 011 014 014 011 |
| 7 | C15 C15 011 C11 | 015 015 011 011 |
| 8 | C15 C15 411 011 | 015 015 011 011 |

Hex representation above omits leading 0x. On B all codes are zero across the 12s RAW, the 52s connect/disconnect PCAPNG and the 85s capture.

## Important correction about reference values
The apparent conflict for A/ADC4 entry 4 is real across sessions:
- 12-s RAW: field AUX160 +88 is **7.9638128**.
- 43-s PCAPNG: field AUX160 +88 is **4.1746297**.

Both are valid for their respective recordings. A prior report incorrectly presented them as if they were from the same session. They should not be reconciled by deleting either value.

Additional A examples, reference field of entry 1 (+40):
- ADC2: 6.948827 (RAW) vs 4.611214 (PCAPNG).
- ADC3: 9.976351 (RAW) vs 8.269575 (PCAPNG).
- ADC4: 4.666816 in both sessions.
- ADC7: 24.146297 (RAW) vs 33.240700 (PCAPNG).

Therefore the constant reference fields are **constant during a session but can be different between sessions**. They are not reliably identified as factory calibration constants or immutable thresholds.

## Interpretation status
- CONFIRMED: descriptor format uint32; low bits stable across two sessions, upper flags change between sessions; AUX160 reference float32 can differ between sessions.
- NOT CONFIRMED: low bits encode physical units, upper bits are alarms, reference is an engineering alarm setpoint.
- The change may relate to historical/reference measurements, initial measurement snapshots, settings, or other device-side state. More data needed to choose.

Architecture: preserve original descriptor and reference with session context and provenance. Do not merge by ADC alone across sessions or treat status as unconditional alarm.

Reproducible local audit script: tools/raw_offline_audit/audit_aux160_descriptors_long.py.
Main Reader Web v0.3.40 has not been changed or run; no device connections.
