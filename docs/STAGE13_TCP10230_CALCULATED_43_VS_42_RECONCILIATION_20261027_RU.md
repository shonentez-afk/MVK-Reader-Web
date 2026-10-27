# Correction: TCP/10230 calculated frames and 42-versus-43 third-octave counts (2026-10-27)

## Prior findings recovered from this repository
The project had **already** reverse-engineered a 4700-byte calculation frame on TCP/10230 on 26 Oct. Evidence: docs/FRAME_4700_MODBUS_MAPPING_20261026_RU.md, docs/FRAME_4700_REAL_RAW_REGRESSION_20261026_RU.md, tools/raw_offline_audit/decode_4700.py. Data: 2 independent stored 12-second RAWs, 24 calculation frames each (48 total), 8 channels per frame (384 channel records). Header 28 bytes, 8 blocks of 584 bytes. Relative words per channel: 0 sensor voltage; 1-43 third-octave acceleration; 44-45 reserved; 46 crest factor; 47 wideband RMS; 48-71 RMS for 24 metrics; 72-79 reserved; 80-103 equivalent peaks; 104-111 reserved; 112-135 equivalent spans; 136-143 reserved; 144 status bitfield. Nonnzero RMS/peak/span triplets 4032 and 4608, with peak ≈ sqrt(2)*RMS and span=2*peak at float32 precision. Structural map is high confidence, specific calibration/metric assignment still provisional.

**Correct protocol model**: TCP/10230 sends BOTH waveform ADC frames (1052 bytes) and calculated values (4700 byte frame), with other service/tach frames. TCP/502 Modbus FC03 also exposes calculated values, statuses and calibration. The current v0.3.40 UI capabilities describe calculated=502, wave=10230 as implementation routing, NOT the exhaustive capability of the network protocol. The earlier '10230 only raw signal' architecture note is WRONG.

## Count 43 vs 42
Manufacturer Appendix 2 maps 43 float32 third-octave readings, whereas text in Appendix 1 P1.3 mentions 42. Existing repo decoder contains 43 centers from 0.63 to 10000 Hz (MVK_Reader_Web/collector/decoder.py) and tests check this size. The real TCP/10230 4700 byte frame likewise contains 43 positions (words 1-43). This proves the data representation has 43 slots. It does not prove all slots always hold calculated nonzero measures.

Hypothesis to test: text P1.3 may count 42 usable bands excluding 0.63 Hz (then 0.8 to 10000 inclusive). This explanation is not yet directly established. Inspect first third-octave position across stored frames and synchronized FC03 if available; distinguish a placeholder from a genuinely computed band. Another explanation is a textual miscount in Appendix 1. Do not label either as established until evidence.

## Consequence / corrections
Promote TCP/10230 4700-byte calculation frame to the Stage13 input architecture. Reuse the existing offline decoder instead of creating another parser. Respect freeze of production v0.3.40 and no live connections without permission. Sync START_NEW_CHAT_RU.md, PROJECT_STATUS_RU.md and project decisions.

## 27.10: итоговая сверка источников
В руководстве таблица 4, раздел 5.2, приложение 1 п.1.3 и приложение 2 пп.3.4/3.5.5 независимо задают 43 частоты 0,63–10000 Гц; одно упоминание «42» встречается в тексте П1.3. Позиции 1–43 кадра 4700 байт согласуются с 43 полями, а битовый статус расположен отдельно в позиции 144. По офлайн-аудиту четырёх PCAPNG первая позиция не пустая. **Решение для декодера: сохранять 43 значения; «42» считать вероятной опиской или редакционным несоответствием, без утверждения о доказанной причине.** Коэффициент пересчёта и диагностический статус не следует вставлять внутрь массива. Не повторять обсуждение без новых данных.
