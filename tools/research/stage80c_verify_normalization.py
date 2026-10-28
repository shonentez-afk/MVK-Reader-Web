#!/usr/bin/env python3
"""Stage80c offline-only IDR normalization branch check."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('unit128', type=Path); p.add_argument('unit115',type=Path)
a=p.parse_args()
u=a.unit128.read_text(errors='replace')
s=a.unit115.read_text(errors='replace')
checks={
 'nonpositive_gain_branch': '008463EA    jae         0084651F' in u,
 'byte_gain_one': '008463F6    mov         dword ptr [ebp-2C],3F800000' in u,
 'fallback_defaults': "0084641B    mov         eax,dword ptr [ebp-328]" in u and "'DefaultConfig.txt'" in u,
 'fallback_gain_computation': '00846509    fdivr       dword ptr [ebp-338]' in u,
 'flag_set': '00846516    mov         byte ptr [eax+0BDC],1' in u,
 'flag_clear': '00846522    mov         byte ptr [eax+0BDC],0' in u,
 'flag_pass': '0084F982    movzx       ecx,byte ptr [ebx+0BDC]' in u,
 'size_divide_four': '007D23B7    shr         esi,2' in s,
 'conditional_apply': '007D23BA    test        cl,cl' in s,
 'multiply_range': '007D23D5    fmul        dword ptr [ebx+4]' in s,
 'advance_pos': '007D23F4    mov         dword ptr [ebx+20],eax' in s,
}
for k,v in checks.items():print(('PASS' if v else 'FAIL'),k)
print(sum(checks.values()),'/',len(checks))
raise SystemExit(0 if all(checks.values()) else 1)
