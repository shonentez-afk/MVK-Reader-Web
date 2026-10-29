# Stage86 — provenance of VALUES timestamps from original MVKView IDR

Date 2026-10-29. Source: original `Projects.7z`, `_Unit125.pas` extracted independently using libarchive. Offline evidence check: **5/5 PASS**.

- `0x008085A5`: parameter block type `0x3100` triggers conditional VALUES dump; `0x008085BD` invokes `0x008066F0` when `ValuesFile` exists.
- `0x0080672B`: `0x0042F594` obtains **current computer wall-clock time**; `0x00806743`: formats `hh:nn:ss.zzz` for a VALUES CSV row. This is **not an ADC sample timestamp** and does not in itself identify device DSP window start/end.
- `0x00809880..0x00809986`: separately creates VALUES file using wall-clock filename and sets `WriteValuesTime` (session timer).
- `0x008096B5..0x008096BD`: separately sets `WriteDataTime` for BIN recording; distinct UI buttons/state machines confirmed by the IDR.
- `0x00806B95..0x00806BBF`: TSXML DateTime is taken from **current time at XML creation**, not a direct ADC first-sample clock; use it carefully.

Consequence: previous lag fitting offsets do **not** equal time between two button presses; they combine file start, transport scheduling, instrument processing latency and clock/time labeling. The VALUES 63 rows at 0.5 s cadence cannot be interpreted as a sample-accurate stream without frame-index/time correlation. Validation script `tools/research/stage86_verify_values_time.py`. No new device acquisition needed: continue by correlating param frame `0x3100` and ADC frame sample counters in existing PCAPNG if sessions match. Do not publish raw captures; no device connection; stable v0.3.40 unchanged.