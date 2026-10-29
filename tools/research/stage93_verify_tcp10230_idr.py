#!/usr/bin/env python3
"""Offline original-IDR verification for recovered TCP/10230 path."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("unit125",type=Path)
s=p.parse_args().unit125.read_text(errors="replace")
checks={
"tcp10230":["00807C12    mov         dx,27F6","00807C18    call"],
"frame_header":["0080841B    xor         edx,edx","00808461    mov         eax,dword ptr [ebp-20]"],
"address_and_length":["00808464    and         eax,0FFFF","0080846F    shr         eax,10"],
"bounds":["008084EB    cmp         eax,4000"],
"store_registers":["00808544    mov         eax,dword ptr [ebp-30]","0080856D    call"],
"values_trigger":["008085A5    cmp         dword ptr [ebp-30],3100","008085BD    call"],
"adc_path":["0080828C    call        TMvkChannelStorage.ProcessBufferChunk"],
}
ok=0
for k,v in checks.items():
 good=all(w in s for w in v);print("PASS" if good else "FAIL",k);ok+=good
print(f"{ok}/{len(checks)}")
raise SystemExit(ok!=len(checks))
