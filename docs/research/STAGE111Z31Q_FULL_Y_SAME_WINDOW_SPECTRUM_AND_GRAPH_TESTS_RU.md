# Stage111Z31Q — полный оригинальный Y на одном BIN/окне и завершение спектральных проверок

Дата: 05.11.2026. Ветка `research/stage111-mvkview-desktop-20261029`.
**Новые исходные расчёты не изобретаются.** Реальные ранее принятые FFT N262144 (131072/131072), четыре Tag0–3 post-Power→Y (каждый 131072/131072), 3/3 summary, FRange, Hann/x87, 10×512 FIR, BIN №83/44 и исходная min/max отрисовка **не проверяются повторно как новая работа**.

## 1. Реализован недостающий связующий компаратор

`mvk_compatible/private_same_window_spectrum_compare.py` ([Stage31Q code](../../mvk_compatible/private_same_window_spectrum_compare.py)):

1. Принимает **только локальный** оригинальный Power/Y-манифест старого Stage31A, который раньше уже проверял SHA256 и полный N/2 Power→Y; при неправильных исходных Power/Y отклоняет.
2. Открывает **настоящий локальный** `DirectBinSession` для Single BIN+TSXML либо проверенный `OfflineSession` Native R6.1 ZIP, а не выдуманный `session=object()`.
3. Требует **отдельный операторский манифест** привязки одной исходной RAW Float32 выборки к оригинальному запуску (ADC, Fs, N, режим 0–3, EnvelopeCode 0–31, first/last sample, исходный SHA256, input_domain). Исходный SHA **не извлекается автоматически из нашего же результата как якобы доказательство оригинала**. Без такой привязки сравнение блокируется.
4. До расчёта проверяет физические байты окна и SHA256, отсутствие нулевого дополнения, исходный выбранный N/режим/частоту; для FIR ещё точную длину source-derived обратной истории и локальный оригинальный SHA-проверенный IDP. Выбирается **ровно окно**, не ближайшее по времени ПК.
5. Использует готовые `session.spectrum` / `session.spectrum_envelope` с `backend=idr_float32`, исходным FRange из оригинального манифеста и явно заданным input_domain. Проверяет `input_source_window` от возвращённого спектра (SHA/границы/частота); считывает **все N/2 Float32 Y**, без отрисовочной обрезки TQGRSeries.
6. Считает bitwise equal-бинов, первый отличающийся бин, максимальную |ΔY|, ULP и частоту максимума отдельно. Итог не содержит оригинальные массивы, пути, коэффициенты, прикладные сетевые команды.
7. Даже при 100% равенстве возвращает `original_runtime_same_thread_window_independently_authenticated=false` — операторский манифест с SHA сам по себе не подтверждает непрерывность работы original Windows процесса.

**Отдельно уже существует:** `private_getspectrum_prefft_envelope_compare.py` для full pre-Hann envelope при доступном original before_fft; его не дублировать. Другой существующий `stage83_compare_spectra.py` — для пары CSV той же частотной сетки. Отсутствующий original full Y для действительно парного BIN — **блокер оригинальной приёмки по данным**, а не недоработка созданного компаратора.

## 2. Локальный вызов без выгрузки данных

Пример CLI для обычного FFT:

```bash
python -m mvk_compatible.private_same_window_spectrum_compare --source-archive "LOCAL_MVK_ADC4.bin" --original-power-y-manifest "PRIVATE_ORIGINAL_POWERY.json" --original-window-evidence "PRIVATE_ORIGINAL_WINDOW.json"
```

Для спектра огибающей добавляется `--original-idp "LOCAL_mvkview.idp"`. Нужен **тот же EnvelopeCode в original и в evidence**. Этот CLI не открывает соединения с МВК и не записывает вывод в GitHub. Exit 0 = Y bitwise equal при операторской заявленной паре, 1 = численное отличие, 2 = отсутствующие/некорректные доказательства.

Структура **приватного** (НЕ коммитить в GitHub) `PRIVATE_ORIGINAL_WINDOW.json`:

```json
{
  "schema": "MVKVIEW_ORIGINAL_SAME_RAW_WINDOW_FULL_Y_V1",
  "original_window_provenance": "OPERATOR_ASSERTED_ORIGINAL_RAW_SINGLE_WINDOW",
  "channel": 4,
  "fft_n": 262144,
  "raw_sample_rate_hz": 65536,
  "spectrum_mode": 0,
  "envelope_code": 0,
  "first_archive_sample_index": 0,
  "last_archive_sample_exclusive": 262144,
  "original_raw_window_float32_sha256": "<64 hex from original raw window independently recorded>",
  "input_domain": "calibrated_bin"
}
```

**НЕ копировать здесь автоматически SHA нашего BIN в поле «original»**: оператор должен связать исходный SHA с действительной оригинальной выборкой; если такого независимого источника нет, оставить приёмку открытой. Код принимает только формат lowercase SHA из 64 символов. `first/last` в примере — **синтаксический образец**, а не якобы подтверждённый диапазон реального №83/№44.

## 3. Внесены регрессионные испытания

- `mvk_compatible/tests/test_stage111z31q_same_window_spectrum.py`: 4 режима Tag0–3 на самосозданном BIN+TSXML, полные 512 Y-бинов для N=1024, битовая проверка, SHA-дрейф на один индекс, отказ по неверным Fs/N/ADC/домену, корректное сообщение о численном расхождении Power/Y и синтетическая огибающая (только коэффициенты `fake_profile`). **Все эти эталоны синтетические, не оригинальные.**
- `mvk_compatible/tests/test_stage111z31q_qt_spectrum_edges.py`: реальные Qt-пути с локальными синтетическими BIN, N=8192/65536/262144, Fs=16384/65536, Tag0–3, исходный график min/max ↔ sparse zoom ↔ min/max, выбор точного бина, averaging=1 и =3 без ошибочного деления на N, выход курсора за границу, неизменность полного N/2 и исходных Float32.
- **Испытания original Qt/PASCAL на тех же самых real BIN №83/№44 заново не проводились:** соответствующие приватные original Y/снимок исходного предфильтрового окна отсутствуют в этом хранилище.

## 4. Проверка исходных файлов и следующий gate

Проверены физически предоставленные локальные `Projects.7z` SHA256 `3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363` и `mvkview.idp` SHA256 `77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438`. IDR фрагмент `_Unit115:007D13D4..007D150F` подтверждает исходный `GetAdjustedEnvelopeLength`, выбор RAW, удаление DC до FIR, дальнейший FFT после FIR. **Точное соответствие окна оригинального GetSpectrum нашей обратной длине FIR по другой N/Fs остаётся непроверенным** — здесь нельзя объявлять полную envelope parity до original Win32 case.

Сначала закрыть CI [#42004815613](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/42004815613); на момент записи *ожидает подтверждения*. Если тесты дают конкретное отклонение — исправлять минимально. Затем — только при доступных исходных файлах — реальные same-BIN/full-Y и original Win32 envelope input/output; курсор/scale/другие N/Fs на уже созданных тестах. Не переходить к временному сигналу/страницам преждевременно.
