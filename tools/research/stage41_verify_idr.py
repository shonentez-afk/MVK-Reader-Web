#!/usr/bin/env python3
"""Stage 41: offline verification of key address anchors in exported IDR Pascal."""
from pathlib import Path
import csv,sys,re
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("Projects")
checks=[
("_Unit125.pas","00808229","ReadStream"),
("_Unit125.pas","00808238","cmp"),
("_Unit125.pas","00808244","FreezeUpdate"),
("_Unit125.pas","0080828C","ProcessBufferChunk"),
("_Unit115.pas","007D23D5","FRange"),
("_Unit115.pas","007D1404","40000"),
("_Unit115.pas","007D13D4","GetSpectrum"),
("_Unit128.pas","00848200","GetSpectrum"),
("_Unit128.pas","0084FB03","GetSpectrum"),
("_Unit128.pas","0084FAA7","GetSignal"),
("_Unit115.pas","008C1082","6,28318530717959"),
]
rows=[]
for fn,addr,context in checks:
    text=(root/fn).read_text(encoding="utf-8",errors="replace")
    line=next((l.strip() for l in text.splitlines() if re.search(r"\\b"+addr+r"\\b",l)),None)
    rows.append((fn,addr,context,bool(line),line or ""))
for row in rows:print("\t".join(map(str,row)))
if not all(r[3] for r in rows):sys.exit("Some anchor addresses missing")
print(f"PASS {len(rows)}/{len(rows)}")
