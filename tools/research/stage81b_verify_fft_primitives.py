#!/usr/bin/env python3
"""Offline verification of Stage81b original Delphi IDR. No network access."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument("unit115",type=Path);a=p.parse_args()
s=a.unit115.read_text(errors="replace")
parts={"fft":s.rsplit("//007D1FE8\n",1)[1].split("//007D2164\n",1)[0],
"conversion":s.rsplit("//007D2164\n",1)[1].split("//007D21A8\n",1)[0],
"window":s.split("//008C1064\n",1)[1]}
checks={"fft":["TDSXFastFourier.Create","TDSXFastFourier.SetNumSamples","TDSXFastFourier.fft","gvar_0096DA48","007D2044    mov         eax,40000","007D209B    fld","007D20A6    fld"],
"conversion":["159,154943091895","007D216A    mov         dword ptr [edx],eax","007D2184    fmul        dword ptr [ebp+8]","007D2187    fmul        st,st(0)"],
"window":["6,28318530717959","262144:Single","call        Cos","call        Sqrt","008C10C1    cmp         esi,40000"]}
fail=[(k,m) for k,ms in checks.items() for m in ms if m not in parts[k]]
print("PASS" if not fail else "FAIL",sum(map(len,checks.values()))-len(fail),"/",sum(map(len,checks.values())),fail)
raise SystemExit(bool(fail))
