# Stage 65 — original MVKView alarm-cell constructor (2026-10-28)

Source: original IDR `_Unit125.pas` and `_Unit128.pas`. Verified 14/14 static anchors, no device access.

At `0x00805178` MVKView constructs a `TMvkCellList` per ADC N=0..7, setting `AddrOffset = 0x2000 + N*0x200`, `AddrLimit=0x200`, and mapping `Data` to the corresponding live result-buffer region. In a loop j=0..7 it adds **three cells per control slot**:

- `AlarmValue`: relative register `0x130+8*j` (current float32);
- `AlarmState`: relative `0x132+8*j` (zone from state uint32; converter from `0x008025F8`);
- `AlarmAlert`: **same relative register `0x132+8*j`** (event bits from same uint32; converter from `0x00802664`).

The third cell does not read another register. The title labels are constructed from localized `xAlarm0..7`, `AlarmValue`, `AlarmState`, `AlarmAlert`. The form constructor at `_Unit128.pas:0x008443F7` invokes `0x00805178` in a loop for all eight ADCs. The `AlarmState` converter refers to 11 options and `AlarmAlert` to 3; full code-to-string table requires further extraction.

This explains the manufacturer protocol v1.0.39 status word format. **Unresolved:** where actual control configuration identifies which of the 144 calculation parameters each slot refers to. The alarm presentation list does not encode that selection. Next inspect constructor `0x00803FB4` and actual config retrieval.

Local complete archive: `MVKVIEW_STAGE65_ALARM_CELL_CONSTRUCTOR_20261028.zip`; includes REPORT_RU.md, verify.py, TEST_RESULTS.txt. Original firmware not examined; stable v0.3.40 unchanged.
