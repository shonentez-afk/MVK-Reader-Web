# Stage109: независимый контроль аппаратных записей R6.1

1. Распаковать пользовательский TEST_*.7z в локальную папку (для этого пакета используется системная libarchive.so.13, скрипт libarchive7z.py).
2. Положить `новый тест 84.pcapng` рядом, не публиковать промышленные записи.
3. PCAPNG, пример (подставить фактический адрес прибора):
   `python pcap_tcp_audit_generic.py "<capture>.pcapng" --server-ip <ipv4> --out-dir <output>`
   Инструмент пишет только в выбранный выходной каталог и сохраняет отдельный реконструированный RAW. Сравнить первые N байт с `incoming.raw` и проверить нулевой клиентский payload / отсутствие gaps/conflicts.
4. Проверка кадров/ZIP/всех выходных SHA256:
   `python independent_frame_file_audit.py "<TEST_dir>" frames_audit.json`
5. Проверка каждого float32 и 60x8x70 численных полей:
   `python verify_live108_independent.py "<TEST_dir>/incoming.raw" "<TEST_dir>/BIN_TSXML_VALUES_TABLE_RECONSTRUCTED" --report samples_audit.json`
   Требуется NumPy. Заявленный штатный неполный хвост обрабатывается по `EXPORT_AUDIT.json` только при правильном окончании предыдущих кадров.
6. Проверка финального TABLE и хода времени:
   `python check_aux_table_and_timeline.py "<TEST_dir>" timeline_audit.json`

**Ограничение:** эти тесты подтверждают внутреннюю целостность и семантику восстановленного экспорта, но не побайтовую эквивалентность с оригинальным MVKView в этом же сеансе.
