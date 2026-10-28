#!/usr/bin/env python3
from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else 'mvkview_reverse/idr_project/Projects/_Unit125.pas').read_text(errors='replace')
anchors=['00803FF4    mov         edi,31','00803FFE    mov         esi,8','0080415A    add         edi,3','00804167    add         edi,8','0080416D    cmp         dword ptr [ebp-14],3','00804177    mov         edi,2','0080417C    mov         esi,2B','008041CE    call        TMvkAdvancedCell.Add','00804277    call        TMvkCellList.Add']
assert all(x in s for x in anchors)
groups=[[49+32*m+3*g+k for g in range(8) for k in range(3)] for m in range(3)]
bands=list(range(2,45))
all_ids=bands+sum(groups,[])
assert len(all_ids)==115 and len(set(all_ids))==115
print('PASS 9/9 anchors; 115 distinct IDs; groups 49–72,81–104,113–136 and bands 2–44')
