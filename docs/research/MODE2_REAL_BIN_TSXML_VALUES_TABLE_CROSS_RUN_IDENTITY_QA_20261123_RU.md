# MVKView 1.0.47 — реальная сверка BIN / TSXML / VALUES / TABLE без смешивания разных измерений

**23.11.2026; только research/stage111-mvkview-desktop-20261029.** Main не изменять, приватные исходники и пользовательские измерения в GitHub не публиковать.

## Приватные оригиналы действительно прочитаны и сверены совместно

- Projects.7z, SHA256 3fad945b6f0bccf94a396875fc87098b214259263c8ec3178b507a1d0f6fd363. Извлечены _Unit114, _Unit115, _Unit125, _Unit128.pas и mvkform.dfm: 5/5 размеров и SHA совпали с sqlite.source_files.
- mvk_idr(1).sqlite, SHA256 97435654a34a69857736e21d83d7a805b976365bb540e55418fd4f564e05365c, PRAGMA quick_check=ok.
- mvkview.idp, SHA256 77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438.
- Из первоисточников: TMvkChannelStorage.GetSignal 007D0C30; GetSpectrum 007D13D4; ProcessBufferChunk 007D2398; live FRange=1 из 007D0A61. Само оборудование здесь не подключалось.

## Физически проверенные пользовательские файлы 28.10.2026

- BIN MVK00000043-ADC1-2026-10-28--10-11-32(3).bin: 8 499 200 байт; SHA256 3a7bfb4e3429ed707cde5c5f289c9d38935a07bbbc67a2cf725f57b61dea48d5.
- TSXML соответствующей записи: SHA256 40cf914adf5cf7ac3bfa13143b4af7d913a052754f8e3b135ce5fc97deb1b860. XML описывает МВК00000043/АЦП1, Fs65536 Гц, 2 124 800 Float32 отсчётов, 32.421875 с, DataLength 8499200 и InternalChannelGain=510.6.
- VALUES 2026-10-28 10:11:33: 99 953 байта, SHA256 664fc1cb8efdf5be8b7d43758f66a272a2831ea1addbb1b4fd034226f0274501; 63 тика, АЦП 1/3/6, 43 SPEC+6 RESULT+24 BAND на каждый.
- TABLE 2026-10-28 10:12:02: 1699 байт, SHA256 97fba2de39e7272bfacbbad50635064ca723eb056eebbb678e6ac56981854eb3.
- VALUES и TABLE точно содержат общий **текстовый снимок**: 90/90 RESULT/BAND ячеек в единственной строке 10:12:02.623. Это не доказательство идентичности BIN исходному live RAW.

## Независимая проверка временной связи (НЕ доказательство одного TCP)

1. В качестве независимого заранее определённого показателя выбран только столбец АЦП1 «Виброускорение, Польз. 2», а не поиск максимума по всем 219 колонкам.
2. По оригинальному BIN вычислена 0.5-секундная СКЗ переменной части (std после исключения DC). Это НЕ оригинальный полосовой фильтр или вычислительный паритет Delphi.
3. Временной сдвиг -1000..+1000 мс шагом 25 мс выбран по первым 29 тикам; 3 тика пропущены между train и test; следующие 31 тик — независимый holdout.
4. Выбран lag -475 мс. Train Pearson r=0.9589065291, holdout r=0.9789751070, all ticks r=0.9706743463.
5. Максимум для циклических перестановок holdout ≈0.2967193; p=1/31≈0.03226. Медианная пропорция VALUES к BIN RMS ~0.95956; это НЕ новый калибровочный коэффициент.
6. Вывод: высокая статистическая согласованность тренда, но **same_physical_capture_authenticated=false**, **same_original_raw_tcp_payload_authenticated=false**, Win32 parity=false. Нельзя молча объединять разные замеры.

## Что реализовано

- Новый модуль mvk_compatible/core/original_mode2_bin_tsxml_values_alignment_qa.py. CLI: python -m mvk_compatible.core.original_mode2_bin_tsxml_values_alignment_qa BIN TSXML VALUES TABLE. Только локальный read-only анализ; запрещены symlink, слишком большие/неполные/неконечные файлы, DTD/ENTITY в XML и неправильные DATA length/rate/channel; обязательны совпадающий календарный день и уникальный TABLE/VALUES снимок. Сдвиг выбирается только на train, считается holdout и циклический null. Вывод содержит только SHA256/счётчики/агрегаты без приватных измерений.
- Новый тест test_mode2_original_bin_tsxml_values_alignment_qa.py: синтетический без приватных данных. Тестирует точное выравнивание, посторонний плоский BIN, другой день, другой TABLE, некорректную Fs/длину/XML, NaN/Inf, symlink и утечку приватных путей.
- original_mode2_paired_acceptance.py теперь поддерживает TABLE_CSV в дополнение к VALUES_CSV, BIN, TSXML, GetSignal/GetSpectrum. При одинаковых файлах без подтверждённого одинакового TCP original_hardware_parity_verified остаётся false.
- test_mode2_original_paired_values_table_byte_parity.py проверяет парное точное сравнение обоих CSV и несоответствие при изменении одного байта единицы измерения.

## Принципиальный нюанс калибровки

Source original live ring при нажатии «Измерить» использует FRange=1, в то время как исходный TSXML архивного BIN хранит InternalChannelGain=510.6. Этот коэффициент нельзя переносить на live ring и нельзя выдавать за аппаратно проверенную калибровку. BIN — записанный результат, а не обязательно исходные принятые байты.

## Остаётся до полной оригинальной цепочки

- Один и тот же аутентичный физический RX/PCAP одновременно с Win32 MVKView 1.0.47 и нашей реализацией: IP→Измерить→Task2→SetRate/ACK/DENIED→PARAM/ADC/TACH→Stop, ошибки и повторные подключения.
- Численный паритет оригинального Win32 x87 для FIR, Hann, FFT, GetSignal/GetSpectrum, FRange, 4 режимов Y, курсоров на идентичных исходных DWORD.
- Прямое byte-to-byte сравнение оригинальных BIN/TSXML, VALUES/TABLE и полного GetValueText/WriteValues на той же аппаратной сессии.
- Полная проверка семи страниц, трёх форм, переключений, ошибок и закрытия файлов по настоящему MVK01.
- Ни один программный тест или корреляция не переводит original_delphi_compatibility_verified/physical_mvk01_e2e_verified в true.

Предыдущий e3bf45f: GitHub Actions #44681963587 = 5/5 SUCCESS, в т.ч. автономный Windows EXE. Новый коммит проверить отдельно по SHA и Actions. Main не менять; пользовательские BIN/TSXML/VALUES/TABLE и 3 первоисточника остаются приватными.
