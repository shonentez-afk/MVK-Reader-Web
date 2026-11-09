# Stage111Z31W — проверка повторного GigaCode отчёта main/obmen (09.11.2026)

Источник: публичный [main/obmen](https://github.com/shonentez-afk/MVK-Reader-Web/blob/main/obmen), прочитан blob `98d8811e8d7d39f98aff83199f27f62bd17b4f8c`. Это **текстовый отчёт ИИ со скрытыми/незаписанными фактическими MCP tool-response**, а не физический dump из оригинального Win32 процесса. Предыдущий аудит: [Stage111Z31V](STAGE111Z31V_GIGACODE_OBMEN_MCP_AUDIT_RU.md). Основной приоритет: завершить оригинальный spectrum numerical parity, не менять принятую FFT/FRange/Tag0–3 математику.

## Что значительно улучшилось

Агент заявил Paused, `EIP=007D14AA`, `EBX=02A40E58`, `EBP=0019F270`, PID1856. В отчёте: `[EBX+04]=262144`, `[EBX+08]=0` (plain A), `[EBX+2C]=65536`, `Storage=[EBP-4]=02B28850`, `Storage+0C=0` (Float32), `Storage+10=2097152` samples, `Storage+14=2097151`, `Storage+18=65536`, `Storage+04=43FF4853` (510.56503296), `Storage+34=7E620010`, `[EBP-2C]=7E510010`. По заявленной карте памяти оба адреса читаемые: region work 7E510000 + 0x110000, region ring 7E620000 + 0x810000. `mask=capacity-1` проходит. **Это ещё не физический capture A/B**, поскольку ответ не содержит независимые бинарные snapshots, SHA/отчёт локального валидатора.

Корректные единицы: 2 097 152 **Float32 samples** = 8 388 608 **bytes (8 MiB)**, а не «2 МБ»; N262144 ×4=1 048 576 bytes, N/2=131072 float32=524288 bytes **каждый из** Power/Y.

## Критические недостоверности / stop gate

1. Агент расшифровал `EBX+18` как `00 80 04 00` / **0x00048000=294912**, назвал это SpectrumMode. Source-based prior [A-script](../../tools/research/stage111z31r_x32dbg_two_mode_capture/RESUME_A_FROM_14AA.template.txt), [B-script](../../tools/research/stage111z31r_x32dbg_two_mode_capture/RESUME_B_FROM_14AA.template.txt), [capture verifier](../../tools/research/stage111z31r_x32dbg_two_mode_capture/Verify-Capture.py) требуют mode 0..3 **по EBX+18**. Число 294912 за пределами этого enum, одновременно в отчёте `EBX+20=0x00048000` (end index). **Варианты:** скопирован неверный участок/переименовано смещение/смешаны данные разных чтений, либо наш prior layout неверен для этого конкретного вызова. Не угадывать без независимого raw 60-byte screenshot/dump. Пока `SpectrumMode` **UNVERIFIED**, `A/B RESUME` по старому mode=2 **запрещён**.
2. Повторный план «шесть стадий» по-прежнему обозначает `007D154B` как «перед FFT» и `007D17E7` как «до FFT-цикла». Правильная проверенная последовательность: `14AA=pre DC`, `14B8=post DC`, `153D=post FIR/pre FFT`, `154B=post FFT/pre mode Power`, `17E7=post mode Power и full display Y ([EBP-30])`, `1900=summary triplet ([EBX+30..38])`. `Power/Y` на `1900` лучше **не откладывать**: исходные указатели и буферы читать именно на `17E7`, при доказанном same TID/EBX/EBP/call/window.
3. Реплика «N — общий размер ADC-буфера» противоречит принятой при (N=262144) побитовой FFT-проверке (131072/131072) Power/Y. Нет причин заменять N на 4096 или объявлять его только ёмкостью кольца.
4. В текущем отчёте `[EBP-08]` назван как «Storage ptr, совпадает с EBP-4», хотя **EBP-08 и EBP-04 разные адреса**. Сохранить raw 48-byte стековый блок и указатель из точного `[EBP-4]` без догадок/перестановок.
5. Текущая четвёртая Float32 описана как `B0 03 BF BD` → **−0.0932687521**, что верно для *этих* байт; **в предыдущем obmen были другие байты** `BD B0 03 BF` → **−0.5144155622**, и наш аудит Z31V декодировал именно их **верно**. GigaCode ошибочно объявил аудит Z31V неправильным, не заметив изменения исходных четырёх байт. Это либо опечатка/транспозиция в первом отчёте, либо смена данных; несовместимые словесные отчёты не заменяют локальный бинарный снимок.
6. `main/obmen` не содержит самих raw MCP read_memory ответов или исполняемого локального Python-verifier с фиксированным SHA. Нельзя утверждать независимую верификацию из заголовка «Python struct». Корректный порядок — **read_memory→физические компактные .bin файлы→независимый локальный stdlib struct→JSON-контроль и SHA**, затем только изменение состояния отладчика.

## Точное следующее действие агента (только read-only, процесс Paused EIP14AA)

- Получить *одним* MCP read_memory ровно **60 байт по новому текущему EBX**, сохранить как `params_at_14AA.bin` (приватно), и **сразу** вывести `len`, `SHA256`, `raw_hex` **для диапазона +0x10..+0x2F** вместе с побайтовым offset-label `[0x18]`, `[0x20]`; не строить таблицу вручную.
- Через MCP прочитать `[EBP-4]` как 4 raw байта; в том же остановленном контексте считать **56 байт по полученному Storage** в `storage_at_14AA.bin`; считать ровно 48 байт с `EBP-0x30` в `locals_at_14AA.bin`, проверить указатели `[EBP-0x2C]`, `[EBP-0x30]` по словарю offsets.
- Запустить детерминированный **локальный Python struct.unpack_from('<I', buf, 0x18)** и распечатать полный `0x18` + значение, `params[0x20]`, их сопоставление с expected `mode in {0,1,2,3}` + ФАКТИЧЕСКИЙ вывод PASS/FAIL. Если `EBX+18==0x48000`, **STOP для исправления layout, без F9/постановки BP**.
- В отчёт включить **настоящие stdout/Python-код/минимальные SHA и показания MCP**, без полных исходных RAW/BIN в облако.
- Предварительный критерий дальнейшего захвата: valid mode, consistent live EIP/TID/EBX/EBP/source window/ring, physical snapshots, согласованный N/2 and Fs, read-only buffers. После этого отдельный операторский approve на run/step/single-shot: автоматизация не должна автоматически выполнять F9.

Status: **MCP connected and some pointer/enum claims plausible; trusted original GetSpectrum preflight NOT PASS**, real A/B same-run numeric parity OPEN, no changes to native core/UI/EXE.
