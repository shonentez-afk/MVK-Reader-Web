#!/usr/bin/env python3
"""Stage 65 offline address anchors of MVKView alarm cell construction."""
from pathlib import Path
import sys
base=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse/idr_project/Projects")
s=(base/"_Unit125.pas").read_text(errors="replace")
a=(base/"_Unit128.pas").read_text(errors="replace")
checks={
"create list":"008051A4    call        TMvkCellList.Create" in s,
"base address":"008051BF    add         eax,2000" in s,
"address range":"008051B3    mov         dword ptr [esi+14],200" in s,
"data pointer":"008051CC    mov         dword ptr [esi+0C],eax" in s,
"8 slots":"008052E6    cmp         ebx,8" in s,
"slot offset":"00805234    add         ecx,130" in s,
"add value":"0080523C    call        TMvkCellList.Add" in s,
"state address":"0080527E    add         eax,132" in s,
"add state":"0080528E    call        TMvkCellList.Add" in s,
"alert address":"008052D0    add         eax,132" in s,
"add alert":"008052E0    call        TMvkCellList.Add" in s,
"zone converter":"00805245    call        008025F8" in s,
"event converter":"00805297    call        00802664" in s,
"form uses constructor":"008443F7    call        00805178" in a,
}
for k,v in checks.items():
 print(("PASS" if v else "FAIL"),k)
assert all(checks.values())
print("PASS 14/14")
