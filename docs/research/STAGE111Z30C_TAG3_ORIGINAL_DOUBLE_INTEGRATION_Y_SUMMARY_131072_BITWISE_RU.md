# Stage111Z30C — оригинальный Tag3 «Линейный ВП»: 2 интегрирования 131072/131072 + Y 131072/131072 + Summary 3/3

**Дата:** 03.11.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. Режим анализа — локальные копии операторских файлов, не подключаем прибор/оригинальную прошивку/Native R6.1, не изменяем `main`/Web.

## 1. Оригинальные входные свидетельства

Оператор передал девять файлов из V6 x32dbg (входная остановка оригинального `GetSpectrum 007D154B`, затем after mode `007D17E7`, затем summary `007D1900`): три полных массива по **524288 байт / 131072 Float32**, три Params snapshots по **60 байт**, `frange.bin` **4 байта**, `summary_triplet.bin` **12 байт**, `capture.log` **96 байт**.

Частные данные/оригинальные BIN/EXE/IDP НЕ загружены в GitHub/CI. Репозиторий хранит только метаданные и агрегаты, подтверждённые локально на прикреплённых файлах.

Проверенные независимые SHA256:
```text
power_before_mode 16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34
power_after_mode  9dfb017893d8a5f85f27b59917002fde0329885d420713fde768fa567f3379c6
display_y         3475f53063d34f098356bdd31aa68b75521ed2d828e9946530072169c4c6e92f
frange            84eb688f8f548bf542dbdefefbadfc38163f1648ee56cfaa84afe882baea7d29
params_before     c47b317f710816c931ee70605c55c89131f7691f0a2109cc4f213974b4b4eb70
params_after      c47b317f710816c931ee70605c55c89131f7691f0a2109cc4f213974b4b4eb70
params_summary    1c7f3a382fa5ddd2f67083bb2e1ecb4297d6878b1bbf6fb4403c724bc3ef8eb8
summary_triplet   e5353f25b35be7f6a1eebd5d4100fa5b148da1ec174095454e9a5871306780a5
capture.log       6ea326f3baff85d83a28eb7755332c62df73dd1e4307ef729603e1af3084da80
```

## 2. Метаданные на трёх остановках

- `params_before` и `params_after` **байтово равны**, в `params_summary` префикс `0x00..0x2F` неизменен, изменены только 3 исходных Output* поля.
- В каждом snapshot: `[EBX+4] N=262144`, `[EBX+28] half=131072`, `[EBX+2C] Fs=65536 Hz`, `[EBX+18] mode=3`, `[EBX+8] envelopeCode=0`.
- `FRange Single bits=0x43FF4853` = `510.5650329589844`.
- `params_summary[0x30:0x3C]` = physical `summary_triplet.bin` **byte-for-byte**.
- `capture.log` содержит **только** строку перенаправления журнала. Маркера DONE и EIP/TID/EBX/EBP каждой остановки в файле НЕТ. Следовательно, **same-frame/thread/process provenance не подтверждено независимо**, несмотря на согласованные snapshots.

## 3. Сверка точного существующего кода без подгонки

Проверка использовала текущие source-derived кандидаты:
- `core/envelope_spectrum_idr_candidate.py::_delphi_integration_power(power,N,Fs,2)`: диапазон `low=max(2,round(N/(2Fs)))=2`, два последовательных прохода `Single(P[k]*(159.154943091895/(k*Fs/N))²)` с повторным Float32-store между проходами.
- `core/spectrum_display_source.py::source_derived_mode_display(after,N,mode=3,FRange)`: `Single(sqrt(after[k]/2)*Single(FRange/(N/2)))`.
- `core/spectrum_metrics_idr_candidate.py::original_spectrum_summary(after)`: исходная последовательная Double сумма и Single расчёт локальной энергии ±2 бина.

**Результаты:**
- Двойное интегрирование **131072/131072 Float32 bitwise exact**, max ULP **0**; SHA результата = `9dfb017893d8a5f85f27b59917002fde0329885d420713fde768fa567f3379c6`.
- Полный массив графического Y **131072/131072 Float32 bitwise exact**, max ULP **0**; SHA результата = `3475f53063d34f098356bdd31aa68b75521ed2d828e9946530072169c4c6e92f`.
- Исторический оригинальный Z8 `after_power(1).bin` имеет тот же SHA, что пользовательский Tag3 `power_before_mode.bin`: `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`. FFT ЗАНОВО не нужен.
- `summary_triplet.bin` исходные 3 DWORD: **`42B1B034 / 00000000 / 00000000`**, кандидат вычислил все **3/3 побитово**; OutputMean `88.84414672851562`, OutputPeakX `0`, OutputPeakY `0`.

**Особенность оригинальной реализации:** при двух интегрированиях энергетический максимум становится `k=2` (`0.5 Hz` при `df=0.25 Hz`), и оригинальная процедура `007D1861..18CC` обрабатывает локальный пик только при `candidate>2`. Поэтому оба итоговых поля PeakX/PeakY равны нулю при ненулевом пике *в полном Y* (max Y `66.94998931884766` на k2). Считать это случайным отсутствием сигнала НЕВЕРНО. Поведение воспроизведено source-derived модулем без специальной подгонки.

## 4. Критичная оговорка: Tag2/Tag3 metadata source-window отличается

**Самый важный найденный QA нюанс:** байты `power_before_mode` Tag2 и Tag3 идентичны (тот же SHA Z8), метаданные N/Fs/FRange/EnvelopeCode совпадают, **но** `[EBX+20]` отличается:

| Поле | Tag2 ВС | Tag3 ВП |
|---|---|---|
| `[EBX+18]` | `00000002` | `00000003` |
| `[EBX+20]` | `00290000` | `003C8000` |
| `[EBX+24]` | `00000000` | `00000000` |
| pre-mode Power SHA | `16ecc8...` | `16ecc8...` |

Существующий локальный `Verify-Stage30C.py` **PASS отдельно** для Tag2 и Tag3, но **REJECT совместно**: окно `[EBX+20]` разное. Это правильный сигнал о metadata mismatch, **не опровержение каждого режима численно**. Нельзя утверждать проверку нескольких режимов на заведомо идентичном *временном* окне только из совпадающих FFT power байтов; нужно отдельно проследить происхождение window offset/кэша/изменения выборки. Это отдельный data-provenance вопрос, не переписывать FRange/интегрирование ради него.

## 5. Приёмка и продолжение

**S06 Tag3 НУМЕРИЧЕСКИ PASS для данного операторского оригинального случая:** два прохода Power, full Y и Output 3/3 точны по всем битам. `core` и `main` не меняли; полноценное end-to-end/UI/спектры других ADC/N/FRange и same-run frame provenance НЕ подтверждены.

Следующий числовой пропуск из 4 режимов — original **Tag0 full Y** на той же операторской архивной записи (ранее Tag0 Power/summary/Copy уже проверены, повторять их не требуется). После этого — анализ TQGrapher/Qt full Y→plot, pixel acceptance и явная повторная проверка влияния source window без лишней повторной трассировки FFT.

Локальный агрегированный файл `MVK_STAGE111Z30C_TAG3_NUMERIC_ACCEPTANCE_20261103.json`, SHA256 `0093bd9b7151e309a0678a237b0e9e2cf1cf2e6052f23c68f9ba2a0c44ce8a1c`, содержит только hashes/метаданные/агрегаты, не сами оригинальные samples.
