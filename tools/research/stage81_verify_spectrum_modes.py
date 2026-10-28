#!/usr/bin/env python3
"""Stage 81 offline IDR structural verification; never connects to devices."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("unit115",type=Path)
a=p.parse_args()
s=a.unit115.read_text(errors="replace")
f=s[s.index("function TMvkChannelStorage.GetSpectrum(var Params"):s.index("//007D193D",s.index("function TMvkChannelStorage.GetSpectrum(var Params"))]
markers={
"limit_262144":"007D1404    cmp         eax,40000",
"ring_input":"007D14A5    call        007D2228",
"pre_transform":"007D1546    call        007D1FE8",
"half_bins":"007D151B    shr         eax,1",
"sample_rate":"007D1512    mov         eax,dword ptr [eax+18]",
"pre_zero":"007D15B5    mov         dword ptr [eax+esi*4],edx",
"mode_switch":"007D15BC    mov         eax,dword ptr [ebx+18]",
"mode0_log":"007D15F2    call        00447DB8",
"mode0_db_mult":"007D162C    fmul        dword ptr ds:[7D1994];10:Single",
"mode0_floor":"007D163E    mov         dword ptr [eax+esi*4],0C3340000",
"mode1_sqrt":"007D168F    call        Sqrt",
"mode2_preprocess":"007D16D7    call        007D2164",
"mode3_preprocess_1":"007D1761    call        007D2164",
"mode3_preprocess_2":"007D1796    call        007D2164",
"gain_mode1":"007D1667    fmul        dword ptr [edx+4]",
"gain_mode2":"007D16F1    fmul        dword ptr [edx+4]",
"gain_mode3":"007D17B0    fmul        dword ptr [edx+4]",
}
missing=[k for k,v in markers.items() if v not in f]
for k in markers: print(("FAIL" if k in missing else "PASS"),k)
print(len(markers)-len(missing),"/",len(markers))
raise SystemExit(bool(missing))
