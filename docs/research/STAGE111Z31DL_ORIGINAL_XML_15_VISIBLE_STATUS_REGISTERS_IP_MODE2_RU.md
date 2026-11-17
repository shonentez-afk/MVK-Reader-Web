# Stage111Z31DJ-DL: original Device/Address, fifteen visible PageStatus fields, passive Core/Qt

Date: 2026-11-17. Source code commit: `c459b5b8131c185e4a4aafefcaa4f7db23dd0c07` (CI must be checked for exactly this SHA). No real-device send operation has been authorized or performed in this stage.

## Exact user-supplied original XML

The private XML `mvkview.exe(1).xml` is CP1251, `<Configuration><Device><Address>192.168.0.30</Address>`; `UseCustomName=FALSE`; `Library/Path=D:\\mvkview-1.0.47\\Data\\`; `UseTsxml=TRUE`; `UseFolderPrefix=FALSE`; `Advanced/DrawInterval=20`; `Window/PixelsPerInch=144`. No private XML bytes are committed. DrawInterval=20 is GUI timer ms, **not** hardware sample rate.

Private `Projects.7z/_Unit128.pas`: at 0084ED8B `TJvCustomAppStorage.ReadString('Device\\Address','192.168.0.30')` to the visible `edIpAddr`; at 0084F270..0084F28C read `edIpAddr.Text` then `WriteString('Device\\Address')`; on Measure `00846D91..00846DD1` passes the CURRENT edit text to `TMVKThread.Create`. `_Unit125.pas 00806105..0080611A` places the passed string in `TMVKThread.IPAddress`, with fallback `192.168.0.30` if absent. The active network interface IP is separate from this remote device IP.

Compatible implementation `original_device_ip_settings.py`: read existing vendor executable-adjacent XML without modifying it, otherwise use source default; read/write the compatible-only user profile override in `LOCALAPPDATA/MVKViewCompatible/device.xml`. Reject malformed/unsafe IPv4 and unsafe or oversized source XML; save operator override atomically. `OriginalStartController.edIpAddr` uses this value; a **separately approved** Native capture dialog device IP is reflected back into the source edit. The selected wired local IP remains the explicit Go `-local-ip` argument, **not** a replacement for `-ip`; no port scan, no additional client.

## Fifteen displayed source fields vs fourteen internal StatusCells

Private `Projects.7z/_Unit125.pas` function `008026B0` creates `TMvkCellList` with `AddrOffset=0x1000`, `AddrLimit=0x200`. The following original relative Add addresses were directly rechecked from the PAS disassembly:

| Original UI field | Relative Add | Absolute 16-bit register word |
|---|---:|---:|
| StatusSerial | 0x00 | 0x1000 |
| StatusVersion | 0x04 | 0x1004 |
| StatusSystemError | 0x06 | 0x1006 |
| StatusTime | 0x08 | 0x1008 |
| StatusSDSize | 0x0A | 0x100A |
| StatusMD5 | 0x0C | 0x100C |
| StatusState 1 | 0x14 | 0x1014 |
| StatusAlert 1 | 0x14 | 0x1014 |
| StatusState 2 | 0x16 | 0x1016 |
| StatusAlert 2 | 0x16 | 0x1016 |
| StatusCalcCounter | 0x24 | 0x1024 |
| StatusModbusCounter | 0x36 | 0x1036 |
| StatusModbusAddr | 0x3A | 0x103A |
| StatusModbusRegs | 0x3C | 0x103C |
| StatusModbusClients | 0x3E | 0x103E |

The 14 TMVKThread StatusCells source addresses are a **different** table; 0x1006 overlaps with the visible SystemError. Go `snapshotSourcePageStatusFields` reads only the receiver's already accepted RegisterImage, with two Valid halfwords per DWORD and eight per 16-byte MD5. Missing halfwords lead to `valid:false/raw_hex_le:null`, never a fictitious 0. The canonical array has 15 ordered items and the original exact addresses. Python validates exact order, source word width, pair-sharing at 0x1014 and 0x1016, and agreement of 0x1006 with the independent 14-cell SystemError. Qt existing PageStatus `tabStatus` gets real captured values through `connected_system_status` and the original four-grid workbench. Not-yet-verified specialised source enum/serial/firmware/Modbus formatters are represented by original RAW HEX, **not** invented human strings. Missing data remain '—'.

The original 15 PageStatus *modes* (system/alarms/three aggregated ADC values/eight bands/two TACH) are separate from these 15 *visible rows on the system mode*; do not confuse them.

## Current boundaries of the measurement chain

Source `bTaskConnectClick` (00848E78) -> Mode2 and page/pnMeasure visibility BEFORE TCP -> `edIpAddr.Text` -> `TMVKThread.Create` -> source initial mRate1Click(65536)/QueueCommand -> source Stage0/Stage1/Stage3, FIFO/ACK/DENIED/FreezeUpdate/retry. The core has an autonomous dry-run model. The actual Qt uses a single passive Go R6.1 client to remote device IPv4 and TCP/10230 only after operator consent; all original QueueCommand/SetRate writes remain **disabled**, so source hardware parity is **OPEN**.

Source full original Measure is **not fully recovered** until original command/ACK pairing, real automatic reconnect and numeric DSP/FFT/RPM + original byte-level export + same-device Win32/pixel comparisons have passed separate authorized acceptance. The 15 register addresses being source-verified does NOT certify all original formatted values. Real physical device was not connected during DJ-DL.

Tests: Go `TestOriginalPageStatusFifteenSourceRegisters`; Core `test_stage111z31dl_source_15_status_core.py`, `test_stage111z31dj_original_device_ip_xml.py`; actual Qt `test_stage111z31dl_qt_source_15_status.py` in Windows DPI100/150/native QPA CI. Test failures must be fixed before calling the Windows EXE accepted.

Private original PAS, IDP, SQLite, XML, raw PCAP/BIN/TSXML and screenshots must never be committed.
