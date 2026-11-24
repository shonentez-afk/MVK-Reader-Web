# Stage111 Z31EE — интеграция TACH RX / метаданных ADC
Дата: 24.11.2026.

## Ревизии и результаты
- Рабочая ветка research/stage111-mvkview-desktop-20261029: 8ebddeedb40d7a7f84738db4d09552a467686479, исходный CI 5/5 #45364186556. Не изменена.
- Кандидат research/stage111-ee-tach-rx-integration-20261124: e547e855ec42bfac59b8e81b75e9e6debb0e05af (реализация), d763e3634d0f89312bb600fd93af4cc1c6fcc758 (тесты и CI). Сравнение с рабочей веткой: ahead 2 / behind 0, 19 файлов.
- [CI кандидата](https://github.com/shonentez-afk/MVK-Reader-Web/actions/runs/45368283654): 3/3 SUCCESS. Native Go Linux и Windows: targeted/full go test, go vet, go build PASS. Cross-language: 30 passed; full Python offline regression: 2723 passed, 150 skipped, 4 warnings, 30 subtests passed.
- Новый GUI/EXE не собран и не принят. На приборе не проверялось. Main, рабочая ветка и приватные материалы не затронуты.

## Что реализовано в коде
- Отдельное состояние оригинальных метаданных и двух TACH latch подключено к реальному Task2 Monitor. Первый PARAM descriptor фиксирует Range/Units, в том числе переход Stage0 при Freeze; TCP epoch сбрасывает признаки свежести без подмены удержанных значений. Неизвестные слова не объявляются полученными. LiveStatus/summary содержат source_adc_metadata_observation с numeric_scaling_applied=false.
- Принятые TACH bytes меняют локальный latch; 0x3100 сохраняет снимок до сброса обоих latch, сброс происходит и при неактивном writer. Last byte сохраняется. Forensic register image и RAW не переписываются.
- SOURCE_ORIGINAL_TACH_FRAME_GATE.dat: 64-byte записи, frame index/socket epoch/rates/channel/Freeze/admission/frame SHA256; ограниченный объем, итоговый SHA/count/schema, fail-closed при ошибках. Journal является локальным доказательством приемника, а не подписанной прибором трассой.
- V2 VALUES schema MVK_SOURCE_VALUES_3100_ORDERED_RAW_TICK_V2_TACH_LATCH: два derived DWORD в копии prefix. V1 historical replay сохранен, V2 не допускает downgrade. Python независимо проверяет журнал и воспроизводит изменение/сброс, сопоставляет реальный Go output. Multi-socket export по-прежнему не сертифицирован.
- Actual Monitor/Finalize fixtures: три строки [1,0], [42,0], [0,1], unarmed reset, Freeze, неверная частота, одинаковые bytes, suffix, reconnect state. Повторно хешированные поврежденные admission/frame/epoch/derived row отвергаются.
- Исключения оригинального writer и аппаратные вызовы не аттестованы.

## Следующая единая реализация: FRange/Units numerical path
Не повторять статический Atlas v32 и standalone latch pass. Взять актуальную рабочую ревизию, проверить пересечение с кандидатом, сохранить проверенный результат.
1. source_original_ring.go / monitor.go: заменить hardcoded FRange1 для нового source-aware domain только при валидной известной метаинформации; ноль -> 1 по контракту. Не сертифицировать неизвестную/нечисловую метаинформацию. Existing Python DSP принимает только положительные конечные коэффициенты; отрицательный конечный случай требует отдельного решения, не выдавать его за восстановленный численный паритет. Исторические V1 окна сохранить.
2. source_live_long_window.go -> original_source_long_window.py -> original_source_ring_receipt.py -> original_live_view_gate.py: привязать окно к metadata identity, socket epoch, raw factor bits, units, stage/known; отвергать устаревшее окно после первого descriptor или reconnect. Не пересчитывать старые физические samples задним числом.
3. Plain GetSignal: копировать физическое кольцо. Filtered GetSignal: нормализация physical/FRange перед FIR, затем выходной масштаб один раз. GetSpectrum: использовать DOMAIN_ORIGINAL_STORAGE и фактический FRange в spectrum_for_zip / prepare_original_fft_input; проверить mode0 dB и physical summary, а также filtered spectrum main_window.py. Не умножать коэффициент дважды.
4. Qt labels/summary/cursor и TSXML: перенос источника единиц и их известности. WriteData raw stream, существующий Native BIN exporter и forensic RAW не смешивать с physical ring; отдельная проверка file-open metadata. TACH PageStatus/TABLE нуждаются в отдельной локальной projection, не в подмене raw register image.
5. Синтетическая приемка: nonunit range, zero, unknown/invalid, первый descriptor/Freeze, reconnect, stale window, plain/FIR/FFT/modes, RAW unchanged, V1/V2 replay, Stop/ошибки. Полная Windows Qt/EXE сборка, затем отдельная SAME-RX аппаратная приемка.

## Ссылки
- [Исходный код кандидата](https://github.com/shonentez-afk/MVK-Reader-Web/tree/research/stage111-ee-tach-rx-integration-20261124)
- [Документация реализации](https://github.com/shonentez-afk/MVK-Reader-Web/blob/research/stage111-ee-tach-rx-integration-20261124/docs/research/MODE2_STAGE111_EE_TACH_RX_INTEGRATION_CANDIDATE_RU.md)
