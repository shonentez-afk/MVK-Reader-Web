#!/usr/bin/env python3
"""Stage79c: offline IDR structural checks for TSXML -> BIN open chain."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument("unit128",type=Path)
a=p.parse_args()
src=a.unit128.read_text(errors="replace")
start=src.index("//00846008")
end=src.index("00846793",start)+8
body=src[start:end]
checks={
 "tsxml_path":"0084605C" in body and "'.tsxml'" in body,
 "read_text":"008460BD    call        @ResetText" in body,
 "frequency":"ChannelFrequency" in body and "StrToInt" in body,
 "units":"846854;'Units'" in body,
 "type_byte_single":"8468D4;'Byte'" in body and "8468EC;'Single'" in body,
 "gain":"InternalChannelGain" in body and "StrToFloat" in body,
 "fallback_prompt":"queryDefaultFileParams" in body,
 "cancel_exception":"errOperationCanceled" in body,
 "channel_storage":"TMvkChannelStorage.Create" in body,
 "storage_init":"TMvkChannelStorage.InitParams" in body,
 "open_bin":"TFileStream.Create" in body,
 "size_to_samples":"008465CF" in body and "008465D9    call        @_lldiv" in body,
 "open_dialog_caller":"00846EB5    call        00846008" in src,
}
for key,passed in checks.items(): print(("PASS" if passed else "FAIL"),key)
print(sum(checks.values()),"/",len(checks))
raise SystemExit(0 if all(checks.values()) else 1)
