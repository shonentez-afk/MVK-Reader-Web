#!/usr/bin/env python3
"""Stage 78: offline TABLE export check. Pass path to _Unit128.pas and TABLE files directory."""
from pathlib import Path
from collections import Counter
import sys
src=Path(sys.argv[1]).read_text(errors='replace')
anchors=['procedure Tmvkform.bWriteTableClick','0084E074','0084E0FE    call        @RewritText',"84E868;'sep=|'",'0084E209    call        TCheckListBox.GetChecked','0084E2C1    call        TMvkCellList.GetTitle','0084E319    call        TMvkCellList.GetValueText','0084E3AE    call        TMvkCellList.GetTitle','0084E409    call        TMvkCellList.GetValueText','0084E49E','0084E57E    call        TMvkCellList.GetMaxCells','0084E5FB    call        TMvkCellList.GetValueText','0084E6CD    call        @Close','errCannotWriteFile']
assert all(x in src for x in anchors)
files=sorted(Path(sys.argv[2]).glob('TABLE-*.csv'))
assert files
profiles=Counter()
for path in files:
 lines=path.read_text(encoding='cp1251',errors='replace').splitlines()
 assert lines[0]=='sep=|' and len(lines)==40,path
 profiles[sum(v.startswith('АЦП ') for v in lines[1].split('|'))]+=1
print('PASS',len(anchors),'static anchors;',len(files),'TABLE CSV; channels distribution',dict(profiles))
