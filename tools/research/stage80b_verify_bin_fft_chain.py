#!/usr/bin/env python3
"""Offline Stage 80b anchor verification; original IDR required, no network."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("unit128", type=Path)
p.add_argument("unit115", type=Path)
a=p.parse_args()
u=a.unit128.read_text(errors="replace")
s=a.unit115.read_text(errors="replace")
checks={
"seek":"0084F951    call        dword ptr [edi+24];TStream.Seek" in u,
"invalidate":"0084F957    call        TMvkChannelStorage.InvalidateData" in u,
"allocate":"0084F969    call        TMvkChannelStorage.AllocBufferChunk" in u,
"file_read":"0084F97F    call        dword ptr [edi+0C];THandleStream.Read" in u,
"process":"0084F98F    call        TMvkChannelStorage.ProcessBufferChunk" in u,
"normalization_flag":"0084F982    movzx       ecx,byte ptr [ebx+0BDC]" in u,
"signal_ui":"00847FCF    call        TMvkChannelStorage.GetSignal" in u,
"spectrum_ui":"00848200    call        TMvkChannelStorage.GetSpectrum" in u,
"processed_gain":"007D23D5    fmul        dword ptr [ebx+4]" in s,
"rxpos":"007D23F4    mov         dword ptr [ebx+20],eax" in s,
"spectrum_start":"007D13D4    push        ebp" in s,
"fft_limit":"007D1404    cmp         eax,40000" in s,
"fft_input":"007D14A5    call        007D2228" in s,
"fft_filter":"007D14B3    call        007D2344" in s,
}
for k,v in checks.items():print(("PASS" if v else "FAIL"),k)
print(sum(checks.values()),"/",len(checks))
raise SystemExit(0 if all(checks.values()) else 1)
