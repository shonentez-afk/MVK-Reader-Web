#!/usr/bin/env python3
"""Static IDR anchors for original VALUES CSV header and row writers."""
from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else 'mvkview_reverse/idr_project/Projects/_Unit125.pas').read_text(errors='replace')
anchors=['00806334    push',"806684;'sep=|", "8066A0;'xTime'", '00806469    call        TMvkCellList.GetTitle', '008064AD    call        TLanguage.localize','008066F0    push',"806924;'hh:nn:ss.zzz'",'008067EE    call        TMvkCellList.GetValueText','00806876    call        TMvkCellList.GetValueText','008085BD    call        008066F0','008085A5    cmp         dword ptr [ebp-30],3100','00806635    call        dword ptr [ebx+10]','008068DA    call        dword ptr [ebx+10]']
assert all(x in s for x in anchors)
print('PASS 13/13')
