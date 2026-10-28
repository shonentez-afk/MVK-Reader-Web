#!/usr/bin/env python3
"""Stage 48 static IDR x87 instruction and numeric conversion check."""
import math
from pathlib import Path
import sys

source=Path(sys.argv[1]) if len(sys.argv)>1 else Path("_Unit115.pas")
s=source.read_text(encoding="utf-8",errors="replace")
anchors=[
"007D2179    fild",
"007D217C    fld",
"007D2182    fdivrp",
"007D2184    fmul",
"007D2187    fmul",
"007D2189    fmul",
"007D16D7    call",
"007D1761    call",
"007D1796    call",
"007D22C8    fdiv",
"007D1667    fmul",
]
for a in anchors:
    assert a in s,a
C=159.154943091895
for fs,n,k in ((65536,65536,100),(32768,32768,25),(512,512,5)):
    actual=(C/k)*(n/fs)
    expected=1000/(2*math.pi*(k*fs/n))
    assert math.isclose(actual,expected,rel_tol=1e-13)
    print(f"f={k*fs/n} K={actual:.12g}")
print("PASS 11/11 anchors, 3/3 numeric cases")
