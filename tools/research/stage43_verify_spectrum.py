#!/usr/bin/env python3
"""Static checks Stage 43 for exported IDR _Unit115.pas; no device access."""
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(encoding="utf-8",errors="replace")
anchors={
"GetSpectrum":"007D13D4",
"FFT length limit":"007D1404    cmp         eax,40000",
"Mean removal call":"007D14B3    call        007D2344",
"Mean subtraction":"007D2387    fsub",
"Window multiplication":"007D2065    fmul",
"FFT invocation":"007D2083    call        TDSXFastFourier.fft",
"Power calculation":"007D20AA    fmul",
"Amplitude sqrt":"007D168F    call        Sqrt",
"Sample rate read":"007D1512    mov         eax,dword ptr [eax+18]"
}
for name,marker in anchors.items():
    assert marker in s, f"Missing {name}: {marker}"
    print("PASS",name)
print("PASS 9/9 static IDR anchors")
