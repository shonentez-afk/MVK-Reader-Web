#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects')
a=(root/'_Unit128.pas').read_text(errors='replace');b=(root/'_Unit125.pas').read_text(errors='replace')
for x in ['0084A5A8','0084A68A','0084A71F','0084A7B4','0084A7E6']:assert x in a,x
for x in ['00807C12','00807A40','00807A8E','00807F78','00808054','008080CA']:assert x in b,x
print('PASS 11/11 core anchors; compact check, full 17-anchor script in local Stage71 ZIP')
