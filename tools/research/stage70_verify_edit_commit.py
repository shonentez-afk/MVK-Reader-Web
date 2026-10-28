#!/usr/bin/env python3
from pathlib import Path
import sys
base=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects')
s=(base/'_Unit115.pas').read_text(errors='replace');t=(base/'_Unit128.pas').read_text(errors='replace')
checks=[(t,'00849038'),(t,'008407CC    call        TMvkAdvancedCell.GetIndexByID'),(t,'00840318'),(t,'008403C1    call        TMvkAdvancedCell.GetID'),(t,'008403D3    call        TMvkCellList.InputValue'),(s,'007CFA2C'),(s,'007CFA90    cmp         dword ptr [eax+4],0A'),(s,'007CFAC4    mov         dword ptr [eax],edi'),(t,'0084A5A8'),(t,'0084A5DD    cmp         dword ptr [eax+0BE0],0')]
for src,needle in checks:
 assert needle in src,needle
print('PASS 10/10 static anchors')
