#!/usr/bin/env python3
"""Stage81d: static offline FFT backend / log output verification. No network."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("unit115",type=Path)
s=p.parse_args().unit115.read_text(errors="replace")
checks={
"power2_check":"007CC1B7    mov         ecx,7CC390",
"bit_reverse":"007CC1F3    call        007CC17C",
"butterfly":"007CC2B4    fsubp       st(1),st",
"stage_doubling":"007CC36A    shl         dword ptr [ebp-0C],1",
"angle_sine":"007CC247    call        Sin",
"forward_sign":"007CC3F8    push        40C90FDB",
"inverse_sign":"007CC408    push        0C0C90FDB",
"inverse_div_n":"007CC425    fdivr       dword ptr [edx+eax*8]",
"power_magnitude":"007D20AC    faddp       st(1),st",
"log_nbins":"007D15F2    call        00447DB8",
"log_nbins_twice":"007D15F7    fmul        dword ptr ds:[7D1990];2:Single",
"log_power":"007D1624    call        00447DB8",
"log_subtract":"007D1629    fsub        dword ptr [ebp-18]",
"log_10":"007D162C    fmul        dword ptr ds:[7D1994];10:Single",
"log_floor":"007D163E    mov         dword ptr [eax+esi*4],0C3340000",
}
missing=[k for k,v in checks.items() if v not in s]
for k in checks:print("PASS" if k not in missing else "FAIL",k)
print(len(checks)-len(missing),"/",len(checks))
raise SystemExit(bool(missing))
