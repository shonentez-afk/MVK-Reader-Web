> **S01 LOCAL WINDOW EVIDENCE ADDED IN Stage111Z29A (02.11.2026):** GetSignal and GetSpectrum now carry same-archive pre-DC Float32 SHA256 + ADC/source RAW identity + sample indices/Fs; original latest/sequential ring source mapping tested, no zero padding for archival BIN, live absolute preview indices marked unverified. This proves correct LOCAL INPUT selection only, not that original Delphi used same ring/window. Stage29B real original GetSignal returned Float32 array+same-run pairing remains OPEN. [Stage29A QA](STAGE111Z29A_GETSIGNAL_WINDOW_SOURCE_AND_FFT_PROVENANCE_RU.md), tested 524cf7a0c1d4f242c339c7556fb41e957a02031b [CI #41408120811](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41408120811) ALL3 SUCCESS Linux1067 Windows1068 Qt49, [EXE artifact 13123989621](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/41408120811/artifacts/13123989621); Stage30 modes 1/2/3 real goldens and original UI parity NOT closed.

# Stage111Z30 — статус полного восстановления спектров оригинальной MVKView

Ревизия 02.11.2026. Ветка research/stage111-mvkview-desktop-20261029.
ИТОГ: ПОЛНОГО 1:1 ВОССТАНОВЛЕНИЯ ВСЕХ СПЕКТРОВ НЕТ. Есть сильное доказательство одного математического случая; нет общей аппаратной/визуальной/всем режимам приёмки.

## Три разных тракта — не смешивать
1. Приборный DSP AUX4700: реальные 43 третьоктавы и 24 RMS/ПИК/ПИК-ПИК, статусы каналов; это НЕ локальный FFT GetSpectrum.
2. Архивный GetSpectrum: original-inspired Float32 periodic Hann/window/DC, IDR radix-2 FFT, интегрирование, четыре режима, summary, шкалы и графический TQGrapher/cursor/Copy/Save.
3. Live Native: предварительный bounded 8192-sample/ADC Float32 ring после уже выполненной калибровки R6.1. Это НЕ оригинальный длинный live спектр.

## Что подтверждено и что остаётся
- Stage111Z8: одна ненулевая операторская original-runtime claimed пара before_fft/after_power, N262144, полные 131072/131072 Float32 power bins совпали ПОБИТОВО с source-derived fft_idr_candidate.py. Независимая аутентификация единого процесса/thread и других окон не доказана.
- Stage111Z10: один original Tag0, N262144 Fs65536 FRange510.565...; OutputMean, OutputPeakX, OutputPeakY совпали 3/3 исходных Float32 HEX. OutputPeakX в BIN; вычисленная частота после XScale и GUI selected record требуют отдельного source context.
- Offline archive spectrum_for_zip поддерживает FFT N до 262144, четыре source-derived mode0 log, mode1 ВУ, mode2 ВС, mode3 ВП. Это КОД-КАНДИДАТ: независимого original numeric golden для остальных режимов 1/2/3, их FRange/интегрирования и log UI нет.
- Подготовка GetSignal/ring/window order/DC, оригинальная temporal origin, FIR/IDP огибающая/source envelope являются PARTIAL и требуют real same-run input/output.
- Qt original source-derived TQGrapher/scroll/ХOR cursor/copy/save имеет отдельные тесты; пиксельный parity и корректный selected record Clipboard/Save в равных условиях НЕ доказаны. Два операторских соседних Copy текста Stage111Z12 не сопоставимы без текущего ESI и actual XScale.
- Live Stage26B только 8192 samples/channel: Fs65536 => df=8 Гц и 0.125 с истории. Для N65536/N262144 нужны соответственно 1/4 с истории, CPU/RAM/IO throttling, правильный выбранный ADC и no second TCP; Stage26C OPEN.

## Формальные незакрытые gates
| Gate | Содержание | Состояние |
|---|---|---|
| S01 | Same-run original BIN, FRange, sample index, GetSignal ring start/end/AC/DC | OPEN Stage27B/29 |
| S02 | Второй независимый original N/ADC pre/post FFT full N/2 bitwise | PARTIAL: Z8 одна пара |
| S03 | Tag0: post-mode log output/пределы/пиксельный Y, summary+clipboard selected record | PARTIAL: Z10 3/3 summary |
| S04 | Tag1: линейный ВУ full original array, summary, шкалы | OPEN real golden |
| S05 | Tag2: линейный ВС original integration + summary | OPEN real golden |
| S06 | Tag3: линейный ВП original integration + summary | OPEN real golden |
| S07 | FIR/огибающая: оригинальный профиль IDP, вход, переходные процессы, амплитуды | PARTIAL source/candidate |
| S08 | TQGrapher курсор, scroll, select/current record, Copy/Save, paired pixels | OPEN |
| S09 | Длинный LIVE FFT 65536/262144 без потери RAW/BIN и перегрузки | OPEN Stage26C |
| S10 | Full same-run 4-mode end-to-end original MVKView vs Qt Windows acceptance | OPEN |

## Порядок реализации
Сначала Stage29 — равный оригинальный GetSignal input/window/ring/DC и огибающая (без переписывания уже точного FFT). Затем Stage30 — независимые original reference Tag0..3 по одному RAW/ADC/Fs/N/FRange, full power after-mode/3 summary/actual XScale/cursor/clipboard, затем pixel reference. Stage26C — отдельно длинный live ring с CPU/IO guard, Stage31 — UI, Stage32 — long-run.
Исходные PAS/DFM/EXE/IDP/BIN/RAW/PCAPNG и actual original FFT golden оставлять только приватно. В GitHub — агрегаты/код/синтетические проверки. Не заменять отсутствие одинакового измерения совпадением формы графика, не менять доказанные StageZ8/Z10.