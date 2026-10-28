#!/usr/bin/env python3
"""Read-only IDR static anchor check for archive FRange selection."""
from pathlib import Path
import sys
src=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse/idr_project/Projects/_Unit128.pas")
s=src.read_text(errors="replace")
anchors=["InternalChannelGain","DefaultConfig.txt","00846237","0084623C","008463EA","008463F4","008464E5","008464FF","00846504","0084655E"]
for a in anchors:
    ok=a in s
    print("PASS" if ok else "FAIL",a)
    if not ok:sys.exit(1)
print("PASS",len(anchors),"anchors; this does not replace full behavioral testing")
