# Stage111Z31AH — EnvelopeCode20 work_raw.bin: exact ADC1 BIN + previous LOG input (2026-11-10)

## Источники и границы доказательства

Проверен присланный пользователем `STAGE111Z31AE_PACKAGE.zip`, SHA256 `d1c911e0b7c21735e1af5147b73a1d0c9bde3e99288d9d94b609826e7bbf71e0`. В ZIP **фактически только три файла**: `work_raw.bin` (1048780 bytes), `Preflight-GetSpectrum-Z31AE-patched.py` (11308 bytes), `STAGE111Z31AE_REPORT.txt` (4171 bytes). Вопреки упоминанию в TXT, **там нет ни `RESUME_B`, ни `Verify-Capture.py`**. Original live x32dbg process отсюда напрямую недоступен, provenance `work_raw.bin` как оригинального дампа основывается на сообщении GigaCode, хотя независимые байтовые проверки ниже необычайно сильны.

Исходный измерительный `MVK00000043-ADC1-2026-10-29--13-32-12.bin` доступен локально и проверен SHA256: `b598d466f9f70f49e4a5f6a0f2a20d4870af43f9864f5e4c9f7cfd51c9d2fad1` — 1965824 Float32. Предыдущий оригинальный `capture_pack.zip` SHA256 `3cc9352a2a95534cddefbe2947573f165ca78eb99ebfc8b53b3bbeee34149c80`, внутри `input_normalized_pre_dc.bin` SHA256 `e6ef549643cd9b5cf4470200d520ef95eb5b93263fb6b2fb942e47c3d4ac12f1` 262144 Float32.

## Два независимых побитовых подтверждения

1. Work `work_raw.bin` SHA256 **`86856251ab33201aec2ccbf43f0e33ea0bf658cd3f1112183071d13b665949c5`**, ровно 262195 Float32. **Уникальный** точный full match среди всех возможных смещений физического BIN, после `np.float32(BIN / np.float32(FRange))` при `FRange` Float32 bits `0x43FF4853`, обнаружен в **`BIN[1703230:1965425]`**, 262195/262195 bit-exact. RAW physical source window SHA256 `0a3dfc14839fb5528f62949b5dc036ba36322f826586a905372d4c815d603002`. Среди совпавших первых точек full match только **один**.
2. **`work_raw[51:]`** (262144 Float32) равен **всем 262144 Float32** `capture_pack.zip/input_normalized_pre_dc.bin`, 0 mismatches, SHA обоих `e6ef549643cd9b5cf4470200d520ef95eb5b93263fb6b2fb942e47c3d4ac12f1`.

Тот же физический конец `1965425` уже использован для обычного LOG в Stage111Z31AA/AB: `BIN[1703281:1965425]`. FIR input добавляет **ровно 51 исходный отсчёт слева**, сохраняет **тот же физический последний отсчёт справа**; значит окно B идентично A по логической точке измерения, хотя содержит специальный FIR lead-in. Два независимых evidence источника совпадают.

**ВНИМАНИЕ к ошибке GigaCode:** он сравнил `work_raw.bin` с **`BIN[294912:557107]`** и получил MISMATCH, назвав его «ожидаемым, поскольку work уже после DC». Это **неверное объяснение**: `294912` и `557107` — **логические индексы Storage ring, НЕ физические индексы файла ADC1 BIN**. Корректный физический offset — 1703230, где сравнение именно до DC даёт полный битовый PASS. Для ясности: среднее `work_raw.bin = -0.06947107469464572`, все значения конечные и **нулевого префикса нет**. Декомпилированный original `GetSpectrum`: `007D14A5` копирует/нормализует raw, `007D14B3` DC-removal выполняется **ПОСЛЕ** текущей `EIP=007D14AA`. Следовательно дамп — **preDC**, а не postDC.

## Следствия для расчётов и B-захвата

- Исходные little-endian bytes `[EBX+20]=33 80 08 00` правильнее `557107`, `[EBX+04]=262195`, начало ring `294912`, FValidPos `294912`, deficit **0**. Старый Stage111Z31AE ZERO-PAD — general source fallback, но сейчас **не использован**.
- Stage5 `FIR_TAPS=51`, `FIR_DECIM=2`; ожидаемый after FIR `FFT N=(262195-51)/2=131072`, Fs out32768, df0.25Hz, 65536 Y bins. Только **гипотеза по source**, а не runtime measurement на EIP153D.
- **Не запускать старый `RESUME_B_FROM_14AA` под N262144**, не считать `fft_half_bins=131097` из локально правленного Preflight реальными FFT-бинами и не объявлять FIR/FFT/LOG Y уже совпавшими. Доработать отдельный guarded B с **inputRawN262195, postFIR N131072 и halfN65536**, оригинальной цепочкой stage stops и численным сравнением всех массивов.
- Локально патченный Preflight снял pow2 guard и переименовал rawN в FFT N, **семантически неверно**; он проверяет структуру предоставленных snapshots, но ZIP их НЕ содержит и не даёт повторить structural preflight. Никаких F9/ARM/RESUME без подтверждённой безопасной новой версии и отдельного согласования.
- Реально полученный полный 262195 точек work buffer — ценная доказанная база для offline расчётов **на этих же физических отсчётах**, при использовании оригинальных PRIVATELY-HELD FIR coefficients, не коммитить коэффициенты/BIN/IDP.

## QA

Независимый `verify_stage111z31ae_fir_input.py` проверяет уникальный full Float32 match BIN после /FRange, полное совпадение raw[51:] с прежним capture_pack preDC, SHA и совпадение физического конца. **8/8 синтетических unit tests PASS**, включая порчу рабочего буфера, LOG, неверный FRange, неверную длину, подложный конец, NaN и повреждённый ZIP. На реальных файлах verdict `FULL_PHYSICAL_ADC1_AND_PREVIOUS_LOG_BITWISE_PASS`; CLI возвращает ненулевой код при несовпадении.

## Передача GigaCode (не пишет GitHub)

Оригинал оставлен GigaCode на paused `EIP=007D14AA`, Envelope20/LOG0, без F9. Сохранить эту точку, проверить реальные pointers и stage call order; подготовить в копии отдельный **guarded** B на rawN262195→FFT N131072, который снимет preDC (уже есть), postDC, postFIR preFFT, power до/после mode, Y и summary; не править источник под фиктивный Preflight PASS, не запускать старый B, не перезапускать original. Следующий runtime event — staged capture на `007D153D` **после согласования operator permission**, чтобы фактически проверить FFT N/Fs и сохранить оригинальные FIR arrays.
