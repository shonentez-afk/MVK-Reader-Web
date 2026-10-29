#!/usr/bin/env python3
"""Original IDR static assertion: VALUES timestamp origin; no instrument I/O."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('unit125',type=Path)
s=p.parse_args().unit125.read_text(errors='replace')
checks={
'param_3100_triggers_values': ['008085A5    cmp         dword ptr [ebp-30],3100','008085BD    call        008066F0'],
'values_current_clock': ['0080672B    call        0042F594',"00806743    mov         eax,806924;'hh:nn:ss.zzz'"],
'separate_values_start': ["00809880    push        809B68;'VALUES-'",'0080997E    call        0042F594','00809986    fstp        qword ptr [eax+404E8]'],
'separate_bin_start': ['008096B5    call        0042F594','008096BD    fstp        qword ptr [eax+404E0]'],
'xml_current_clock': ['00806B95    call        0042F594',"00806BAD    mov         eax,807244;"],
}
errors=[key for key,items in checks.items() if not all(i in s for i in items)]
for key in checks:print('FAIL' if key in errors else 'PASS',key)
print(len(checks)-len(errors),'/',len(checks))
raise SystemExit(bool(errors))
