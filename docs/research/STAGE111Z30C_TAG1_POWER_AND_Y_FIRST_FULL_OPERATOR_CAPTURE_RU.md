# Stage111Z30C — первый полный пользовательский Tag1 Power + Y (131072/131072)

Дата: 03.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`. Автономная Windows MVKView Compatible, без изменения Native R6.1 / Web / main.

## Исходные данные и статус

Пользователь передал четыре файла от x32dbg V4 текущего original GetSpectrum Tag1:

- `capture.log` — 204 байта, SHA256 `08ceec75340b8d441834c54ea3c586e46c2a9bfaedfb7f66546320ba5a67d1f1`.
- `power_before_mode.bin` — 524288 байт, 131072 Float32, SHA256 `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`.
- `power_after_mode.bin` — 524288 байт, 131072 Float32, SHA256 `81456d63be57536572fc2e0fe174f57454157c41c00890233554558e74f2ce09`.
- `display_y.bin` — 524288 байт, 131072 Float32, SHA256 `880807d52c55169a1107e3cdcf8a2454ae2133bdee1e38d66df7dca534f61516`.

**Ни один бинарный файл или сырые отсчёты не добавлены в GitHub.** Предыдущий x32dbg original Tag1 checkpoint на 007D154B прошёл `MVK_DIAG_TAG1_ALL_GATES_PASS` (N262144, Fs65536, code0, FRange Single `43FF4853`, точка 007D154B). Локальный операторский путь исходного capture.log содержит только запуск V4 и НЕ содержит завершения.

## Фактические результаты локальной проверки трёх пользовательских файлов

1. Все три .bin имеют корректный размер, finite Float32; нет NaN/Inf, массивы не пустые. Before и After powers неотрицательны; displayed Y неотрицателен для Tag1.
2. **POWER BEFORE SHA256 полностью совпал с оригинальным `after_power(1).bin` Stage111Z8**, который ранее проверен с исходным FFT входом на 131072/131072. Не требовать нового FFT или повторного Z8.
3. Source formula Tag1: `low=max(2, round(N/(2*Fs)))=2`; source-derived `power_before` с занулёнными бинами 0/1 **побитово совпадает с `power_after_mode.bin` в 131072/131072**. Изначальный before/after отличается **ТОЛЬКО** в индексах 0,1: 131070/131072 равных.
4. Новый original-operator-supplied full `display_y.bin` (в отличие от ранее отсутствовавшего Y): существующий Stage30B `source_derived_mode_display` по 131072 post-mode powers, FRange original `43FF4853`, mode1, N262144 вычисляет **131072/131072 побитово; max Float32 ULP 0**, выходной SHA256 **точно** `880807d52c55169a1107e3cdcf8a2454ae2133bdee1e38d66df7dca534f61516`. Отдельная локальная проверка direct formula `Float32(sqrt(P/2) * Single(FRange/(N/2)))` дала тот же результат.
5. Максимальный прямой бин Y=0.6187341809272766 при k=15200 (3800 Гц). `OutputPeakY` исходной summary — другая величина: source ±2-bin energy neighborhood. На загруженном after-power source-derived summary рассчитывает **40DC8F5E/466D8095/3F475279**, т.е. совпадает с ПРЕЖНИМИ оригинальными Tag0 словами Z10, но **этот пользовательский V4 лог НЕ содержит собственных Tag1 OutputMean/PeakX/PeakY**. Поэтому писать `Tag1 original summary 3/3 verified` нельзя, только derived observation и ранее имеющийся Tag0 reference.

## ДОПОЛНЕНИЕ 03.11.2026 — оригинальные Tag1 OutputMean / PeakX / PeakY получены после передачи массивов

После предыдущего отчёта оператор дополнительно прислал из x32dbg ровно три raw IEEE754 Float32 HEX, считанных по запросу с `[EBX+30]`, `[EBX+34]`, `[EBX+38]` на финальном этапе оригинального GetSpectrum Tag1:

| Поле | Операторский original Win32 HEX | Наш source-derived расчёт на ПРИЛОЖЕННОМ `power_after_mode.bin` | Float32 ULP | Побитово |
|---|---|---|---:|---|
| OutputMean | `40DC8F5E` | `40DC8F5E` | 0 | ДА |
| OutputPeakX (в FFT-бинах) | `466D8095` | `466D8095` | 0 | ДА |
| OutputPeakY | `3F475279` | `3F475279` | 0 | ДА |

Локальный независимый повторный пересчёт с настоящего присланного `power_after_mode.bin` при `N=262144`, `Fs=65536`, `FRange=0x43FF4853`: OutputMean=6.892500877380371; OutputPeakX=15200.1455078125 bins / 3800.036376953125 Hz; OutputPeakY=0.7786021828651428. **3/3 исходных отдельных операторских HEX совпали битово** без подгонки. Это НЕ просто старый Z10 текст: пользователь заново сообщил значения после получения файла Tag1.

Внимание: те же 3 HEX мы ранее зафиксировали для Tag0 в Stage Z10. Это **математически ожидаемо**, так как исходные мощности после зануления низких бинов в данном окне Tag0 и Tag1 совпадают; собственно графические Y различаются. Совпадение триплета между Tag0 и Tag1 не означает ошибку и не проверяет дополнительные режимы Tag2/3.

**Текущий уровень приёмки Tag1:** Power before/after 131072/131072 exact; GUI display Y 131072/131072 exact; summary 3/3 operator original words exact. Численный режим Tag1 на данных оператора — ПОДТВЕРЖДЁН. Однако `capture.log` до сих пор имеет только BEGIN и НЕ имеет `MVK_CAPTURE_DONE`, записи EIP/TID/EBX/EBP на втором/третьем checkpoint и значения тройки в самом логе. Поэтому принадлежность всех объектов **одному исходному thread/frame** не независимо подтверждена, а source-to-original provenance остаётся операторским утверждением. Нельзя трактовать это как сертификацию всего оригинала MVKView или всех условий.

Новый актуализированный локальный aggregate JSON (только численные выводы; без raw buffers): `MVK_STAGE111Z30C_TAG1_FINAL_NUMERIC_ACCEPTANCE_20261103.json`, SHA256 `c269810d164b1d67011057f118d6c696d653d48d7b71c38f5b88675cc120a6ad` (скачивание из этого чата; в GitHub не выкладывали).

**Следующий шаг:** Tag2 Линейный ВС и Tag3 Линейный ВП, проверка исходных integrated power + full Y + оригинальные три HEX со второго/третьего режима. Не делать прежние FFT/Z8, логарифм/Z10 или переснимки Z13/Z14 повторно.


## Важная проблема полноты журнала

Загруженный `capture.log` содержит ТОЛЬКО:

```text
Log will be redirected to C:\MVK_CAPTURE\RUN_RECOVER_20261103_114259_2f2e46b3\TAG1\capture.log.
MVK_CAPTURE_BEGIN EXPECTED_TAG=1 MODULE_BASE=00400000 CURRENT_EIP=007D154B RESUME_FROM_CURRENT_BREAKPOINT=1
```

Отсутствуют `MVK_STAGE=BEFORE/AFTER/SUMMARY`, `MVK_CAPTURE_DONE TAG=1`, данные EIP/thread/EBX/EBP/Frame provenance. Три уже существующих корректных файла означают, что сохранение больших массивов произошло, но без лога **не подтверждён окончательный проход до 007D1900** и неизменность потока/кадра; при этом full Y 131072 exact и before SHA совпадают с историческими эталонами, что является сильным согласованием source-формул. Не заявлять `end-to-end original three stop authenticated` и не маркировать всю S04=Closed.

## Что делать дальше — только недостающий минимум

- Если оригинальный x32dbg ещё остановлен в **007D1900**, вручную снять три HEX `dword:[ebx+30]`, `[ebx+34]`, `[ebx+38]` и текущее EIP/TID. Лучше сохранить 12 bytes `savedata "C:\MVK_CAPTURE\TAG1_summary_triplet.bin", ebx+30, C` (адрес/счётчик в x32dbg). Не запускать заново прежнюю FFT проверку.
- Если `007D1900` уже пройден — не объявлять провал, оставить Tag1 **source-numeric power/Y verified on operator-supplied arrays**, final original triplet and same-call thread metadata pending.
- Для Tag2/3 применять фиксированный автоматизированный захват, который сохраняет 12-байтный triplet физически, а не только в `RedirectLog`; отдельно сравнить исходную 007D2164 power integration и Float32 Y. Ранее проверенные Z2 scale words не подменяют raw Tag2/3.
- GitHub сохраняет только derived report, тесты synthetic и будущие исходники automation; BIN/IDP/EXE/приборные измерения private. No change to original recorder.

## Формальный статус

**Stage30C Tag1 numeric Power postmode 131072/131072 + displayed Y 131072/131072: PASS on submitted user-supplied original-runtime-claimed buffers.** Real same-invocation/source-domain/thread/Tag1 Output* metadata still OPERATOR-UNAUTHENTICATED / OPEN. Stage Z8 131072/131072 historical FFT and Tag0 Z10 3/3 are preserved. Tag2/3 full raw original parity OPEN.
