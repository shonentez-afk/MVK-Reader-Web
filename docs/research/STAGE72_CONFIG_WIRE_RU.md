# Stage 72 — Original TCP/10230 configuration upload frame

Offline verified 14/14 static anchors from IDR `_Unit125.pas`, plus seven synthetic length cases. At 0x0080937C header is eight uint32 little-endian words `[0xFF800C0D,32+2*reg_count,0,0,0,0,1,(reg_count<<16)|start_address]`. Helper 0x00807A40 sends `2*reg_count` bytes from a memory-backed configuration buffer.

Task 3 blocks (address, registers): `(0x04,0x0A)`, `(0x14,0x0C)`, `(0x30,0x90)`; task 4 `(0x10,4)`, `(0x20,0x20)`; task 5 `(0x100,0xA00)`.

Then a separate 36-byte frame for `(address=0x02, count=2)` plus DWORD `0x000F0001` (save to flash), followed by 8-byte packet `[0x00010F0F,8]` (restart). Responses `0x00010FF0` and `0x00010FFF` correspond to success and denial. These are potentially disruptive commands: never send on production equipment without approval. **Exact acknowledgment per configuration block still unresolved**.

Local report and 14-anchor script: `MVKVIEW_STAGE72_CONFIG_WIRE_20261028.zip`. Original firmware not analyzed, stable v0.3.40 unchanged.