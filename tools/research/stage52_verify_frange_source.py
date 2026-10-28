#!/usr/bin/env python3
"""Stage 52: check IDR origin of per-channel FRange without device access."""
from pathlib import Path
import sys
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path("_Unit125.pas")
s=p.read_text(errors="replace")
checks={
"channel config list":"00806971    mov         eax,dword ptr [eax+edx*4+1004]",
"parameter 0x0E":"00806978    mov         edx,0E",
"read float":"0080697D    call        TMvkCellList.GetFloatByAddr",
"tachometer fallback":"00806988    mov         dword ptr [esp],3F800000",
"zero fallback":"0080699E    mov         dword ptr [esp],3F800000",
"call coefficient getter":"0080863D    call        00806964",
"store FRange":"00808653    fstp        dword ptr [eax+4]",
"units parameter":"008069C8    mov         edx,10",
"read unit label":"008069D8    call        TMvkCellList.GetValueText",
"store unit string":"0080867F    add         eax,8",
}
for name,anchor in checks.items():
    ok=anchor in s
    print(("PASS" if ok else "FAIL"),name)
    if not ok:sys.exit(1)
print("PASS 10/10")
