#!/usr/bin/env python3
"""Stage81c offline IDR check, original _Unit115.pas required."""
import argparse
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument("unit115",type=Path);s=ap.parse_args().unit115.read_text(errors="replace")
w=s.split("//008C1064\n",1)[1]
f=s.rsplit("//007D1FE8\n",1)[1].split("//007D2164\n",1)[0]
i=s.rsplit("//007D2164\n",1)[1].split("//007D21A8\n",1)[0]
checks={
"periodic_window":all(x in w for x in ["008C1097    call        Cos","008C109C    fld1","008C109E    fsubrp","008C10B8    fdivrp"]),
"sqrt_1_5":all(x in w for x in ["008C10A4    push        3FFF","008C10A9    push        0C0000000","008C10AE    push        0","008C10B0    call        Sqrt"]),
"window_table_262144":"008C10C1    cmp         esi,40000" in w,
"fft_window_stride":all(x in f for x in ["007D2044    mov         eax,40000","007D204B    div         eax,dword ptr [ebp-4]","007D2065    fmul        dword ptr [esi*4+96DA48]"]),
"fft_power":all(x in f for x in ["007D209E    fmul        st,st(0)","007D20AA    fmul        st,st(0)","007D20AC    faddp"]),
"frequency_transform":all(x in i for x in ["159,154943091895","007D2179    fild","007D2182    fdivrp","007D2184    fmul","007D2187    fmul","007D216A    mov"])}
for name,ok in checks.items():print("PASS" if ok else "FAIL",name)
print(sum(checks.values()),"/",len(checks))
raise SystemExit(not all(checks.values()))
