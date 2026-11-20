# MVKView 1.0.47 — GetValueText, WriteValues, оригинальный RU TABLE и сквозная проверка

Дата: 20.11.2026. Ветка: research/stage111-mvkview-desktop-20261029. Main не менять; никакие приватные файлы в GitHub не загружать.

## Исходный оригинал

- _Unit125.pas:008066F0 — WriteValues на реальном PARAM 0x3100 пишет hh:nn:ss.zzz, по каждому выбранному ADC проходит SPEC43, RESULT6, BAND24, затем TACH6; разделители |, CRLF, @LStrFromUStr из Delphi Unicode в Windows ANSI.
- _Unit128.pas:0084E020 — bWriteTable: sep=|, 30 RESULT/BAND строк, пустая строка, шесть TACH строк, выбранные 8+2 канала, GetTitle/GetValueText/GetUnits.
- _Unit115.pas:007CE6E4, 007CF4A4 — source 30 типов, 13 используемых formatter ветвей, Advanced через Bits/BitStart + GetTitleByID/TLanguage.
- _Unit114.pas:007B2090 — Float32 FormatSpec=4, шаблон от 0. с десятичными знаками и исходный Delphi FormatFloat.
- Сверено с приватными Projects.7z, mvkview.idp, mvk_idr(1).sqlite. Приватные PAS/IDP/SQLite и пользовательские записи не публиковать.

## Доказательство на настоящих файлах пользователя

- VALUES-2026-10-28--10-11-33(2).csv: 99 953 байта, SHA256 664fc1cb8efdf5be8b7d43758f66a272a2831ea1addbb1b4fd034226f0274501, 63 тика.
- TABLE-2026-10-28--10-12-02(2).csv: 1 699 байт, SHA256 97fba2de39e7272bfacbbad50635064ca723eb056eebbb678e6ac56981854eb3.
- Единственный совпавший тик 10:12:02.623: все 90/90 RESULT/BAND значений по АЦП 1, 3, 6 точно одинаковы с TABLE. Разные дни/файлы BIN/TSXML нельзя без проверки считать одной сессией.
- Полный оригинальный заголовок VALUES для 3 ADC × (43+6+24) независимо восстановлен по именам и флагам: 5554/5554 байта. SHA256 faf529700f0a597d44e112cdd9459634748f56119f0469adc882e189603ef467.
- Весь TABLE построен независимо из единственной совпавшей строки VALUES и подтверждённых имён/Units/TACH: точное совпадение 1699/1699 байт с оригиналом, включая обе секции, CP1251, CRLF и все пустые поля.
- Все 12 701 ненулевых числовых полей из оригинального VALUES воспроизводят текстовый FormatSpec=4 после обратного преобразования в float32 как в Python, так и Go. Это НЕ идентичность битов исходных приборных DWORD и НЕ полный Delphi x87-паритет.

## Код текущего пакета

1. original_ru_csv_layout.py: один источник 43 исходных SPEC частот, 6 RESULT, 24 BAND, 6 TACH, Units и 10 ранее извлечённых ru-ru Advanced подписей. Кодировка Windows-1251, без BOM; CRLF, sep=|, исходный порядок каналов.
2. original_values_table_pair_qa.py: локальный параметр --full-table-parity; подтверждает полный TABLE по уникальной строке VALUES, не утечёт измеренные числа. Если замеры различаются, проверка закрыта.
3. original_live_table_snapshot.py: сохранён старый RAW-аудит как отдельная функция; добавлены build_live_ru_table_candidate_rows и export_live_ru_table_candidate на настоящем валидированном одиночном TCP/PARAM источнике. Неизвестное поле — UNKNOWN, не поддельные 0 или ####.
4. original_measure_controls_ui.py: LIVE bWriteTable теперь сохраняет русский CP1251 source-format CANDIDATE вместо диагностического UTF8-BOM/RAW, с правдивым предупреждением о непроверенном Delphi-byte-паритете.
5. original_source_ru_values_acceptance.py: независимый 4-file компаратор: RECEIVED.jsonl + RAW_LAYOUT.csv + TEXT_CANDIDATE.csv + RU_PROFILE_CANDIDATE.csv. Пересчитывает заголовки, типизированные исходные значения, Advanced bit IDs, CP1251, SHA, порядок, маски и целостность optional final audit.
6. Новые unit/Qt/Go-независимые тесты проверяют RU header SHA и размер, TABLE full source byte layout, выбранные каналы, оригинальные подписи, CRLF, обязательность полной информации и отказ от подмены.

## Границы достоверности

Исходная структура и пара реальных результатов подтверждены. Но весь оригинальный Delphi GetValueText для всех 30 типов на ВСЕХ входных DWORD пока не подтверждён byte-to-byte: нужны Win32 x87 rounding на границах, DateTime/ANSI иных локалей и парная оригинальная сессия с теми же регистрами. Новый живой RU WriteValues и TABLE — source layout CANDIDATE. Три флага original_delphi_compatibility_verified, original_delphi_values_csv_byte_parity_verified, physical_mvk01_e2e_verified остаются FALSE до настоящего 1:1 hardware oracle.

Проверить GitHub Actions по финальному SHA и Windows EXE перед подтверждением. Следующий крупный этап: реальные идентичные входные DWORD двух программ, отказоустойчивая локализация и завершающая аппаратная проверка IP → Измерить → PARAM0x3100 → GetValueText/WriteValues + bWriteTable → Stop.

Не просить повторно BIN/TSXML/VALUES/TABLE за 28 октября: все они уже предоставлены пользователем.
