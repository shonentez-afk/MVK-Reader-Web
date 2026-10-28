#!/usr/bin/env python3
"""Stage 47 offline source-anchor checks (requires original IDR export)."""
from pathlib import Path
import sys, math
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse")
u=(root/"idr_project/Projects/_Unit115.pas").read_text(errors="replace")
v=(root/"idr_project/Projects/_Unit128.pas").read_text(errors="replace")
labels=(root/"LOCALIZATION_labels.md").read_text(errors="replace")
checks={
 "four localized labels":all("**popSpecTypeItem"+str(k)+"**" in labels for k in range(4)),
 "menu tag transfer":"0084C54A" in v and "TButton.FTag" in v,
 "four spectrum branches":"007D15C4" in u and "007D15D2" in u,
 "FRange output":"007D1667" in u,
 "one transform":"007D16D7" in u,
 "double transform":"007D1761" in u and "007D1796" in u,
 "input FRange division":"007D22C8" in u,
 "integrator constant":"159,154943091895" in u}
for name,passed in checks.items():print(("PASS" if passed else "FAIL"),name)
assert all(checks.values())
for hz in (5,25,100):
 a=2*math.pi/(1000*hz)
 b=1000/(2*math.pi*hz)
 print(f"frequency={hz} code_amp_factor={a:.12g} physical_mm_s_factor={b:.12g}")
print("PASS 8/8 source anchors; physical equivalence not established")
