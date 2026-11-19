# MVKView 1.0.47 — единый численно-файловый пакет Mode2, 19.11.2026

**Рабочая ветка:** research/stage111-mvkview-desktop-20261029.
**Кодовый пакет:** 5de67779e763411ce0d13a4b653f1bcf62c0d240 + исправление приёмочного теста 0be565fb9abf913d960a8f1354e6bff1580ff853.
**GitHub Actions:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44480562363 (проверить фактические 5/5, не путать с прежними run).
**Прежняя полная приёмка Task2/приёма/Stop:** https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/44476472842 — 5/5 PASS.

## Тройная приватная сверка — проверена в текущей работе

1. /mnt/data/Projects.7z: реально извлечены _Unit114.pas, _Unit115.pas, _Unit125.pas, _Unit128.pas и mvkform.dfm — все пять размеров и SHA256 совпали с sqlite.source_files.
2. /mnt/data/mvk_idr(1).sqlite: PRAGMA quick_check=ok, функции/вызовы; source GetSignal: 007D0D9F..007D0DD5 (RMS), GetSpectrum: 007D16A7/007D1731 → 007D2164 (интегрирование мощности), 007D1FE8 (оконная FFT).
3. /mnt/data/mvkview.idp: SHA256 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438, приватный образ FIR/частот, все 10×512 исходных банков конечны и содержат данные; никакие оригинальные байты и коэффициенты не копировались в репозиторий.

## Одна связанная техническая реализация

- envelope_idr_candidate.py: оригинальный GetSignal после FIR/IQ накапливает квадраты исходных Float32 по одному в сохраняемый на каждом шаге Float64 аккумулятор, затем sqrt(sum/N) * FRange с финальным Float32. Старый NumPy pairwise mean расходился по порядку арифметики. Новая _source_getsignal_rms_stepwise использует add.accumulate Float64 по исходному порядку; результат остаётся кандидатом (Win32 Extended sqrt не проверен). Запрет NaN/Inf, запрет не представимого в Single FRange.
- envelope_spectrum_idr_candidate.py: режимы 2/3 исходной 007D2164 используют сохранённую Single величину N/Fs, затем мощность * ((159.154943091895 / bin) * Single(N/Fs))². Каждый проход интегрирования записывает Float32. При переполнении Float32 отказывается показывать недостоверный спектр.
- original_mode2_source_files.py: Windows-1251 XML допускает имена с кириллицей U+0410..U+044F и оригинальной безопасной пунктуацией; по-прежнему закрыты path traversal, ссылки и управляющие символы, original byte-exact TSXML НЕ заявлен.
- original_mode2_paired_acceptance.py: строгий локальный инструмент парного сопоставления исходного MVKView и нашего вывода на ОДНОМ источнике, по желанию SHA+байтам обоих incoming.raw; сравнение ADC BIN Float32 / TACH bytes / GetSignal Single / GetSpectrum Power+Y Single / TSXML CP1251 / VALUES CSV; число несовпадающих Single, отклонения и первый байт, хеши, размер. Исходные значения, полные имена путей, файлы и приватные данные никогда не добавляются в отчёт или GitHub.

## Длинные оригинальные потоки

Дополнение [2d19716](https://github.com/shonentez-afk/MVK-Reader-Web/commit/2d19716b66f90e6824b8d6bd035715686331d077): два исходных `incoming.raw` читаются потоком с фиксированным буфером до 2 ГиБ **каждый**; обе SHA256 считаются по всем байтам, а не по выборке, и несовпадение любого фрагмента блокирует паритет. Проверяется также отсутствие изменения файла в процессе чтения (размер и mtime). Память не увеличивается с длительностью записи. Для отдельных численных Float32-файлов по-прежнему установлен отдельный лимит 128 МиБ на пару, поскольку для точных квантилей отклонений требуется полный массив; это явно проверяемое ограничение, не молчаливое усечение.

## Как выполнить парную локальную приёмку при наличии оригинальных файлов

Создать **на компьютере оператора**, не в публичном репозитории, JSON-файл (например, mode2_compare.json), отредактировав имена существующих локальных файлов:

~~~json
{
  "session_id": "MVK01_OPERATOR_REFERENCE",
  "reference_raw_name": "incoming.raw",
  "candidate_raw_name": "incoming.raw",
  "files": [
    {"kind": "ADC_BIN_F32", "reference_name": "original_adc1.bin", "candidate_name": "candidate_adc1.bin"},
    {"kind": "GETSIGNAL_F32", "reference_name": "original_signal.f32", "candidate_name": "candidate_signal.f32"},
    {"kind": "GETSPECTRUM_POWER_F32", "reference_name": "original_power.f32", "candidate_name": "candidate_power.f32"},
    {"kind": "TSXML_CP1251", "reference_name": "original.tsxml", "candidate_name": "candidate.tsxml"},
    {"kind": "VALUES_CSV", "reference_name": "original.csv", "candidate_name": "candidate.csv"}
  ]
}
~~~

~~~bash
python -m mvk_compatible.core.original_mode2_paired_acceptance \
  --reference-dir /local/path/original \
  --candidate-dir /local/path/candidate \
  --manifest /local/path/mode2_compare.json
~~~

Поля reference_raw_name и candidate_raw_name **необязательные только когда оригинальный RAW недоступен**. При их указании различающийся TCP поток приводит к ошибке; одинаковые RAW нужны, чтобы сравнить численные результаты одного и того же сигнала. Инструмент не извлекает эти файлы из оригинальной программы автоматически и не записывает результаты проверки в сеть. Код возврата 0: все предоставленные пары байтово равны; 2: есть расхождения. Ни один результат не устанавливает original_delphi_compatibility_verified=true без аппаратной идентичности и доверенного происхождения исходных данных.

## Ограничения и следующие действия без дробления

- Сохраняется original_delphi_compatibility_verified=false. Численная исходная последовательность подтверждена дизассемблированием, но **нет** побитовых Win32 x87 runtime reference для полной FIR/Hann/FFT/Power/Y, достоверного архивного FRange и полного GetValueText.
- Нет оригинального физического второго эталонного запуска МВК01/Delphi 1.0.47, чтобы подтвердить весь IP→Measure→SetRate→RX→GetSignal/Spectrum→writers→Stop на одном реальном потоке и ошибках.
- Имена файлов/TSXML/CSV/Win32 локальные timestamps пока совместимые по структуре, НЕ 1:1 byte-parity. Не помечать без оригинального файла.
- Все живые аппаратные действия требуют отдельного подтверждения оператора. Запрещено автоматически посылать Flash/IP/Reboot/Task3/4/5. Исходную ветку main не менять.
