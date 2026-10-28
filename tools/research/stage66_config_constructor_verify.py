#!/usr/bin/env python3
from pathlib import Path
import sys
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects/_Unit125.pas')
s=p.read_text(errors='replace')
anchors=['00803FB4','00804073','0080417C','008041FD','008041F0','00804494','00804272','008042AF','0080432F','008043C4','00804428','008042EC','00804378','00804489','AlarmBand','xParamOption']
for a in anchors:
 print(('PASS' if a in s else 'FAIL'),a)
assert all(a in s for a in anchors)
print('PASS 16/16')
