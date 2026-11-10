# Stage111Z31AM — Original MVKView EnvelopeCode20 / LOG0: FULL numerical bitwise acceptance (10.11.2026)

## Вердикт

**ПОДТВЕРЖДЁН ПОЛНЫЙ ЧИСЛЕННЫЙ ПОБИТОВЫЙ ПАРИТЕТ ОДНОГО ОКНА ОРИГИНАЛА** — от исходного физического ADC1 Float32 и нормализации FRange через DC, 51-tap FIR/IQ envelope, decim2, Hann-RMS, оригинальный IDR radix2 FFT Power, low-bin mask, LOG Y и итоговые метрики. Это независимое **offline** воспроизведение оригинальных массивов, переданных оператором; не свидетельство 1:1 всех режимов, экрана/UI или работы аппаратного прибора.

**Источник фактического оригинального B:**
- GitHub Exchange commit [cabd263fa32a0304d5fff14264e72e112b1b7508](https://github.com/shonentez-afk/MVK-GigaCode-Exchange/commit/cabd263fa32a0304d5fff14264e72e112b1b7508), текстовый `RESULTS/STAGE111Z31AL_B_CAPTURE_REPORT.md`, исходная 6-stop последовательность сообщена GigaCode;
- переданный пользователем **ПРИВАТНО** `STAGE111Z31AL_B_CAPTURE_PACKAGE.zip`, 3771873 bytes, SHA256 `78e7c095d8b1a9d21a26bb9b21b6edaf826a8a9ba34e67af625e6717ff775292`. В нём 18 entries: **16 Float32/params raw binary файлов** суммарно 4457492 bytes + `capture_b.log` + копия текстового отчёта. ZIP CRC, размеры и все 16 SHA256 сверены с GitHub report. Приватные массивы/ZIP в GitHub **не коммитились**;
- подтверждённый Stage111Z31AH физический исходный `MVK00000043-ADC1-2026-10-29--13-32-12.bin` SHA `b598d466f9f70f49e4a5f6a0f2a20d4870af43f9864f5e4c9f7cfd51c9d2fad1` и старый оригинальный `capture_pack.zip`;
- пользовательский локальный PRIVATE оригинал `mvkview.idp` SHA `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. Верифицированная `EnvelopeProfile.from_original_local_idp` читает FIR bank #5, не публикует коэффициенты/IDP.

## Стопы и фактические размеры

Один GigaCode one-shot original x32dbg capture после явного согласия оператора, reported `EIP 007D14AA → 007D14B8 → 007D153D → 007D154B → 007D17E7 → 007D1900`. Начальный `rawN=262195`, `WindowEnd=557107` (little endian `33 80 08 00` = 0x00088033), oldest294912, Code20, Mode0, raw Fs65536, FRange bits0x43FF4853. Post-FIR `N=131072`, output Fs32768, halfN65536, frequency step 0.25Hz. Локально запущен exact pinned `Verify-Capture-Code20-BOnly.py` с exact 434-byte `capture_config.json`, выход `B_CAPTURE_FILES_VALID_NOT_NUMERIC_PARITY` / exit 0. **Ни один runtime debugger process не запускался ChatGPT; это проверка приватных файлов.**

| Стадия | Кол-во Float32 | Предсказанный и исходный SHA256 | Побитово | Ошибка |
|---|---:|---|---:|---:|
| preDC (physical BIN/FRange, same-end) | 262195 | `86856251ab33201aec2ccbf43f0e33ea0bf658cd3f1112183071d13b665949c5` | 262195/262195 | 0 ULP |
| after DC (Float32-stored cumulative mean) | 262195 | `005385a7491739f2408266bb041385d3f7597939f503962bfd11c6f40ef87ce8` | 262195/262195 | 0 ULP |
| after stage5 FIR/IQ (51 taps / 2 decim, sqrt(I²+Q²)) = `before_fft.bin` | 131072 | `4bb9779db50c8564d413ff526c75aeaf1594b21a02da99b9d00b5e0f6055ccfb` | 131072/131072 | 0 ULP |
| Hann-RMS, IDR Float32 positive-angle radix2 FFT, Power | 65536 | `34652484a5897679b3bc926aabdeaba04493a46f5a7d1e50ece7ee8d8ffaba02` | 65536/65536 | 0 ULP |
| Power после low-bin mask (bins 0,1 → 0) | 65536 | `0c20b4603d6af1d8ead7a7ee274e4a5919e62cf3279465f46836acd7bcf64b0a` | 65536/65536 | 0 ULP |
| LOG Y (original f32 offset `2*log10(halfN)`, tenfold difference; 0 → -180dB) | 65536 | `d1ba2c2e222cc1cdd30ef1b4cfad367016c66af584388f591f99e40f05c9caf8` | 65536/65536 | 0 ULP |
| summary `OutputMean, OutputPeakX(bin), OutputPeakY(linear)` | 3 | `1589fedb367b0d4209d295c6d2af4a646d87eaa0bf62a9e59901aa57980857b0` | 3/3 | 0 ULP |

**DC:** Original running sum stored each step in Float32; removed mean `-0.069470465...` (`0xBD8E4688`), не следует подменять его точным Float64 mean `-0.06947107469`. Offlined `mean_center_float32` повторил afterDC array bit-for-bit.

**FIR:** profile из верифицированного private IDP, stage5 coefficients (51 pairs of I/Q), decimation=2; на каждом tap применяется original FSTP float32 для обоих аккумуляторов, после sqrt FSTP Float32. Параллельный векторизованный offline Python replay совпал **131072/131072** (SHA одинаков).

**FFT:** `idr_power_spectrum`-equivalent: periodic Hann RMS (262144-table stride2), Float32 positive-angle FFT twiddle with Single stores + Float32 butterfly output, Power Single storage. Bitwise matches power 65536/65536 — это явное runtime подтверждение ранее source-derived IDR-кандидата также для FFT N131072.

**LOG:** `source_derived_mode_display`-equivalent mode0 exactly reproduces all 65536 Float32. Фактический raw mode0 power copy с suppression именно индексов 0/1, остальные 65534 значения unchanged.

**Summary:** `original_spectrum_summary`-equivalent output float32 3/3 exactly: `OutputMean=0.42281264066696167`, `OutputPeakX=79.9397964477539` **bin**, `OutputPeakY=0.06395269930362701` (линейная амплитуда). Discrete graph max **bin 80**, `80*(32768/131072)=20.00 Hz`, `Y[80]=-77.12222290039062 dB`. PeakX после взвешенного уточнения = `79.9397964*0.25=19.9849491 Hz`. **Не путать** PeakX в бинах с 79.94 Гц и linear PeakY с Y dB.

## Ограничения и дефекты отчётности GigaCode

1. **GigaCode дважды неверно подписал little-endian в pre-run отчёте Z31AL:** `[EBX+04] = 33 00 04 00` означает `0x00040033 = 262195`, а не написанное `0x33000400`; `[EBX+08] = 14 00 00 00` означает `0x00000014 = 20`, а не `0x14000000`. Корректное `[EBX+20] = 33 80 08 00 → 0x00088033 = 557107` подтверждается raw Params/Storage.
2. В ZIP `capture_b.log` обрывается после установки breakpoint `007D17E7` (фактически snapshot-redirect). Поэтому текстовый лог один **не даёт полного независимого доказательства посещения 17E7 и 1900**, хотя реальные `params_after_y.bin`, `params_final.bin`, `display_y.bin` и `summary_triplet.bin` присутствуют и согласованы. Не повторять live process только для заполнения лога.
3. Происхождение файлов от единственного оригинального Win32 процесса фиксируется GigaCode, но не аутентифицировано инструментально ChatGPT. Бинарные файлы согласованы с прежним physical ADC1 и исходным local IDP; это сильная численная provenance crosscheck, а не гарантия всех гипотез.
4. **Охват:** только один исходный физический ADC1 сигнал, EnvelopeCode20/LOG0, Fs65536→32768, N131072. Остальные фильтры, mode1/2/3, UI, диаграмма/координатная шкала, новые окна/файлы, источник Collector Server остаются отдельными задачами. **Не объявлять завершённым весь MVKView.**
5. GigaCode закончил **один** ранее разрешённый B-run; разрешение **израсходовано**. По сообщению оригинал снова Paused `007D1900`; новая команда на `F9`, `run`, RESUME или другой спектр требует **отдельного согласия** пользователя.

## Дальнейшая реализация

Принять Stage111Z31AM как `FULL_NUMERICAL_CODE20_LOG0_SINGLE_WINDOW_BITWISE_PASS`, закрепить regression/harness на локально предоставляемых PRIVATE ZIP + IDP, подключить проверенные коэффициенты **только из локального оригинального IDP** (не публиковать), а затем расширить паритет на следующие EnvelopeCode и SpectrumMode **по одному реальному оригинальному golden-снимку**, без повторной калибровки уже точных FIR/FFT/LOG механизмов. Визуальные оси и UI — отдельный следующий слой. Сосредоточиться на численной совместимости перед косметикой.
