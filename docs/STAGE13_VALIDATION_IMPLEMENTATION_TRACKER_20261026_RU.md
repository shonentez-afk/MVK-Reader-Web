# Stage 13 — рабочий журнал задач и статуса

Производственная v0.3.40 заморожена, все изменения в независимом тестовом прототипе.

## GitHub Issues
- #1 P0 AUX4700 полный побитовый архив — **прототип реализован**, требует полного теста PCAPNG/Windows.
- #2 P0 AUX160 все четыре слова — **прототип реализован**, требует полного теста PCAPNG/Windows.
- #3 P0 FFT единицы/масштабы и MVKView — **открыта**.
- #4 P0 отчёты полноты и Windows — **частично:** экспорт AUX4700_FULL.csv.gz, AUX160_FULL.csv.gz, PERSISTENCE_AUDIT.json с SHA256; остальные проверки TODO.
- #5 P1 TCP FIN/RST, временная ось, полевая приёмка — **открыта**.

## Проверка реализованного P0 (офлайн)
База Stage12.2. Новые SQLite таблицы: aux4700_full(report,adc,tag,status,values_f32_le BLOB 576B); aux160_full(report,adc,entry,current_bits,descriptor,reference_bits,extra_bits). Всего 144 float32×8 АЦП на каждый AUX4700. Побитовая запись с сохранением NaN payload. `stage13_export_audit.py` выгружает все индексы и биты, проверяет 8 записей на AUX4700 и 4 на AUX160, сверяет количество `metrics`, выполняет SQLite integrity_check, SHA256 выгрузки.

RAW №83: 24 AUX4700 => 192 строки; 108 AUX160 => 384 строки; metrics 192; graph 104; integrity ok.
RAW №84: 24 AUX4700 => 192 строки; 108 AUX160 => 384 строки; metrics 192; graph 104; integrity ok.
59/59 unittest OK. Эти тесты прошли на Linux, Windows ещё не проверена.

**Важно:** полные временные метки и сырые bytes AUX4700/AUX160 не сохранены в этих таблицах; индексы report отражают порядок сообщений, но временная привязка и cross-correlating PCAPNG ещё в работе. FFT lines экспорт ещё не реализован; текущий тест process_file работал без spectra=True и поэтому fft=0 ожидаемо. Не считать Stage13 завершённым.
