# Stage 111H — GetNarrowbandValue, GetNoisePeak и независимое сравнение трёх полей Copy

**Дата:** 29.10.2026. **Ветка:** `research/stage111-mvkview-desktop-20261029`. **Цель:** восстановить дополнительную численную функцию оригинальной MVKView и подготовить доказательную сверку показателей `GetSpectrum`. Программа — самостоятельный Windows Qt Desktop, без сервера. **Паритет Delphi не принят.**

## 1. Проверка оригинального кода, а не догадка по графику

В локальных приватных исходниках `Projects.7z` изучены `_Unit115.pas:007D0E58–007D10F3` и `TMvkChannelStorageCalcParams`; оригинальные файлы не публикуются. Функции с отдельным названием `GetNoisePeak` в этом классе нет: **это булев флаг третьего аргумента `GetNarrowbandValue`**.

| IDR адрес | Установленное действие |
|---|---|
| `007D0E85–007D0E98` | `OutputLength=SignalLength/2`, `OutputSampleRate=FSampleRate` |
| `007D0E9B–007D0EC1` | `center=Round(SignalLength/FSampleRate*InputValue)`, частота входа как Single |
| `007D0EC4–007D0EF9` | `radius=Max(1,Round(center_unrounded*0.0005))` |
| `007D0F02–007D0F60` | Частота допустима, только если `1<=center<OutputLength-1`; иначе оригинальная ошибка `Invalid frequency band` |
| `007D0F7D–007D0FA7` | Берётся **последнее исходное полное временное окно**, выполняется вычитание DC `007D2344`, затем локальный FFT `007D1FE8` |
| `007D0FAC–007D0FF3` | Вызов `007D21A8` на диапазоне `center-radius..center+radius`, `OutputValue=sqrt(SUM(P)/2)*FRange/(N/2)` |
| `007D0FF7–007D100B` | Если `GetNoisePeak=True`: `excluded_radius=20*radius`, поиск начинается с `k=20*radius` |
| `007D100B–007D1028` | Просмотр только до `floor((OutputLength*64)/256)=floor(N/8)` включительно, пропуск закрытой области `center ± 20*radius` |
| `007D103B–007D106F` | Сумма трёх соседних мощностей `P[k-1]+P[k]+P[k+1]`, сравнение строго `>`; первый равный максимум сохраняется, в `OutputPeakX` записывается **индекс бина** |
| `007D107A–007D10A2` | `OutputPeakY=sqrt(best_three_bin_power/2)*FRange/(N/2)` |
| `007D1A80–007D1ADE` | `InitParams` сбрасывает поля OutputValue/PeakX/PeakY в 0 |

**Нельзя смешивать три разные логики пика:** приборный DSP/AUX4700; энергетически взвешенный `OutputPeakX/Y` функции `GetSpectrum`; трёхбинный шумовой `GetNoisePeak` в `GetNarrowbandValue`.

**Разница с небезопасным оригинальным краем:** в Delphi явная проверка `center+radius<OutputLength` не выявлена. Новый модуль **отказывается от чтения за границей** вместо эмуляции потенциально некорректного доступа. Это сознательная защитная несовместимость.

## 2. Реальный новый код

- `mvk_compatible/core/narrowband_idr_candidate.py` — две чистые офлайн-функции: `narrowband_from_full_power` для полного N/2 массива мощности; `narrowband_from_samples` для исходного калиброванного BIN с одним удалением DC. `Round` кандидата nearest-even, Single-аккумуляторы, строгие диапазоны и source tag `APP_DERIVED_NARROWBAND_IDR_CANDIDATE` / `APP_DERIVED_NOISE_PEAK_IDR_CANDIDATE`.
- `mvk_compatible/core/offline_export.py`: `OfflineSession.narrowband(channel, frequency_hz, n_fft, start_s, get_noise_peak)`. Запись выбирается явно, недостающие отсчёты не подставляются. Никаких команд TCP/10230.
- `mvk_compatible/desktop/main_window.py`: отдельный блок в **исследовательской** части спектральной панели, ниже штатного DFM: частота, флажок поиска шумового пика и кнопка расчёта. Результаты явно помечены «не приборный DSP» и «численный паритет не доказан». В основе остаётся архивный BIN, **не** показанный (возможно прореженный) график спектра.
- `mvk_compatible/triplet_reference_compare.py`: автономный CLI для локального эталона **одной** строки `bSpecCopyValue`: 3 значения с TAB, явная десятичная запятая или точка, UTF-8/CP1251, обязательные совпадающие BIN/окно/канал/N/режим. Возвращает по каждому полю абсолютную ошибку и прошёл/не прошёл заданные допуски; нет автоподбора масштаба и округления. Отчёт содержит только ошибки и SHA оригинального TXT, без полного массива измерений; даже при всех PASS всегда `original_delphi_parity_verified=false`.

Пример локальной команды сравнения по настоящему экспорту оригинала (подставить собственные файлы и одинаковые параметры, **не** отправлять TXT в Git):
```powershell
python -m mvk_compatible.triplet_reference_compare --archive "C:\private\session.zip" --reference "C:\private\mvkview-copy.txt" --channel 4 --n-fft 4096 --mode 1 --start-s 0 --backend idr_float32 --decimal "," --separator tab --report-json "C:\private\stage111h_3fields.json"
```

При анализе **спектра огибающей** дополнительно указать `--code 20 --idp "C:\private\mvkview.idp" --end-s <конец_архива_в_секундах>`; обычный BIN режим не принимает `--idp`.

## 3. Проверки и границы

Тесты добавлены в `test_narrowband_idr_candidate.py`, `test_triplet_reference_compare.py`, `test_desktop_qt.py`: синтетические бин-центры, nearest-even, радиус, band-sum, ±20*radius исключение, N/8 предел, 3-значный шумовой пик, равные пики, запрет памяти за концом массива, отказ при нехватке BIN, проверка AUX4700 без изменений, восстановление 3-field TAB/CSV локального эталона, Qt-реальное нажатие кнопки.

**Численная приёмка на оригинальной работающей MVKView НЕ проведена:** в текущих приватных материалах нет исходной строки Clipboard с доказанно одинаковыми `channel/FS/N/Start/FRange/EnvelopeCode`. Исследовательские pytest и GitHub Windows CI — не доказательство полного Delphi/x87 совпадения. `FRange` калибровки и точное Archive/Live положение остаются CANDIDATE.

## 4. Дальше — Stage 111I

1. Приватно сравнить исходную строку оригинального `bSpecCopyValue` по трём числам и исходный спектральный CSV с новым независимым CLI, на одинаковых параметрах.
2. Сверить `GetNarrowbandValue` / шумовой пик по реальному контрольному выходу оригинальной программы, особенно границы и коэффициент калибровки `FRange`.
3. Довести Delphi x87 / `007B2090` и точную геометрию курсора TQGrapher; использовать только подтверждённые параметры.
4. Затем pixel-to-pixel QA трёх вкладок и Archive/Live через один R6.1 Collector **только по отдельному разрешению**.

**Главное для нового чата:** читать оба ADR, `docs/research/STAGE111_IMPLEMENTATION_AND_HANDOFF_RU.md`, этот Stage111H отчёт, `docs/research/STAGE111_MVKVIEW_COMPATIBILITY_MATRIX_RU.md`, проверить последний Actions SUCCESS, затем продолжать Stage111I. Не пересобирать приложение со старого server.py. Stable `main` и v0.3.40 не изменять.
