# Stage111Z31Y — независимая проверка шести бинарных файлов GigaCode (10.11.2026)

## Источник и пределы доказательства

Пользователь передал пять физических *.bin и один `session_at_14AA.json`, полученные от GigaCode в текущем исследовании оригинальной MVKView. Все **шесть пользовательских файлов** прочитаны независимым офлайновым Python `struct.unpack_from('<I' / '<f')` и `sha256`; длины каждого файла проверены непосредственно. Никакого доступа к живому x32dbg, MCP transcript, проверки opcode/region или перемещения отладчика во время этого аудита не было. Бинарные файлы и оригинальные EXE/BIN/IDP **не коммитить**.

**Итог: `STRUCTURAL_PREFLIGHT_PASS_NOT_RUNTIME_ATTESTATION` для переданного набора. Но `BLOCK_CAPTURE_MODE` для существующего целевого Stage111Z31R A/B, поскольку actual SpectrumMode=0 (LOG), а capture config по умолчанию `SpectrumType=2` (VELOCITY).**

## Побайтово подтверждено

- `params_at_14AA.bin` 60 байт, `params_recheck_10_2f.bin` 32 байта, `storage_ptr_at_14AA.bin` 4 байта, `storage_at_14AA.bin` 56 байт, `locals_at_14AA.bin` 48 байт. JSON 109 байт.
- Независимое `params[0x10:0x30]` = `params_recheck[0:0x20]`, **32/32 побайтно**.
- `[EBX+0x18]` raw `00 00 00 00` => mode **0**; `[EBX+0x20]` raw `00 80 04 00` => end **294912**. Предыдущее значение 294912 неверно приписывали mode; сами файлы подтверждают правильный offset, а не причину прежней ошибки агента.
- `[EBX+04]` N **262144**, N/2 **131072** Float32, input **1048576** bytes; каждый будущий массив Power/Y **524288** bytes. `[EBX+08]` EnvelopeCode **0**, `[EBX+2C]` output Fs **65536 Hz**.
- Storage pointer = `0x02B28850` в independent `[EBP-4]` и `locals+0x2C`. Work pointer `0x7E510010`, ring pointer `0x7E620010`. Наличие страниц и прав доступа здесь **НЕ проверялось**.
- `Storage+0x0C` Float32 type **0**; `Storage+0x10` ring capacity **2097152 samples** = **8388608 bytes**; `Storage+0x14` mask **2097151**; `Storage+0x18` raw Fs **65536 Hz**; FRange `Storage+0x04` bits `0x43FF4853` -> **510.5650329589844**.
- `[EBX+0x20]` end **294912** = Storage write position; oldest **32768**; window start=end-N=**32768**, точно oldest. High index words нулевые. Достаточность сохранённой истории **структурно** пройдена.
- `session_at_14AA.json` сообщает `paused`, EIP `0x007D14AA`, EBX `0x02A40E58`, EBP `0x0019F270`, PID 1856, TID 10768, но этот JSON — **заявленная метаинформация**, не независимая аттестация отладчика.

## Хеши SHA-256 вложений, без загрузки их содержимого в GitHub

| Исходное имя у пользователя | SHA-256 |
|---|---|
| `params_at_14AA(1).bin` | `25e7695fa70392f8f8cb454fa85f4c30669a7e9d49451f346d8354f621f464da` |
| `params_recheck_10_2f(1).bin` | `13acf3a8ba9fa284052445fe54372e03acc2357795a53f64c0ffe813f401dfe2` |
| `storage_ptr_at_14AA(1).bin` | `095c89d6ad01f3c3a5b7a0583b02718176f6a1fbb0b6a25c6d8ff7f0c87b221f` |
| `storage_at_14AA(1).bin` | `a5bbc3eeb71872f31f66138b12bbe73fe0118d31dd06c7dd8cb01cffdbca53b4` |
| `locals_at_14AA(1).bin` | `4d95358b023feeb9da511266ddc731e934e58f6ff2d688ac55e92c9c8b0edc7a` |
| `session_at_14AA(1).json` | `01dcd0d6d2c2a520f87ae385d304bf666e121b419a759fd2be9ef95775a084c1` |

## Почему структурный PASS не достаточен

`Preflight-GetSpectrum.py` из Stage111Z31X проверяет саму допустимость SpectrumMode=0..3. В Stage111Z31X/Y был добавлен **отдельный target gate** `--expected-mode` и `--expected-envelope`; тестируется в GitHub Actions [#42736482828](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42736482828) — 2 jobs SUCCESS (synthetic, не original runtime). Для velocity A проверка должна быть запущена **ровно над неизменёнными реальными файлами**:

```powershell
py -3 Preflight-GetSpectrum.py "C:\\MVK_CAPTURE\\GIGACODE_PREFLIGHT" --expected-mode 2 --expected-envelope 0
```

На проверенных вложениях ожидаемый итог **`BLOCK_CAPTURE_MODE`**, потому что фактический режим 0. Нельзя объявлять velocity A готовым и нельзя править raw байты mode0 на mode2. Если важен текущий LOG снимок, оформлять его **отдельным** согласованным экспериментом mode0; для запланированного velocity A/B требуется новый реальный stop EIP14AA с mode2 и независимым preflight. До утверждения действия — **не нажимать F9, не ставить BP, не запускать A/B скрипты, не перезапускать оригинальный процесс**.

Текущий отчёт не содержит full original `before_fft` / `power_before_mode` / `power_after_mode` / `display_y` и не доказывает same-window оригинального BIN, FIR/IQ либо 1:1 спектры. Принятые FFT/FRange/Tag0–3, Native R6.1, Qt и Windows EXE не изменять только из-за этого preflight.

**Порядок разработки:** закрыть полный спектр → временной сигнал → расчётные данные → остальные страницы.
