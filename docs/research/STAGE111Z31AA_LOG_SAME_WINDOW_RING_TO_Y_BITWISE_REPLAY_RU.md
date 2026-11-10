# Stage111Z31AA — независимая перепроверка полного LOG-тракта по capture_pack.zip (10.11.2026)

**Доказано на одном пользовательском наборе данных:** исходный ring Float32 → FRange → DC → Hann RMS → IDR FFT → Power → очистка младших бинов → логарифмический Y → итоговые 3 Float32 **побитово совпали** с полными массивами, предоставленными как оригинальный захват. Это **не** самостоятельная аутентификация конкретного процесса Win32 и **не** универсальное доказательство 1:1 для других N/Fs/ADC/окна или пиксельного UI.

**Источник:** пользовательский приватный `capture_pack.zip`, SHA-256 `3cc9352a2a95534cddefbe2947573f165ca78eb99ebfc8b53b3bbeee34149c80`, 19 архивных элементов, ZIP CRC PASS. В публичный GitHub не загружаются исходные BIN/Float32/EXE/IDP. Аудит выполнен на локальных байтах Python/NumPy и повторением уже восстановленных формул из `mvk_compatible/core/fft_idr_candidate.py`, `spectrum_display_source.py` и `spectrum_metrics_idr_candidate.py`, без новой подгонки.

## Полный numerical replay

| Этап | Сравнение Float32/слов | Результат |
| --- | ---: | --- |
| `ring_head.bin` / `FRange` → `input_normalized_pre_dc.bin` | 262144/262144 | exact |
| mean-center Float32 → `input_after_dc.bin` | 262144/262144 | exact |
| plain code0 без FIR → `before_fft.bin` | 262144/262144 | exact |
| Hann/IDR radix-2 FFT → `power_before_mode.bin` | 131072/131072 | exact |
| low-bin suppression (нулевые бины 0/1) → `power_after_mode.bin` | 131072/131072 | exact |
| LOG display `Y` → `display_y.bin` | 131072/131072 | exact (0 ULP) |
| original summary HEX (mean, peak X, peak Y) | 3/3 | exact |

Параметры `N=262144`, `Fs=65536 Hz`, `Mode=0`, `EnvelopeCode=0`, `FRange=510.5650329589844 (0x43FF4853)`; исходный end `294912`, start `32768`, Storage oldest `32768`, capacity `2097152` Float32, mask `2097151`. Шесть Params-снимков согласованы по mode/filter/end. Full Y и PostPower по `524288` байт, исходные ring/preDC/postDC/preFFT по `1048576` байт.

**Сохранённые исходные HEX и корректные значения, в отличие от текста GigaCode:**

| Поле | Hex | Decoded Float32 |
| --- | --- | ---: |
| OutputMean | `40DC8F5E` | 6.892500877380371 |
| OutputPeakX (**в бинах**, не Гц) | `466D8095` | 15200.1455078125 |
| OutputPeakY (linear summary) | `3F475279` | 0.7786021828651428 |

Наибольший бин (k=15200), `df=0.25 Hz`, графический X = `3800 Hz` (взвешенный центр пика `3800.036376953125 Hz`), display Y = `-55.32063674926758 dB`. Не смешивать log-display dB и linear OutputPeakY.

**Хеши исходных массивов:**
- `before_fft.bin` = `9832b04ced202b793533823a2ec8d14c38971568c6e3cbd446eb2d7101d70d2d`;
- `power_before_mode.bin` = `16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34`;
- `power_after_mode.bin` = `81456d63be57536572fc2e0fe174f57454157c41c00890233554558e74f2ce09`;
- `display_y.bin` = `28c605d9864e9f52a79e09e874f39243ab08b4696e2bb2c8946dab7c71467d90`;
- `summary_triplet.bin` = `f82f11a8cbd114a1da7558f6aa8792d05e473cc8377be776279bf1f95e87dba7`.

Важное reuse-first: SHA последних `power_after_mode.bin` и `display_y.bin` **точно совпадают** с уже принятыми [Stage111Z30C Tag0 03.11.2026](STAGE111Z30C_TAG0_ORIGINAL_LOG_FULL_Y_131072_BITWISE_FOUR_MODES_RU.md). Это старый эталон на том же сигнале, **не независимая новая выборка**. **Новое доказательство** состоит в захвате и битовом сопоставлении ранних стадий ring→full FFT Power именно на том же окне, дополнительно к Y/summary.

## Важные ограничения/блокировки

1. `capture_log_a_snapshot.txt` в ZIP — **пустой файл 0 байт**. `Z31R_A_SAVED`, EIP `007D1900`, PID/TID после шести stops — это пока **только заявление GigaCode**; сам ZIP не содержит независимого живого thread/frame журнала. Не перезапускать A ради лога: лучше получить имеющийся x32dbg Console/Log read-only и сообщить, что evidence операторское.
2. `capture_config.json` имеет `adc_claim=4`, **не** `source_bin_sha256`; независимое тождество архивного BIN №83/АЦП4 ↔ этот ring **не доказано**. Старые сравнения BIN/screens не повторять.
3. Power/Y на этом конкретном окне exact **не** закрывает original Win32 FIR/IQ envelope20, другие N/Fs/ADC, реальный TQGrapher/GDI/Qt pixel diff, zoom/cursor/export и другие страницы.
4. Original paused по словам GigaCode на EIP `007D1900`. До нового согласованного плана не F9, не ARM_B и не менять GUI. **Новые значения FFT/Hann/Y менять не нужно.**
5. В `spectrum_calculation_acceptance.py` прежний общий статус `original_full_power_from_same_raw_window_bitwise_verified:False` относился к отсутствию такого примера до нынешнего захвата; now **one supplied LOG case exact**, но для общей матрицы и других режимов по-прежнему нет универсальной гарантии.

**Очередной приоритет:** сохранить операторский MCP/x32dbg журнал, затем добрать **оригинальный envelope FIR/IQ same-window и графическую TQGrapher/Qt parity**, а не перепроверять Tag0 FFT/Y на той же выборке. Строгий порядок проекта: спектр → GetSignal → расчётные данные → страницы.
