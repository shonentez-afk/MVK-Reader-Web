# Stage94 — original MVKView IDR versus supplied mvk_tcp_reader_v2(1).py

Read original `_Unit125.pas` from the user-provided `Projects.7z`, supplied Python reader, and existing GitHub decoder/report assets. **The original MVKView source is not completely reverse engineered.**

Confirmed in original IDR: TCP port 0x27F6=10230 (`0x00807C12`); a structured record descriptor is low16=register address (`0x00808464`) / high16=word count (`0x0080846F`); nonzero even word count, address+count <=0x4000; block saved at byte offset address*2 to a `TRecordMemoryStream` (`0x00808544..0x0080856D`); calculation UI updates by `sub_00805D08` (`0x0080857C..0x0080859A`); VALUES export on 0x3100 (`0x008085A5..0x008085BD`). Reader's packet framing and `records()` agree with these core rules. ADC type FF800ADC, length 1052, 256 float32, tacho FF8001AC, length 284 agree with previous archived frame tests.

**Material missing in the supplied reader**: it returns structured tuples without maintaining original register-image, it discards them in `listen()` except counts, no connection to `decode_4700.py` and no calculated-values UI, no scale factor application for saved BIN (unlike original MVKView BIN). Original program tasks, protocol live handshake/ACK, error modes and firmware DSP coefficients remain incompletely proven. Do NOT claim full MVKView equivalence or proven passive live socket capability.

Ran five offline synthetic tests (split TCP frame, ADC header/payload, structured record, rejecting odd word count, concatenated frames): 5/5 PASS. Script/results/full comparison provided locally as `stage94_source_parity.zip`; industrial captures and original decompiled source not committed. Stable v0.3.40 untouched; no devices contacted.
