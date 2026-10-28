#!/usr/bin/env python3
from pathlib import Path
import sys
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects/_Unit115.pas')
s=p.read_text(errors='replace')
checks={'store_id':'007D059E    mov         dword ptr [ebx],edi','append_entry':'007D05C8    call        TList.Add','get_id':'007D072D    mov         eax,dword ptr [eax]','search_id':'007D075C    cmp         ebp,dword ptr [eax]','not_found':'007D073D    mov         dword ptr [esp],0FFFFFFFF','text_getdword':'007CF4EF    call        TMvkCellList.GetDword','text_title_by_id':'007CF51A    call        TMvkAdvancedCell.GetTitleByID','title_search':'007D083A    call        TMvkAdvancedCell.GetIndexByID','unknown_text':'007D0845    push        7D0944','text_branch':'007CF4DC    cmp         dword ptr [ebx+4],0A'}
for name,anchor in checks.items():
 ok=anchor in s
 print('PASS' if ok else 'FAIL',name)
 if not ok:sys.exit(1)
print('10/10 IDR anchors')
