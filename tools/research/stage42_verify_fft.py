#!/usr/bin/env python3
"""Reproducible static anchor check for Stage 42 (requires exported IDR _Unit115.pas)."""
from pathlib import Path
import sys
src = Path(sys.argv[1]) if len(sys.argv)>1 else Path("_Unit115.pas")
text = src.read_text(encoding="utf-8",errors="replace")
anchors = {
 "forward_fft": "procedure TDSXFastFourier.fft;",
 "inverse_fft": "procedure TDSXFastFourier.ifft;",
 "local_spectrum": "function TMvkChannelStorage.GetSpectrum",
 "common_core": "007CC198",
 "forward_address": "007CC3F8",
 "inverse_address": "007CC404",
}
failed=[]
for key,value in anchors.items():
 found=value.casefold() in text.casefold()
 print(f"{'PASS' if found else 'FAIL'} {key}: {value}")
 if not found:failed.append(key)
if failed:sys.exit("Missing IDR anchors: "+",".join(failed))
print("PASS 6/6; static identification only, not a numerical FFT verification")
