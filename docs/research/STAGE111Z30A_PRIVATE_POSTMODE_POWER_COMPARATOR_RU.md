# Stage111Z30A — локальная проверка original GetSpectrum post-mode power

Дата: 02.11.2026. Ветка: `research/stage111-mvkview-desktop-20261029`.

## Что добавлено

- `mvk_compatible/private_getspectrum_postmode_compare.py`: read-only сравнение Float32 N/2 **перед** low-bin/mode (`0x007D154B`) и **после** mode (`0x007D17E7`) внутри одного заявленного оператором original GetSpectrum вызова. Все Tag0/1/2/3; Tag2/3 source-derived `_delphi_integration_power` повторно используем, FFT не вычисляем и не меняем.
- По желанию — три оригинальных Float32 HEX после summary (`0x007D1900`): отдельные побитовые сравнения с исходным post-mode и реконструированным post-mode, без второго summary/пересчёта в графические пиксели.
- Обязательные metadata: `fft_n`, `output_sample_rate_hz`, `spectrum_mode`, нулевой индекс канала, `envelope_code`, `f_range_bits`, 2 адреса breakpoint, `same_invocation_operator_confirmed: true`, имена обоих `.bin` и их SHA256. Не пытаемся угадать режим/ADC, сдвигать массивы или подбирать FRange.
- Источник и измерения не загружаются в GitHub: только алгоритм, синтетические тесты и aggregate numeric output; все данные оригинального процесса — локально.
- `mvk_compatible/tests/test_stage111z30a_private_postmode.py`: synthetic четыре режима, независимые контрольные суммы, one-ULP mutation, 3-value summary, 0/negative/NaN, повреждения metadata и symlink.

## Как проводить частную сверку

`python -m mvk_compatible.private_getspectrum_postmode_compare ORIGINAL_CAPTURE.json`

Создать в **одной локальной папке** два разных raw little-endian Float32 дампа длиной `fft_n/2*4`: `before_power.bin` прямо на `007D154B` (перед low-bin), `after_mode.bin` на `007D17E7` (после обработки mode), от **одного original GetSpectrum вызова**. Сохранить SHA256 обоих. Манифест пример:

```json
{
  "schema": "MVKVIEW_ORIGINAL_POSTMODE_CAPTURE_V1",
  "fft_n": 262144,
  "output_sample_rate_hz": 65536,
  "spectrum_mode": 2,
  "channel_index_zero_based": 3,
  "envelope_code": 0,
  "f_range_bits": "0x3F800000",
  "before_stop_va": "0x007D154B",
  "after_stop_va": "0x007D17E7",
  "same_invocation_operator_confirmed": true,
  "before_power_file": "before_power.bin",
  "after_mode_file": "after_mode.bin",
  "before_power_sha256": "REPLACE_WITH_REAL_LOWERCASE_SHA256",
  "after_mode_sha256": "REPLACE_WITH_REAL_LOWERCASE_SHA256"
}
```

Для summary добавить `summary_stop_va:"0x007D1900"`, `output_mean_bits`, `output_peak_x_bits`, `output_peak_y_bits` (все `0xXXXXXXXX`). Обязательно записывать действительные mode, Fs, канал, EnvelopeCode и FRange **исходного процесса**. Это шаблон полей, приведённые численные значения не являются эталоном.

## Границы доказательства

**CODE IMPLEMENTED; реальные Tag1/2/3 original after-mode файлы по-прежнему НЕ ПОЛУЧЕНЫ, сопоставление 1:1 не подтверждено.** Инструмент принципиально не способен самостоятельно доказать, что два дампа с одного реального оригинального вызова. Tag0 старые Z8/Z10/Z13 не переисследуем. Stage27B same-run original↔Native BIN, Stage29B GetSignal return, Stage26C long live, Stage31/32 остаются OPEN. Ни оригинальный FFT golden, ни Native R6.1, ни main/Web не менялись.

CI/Windows EXE: наличие нового коммита не означает успешного CI и не является новым подтверждённым EXE. Последний подтверждённый Windows exe всё ещё Stage29C2 source `5cbb0d69adf904160df33e41d55f58a56b3daceb`, artifact 13129387408, SHA256 `9d36482b491952c597dac20e5dee497a77cb2e041d155ae776a358b4137221c2`.
