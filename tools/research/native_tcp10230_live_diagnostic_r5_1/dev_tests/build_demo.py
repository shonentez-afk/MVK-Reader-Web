#!/usr/bin/env python3
"""Generate harmless synthetic frames for an offline diagnostic demonstration."""
from pathlib import Path
import struct

BASE = Path(__file__).resolve().parents[1]
ID,ADC,TACH,PARAM=1,0xFF800ADC,0xFF8001AC,0xFF800C0D

def samples(kind,ch,n,idx=0):
    return struct.pack('<7I',kind,28+4*n,0,idx,0,ch,65536) + struct.pack(f'<{n}f',*([.25]*n))
def param(blocks):
    msg=struct.pack('<II5I',PARAM,0,0,0,0,0,len(blocks))
    for address,data in blocks:
        assert len(data)%4==0
        msg+=struct.pack('<I',(len(data)//2<<16)|address)+data
    return msg[:4]+struct.pack('<I',len(msg))+msg[8:]

b=bytearray(struct.pack('<II',ID,264)+bytes(256))
b+=param([(0,bytes(32768))])
for ch in range(8):b+=samples(ADC,ch,256)
for ch in (8,9):b+=samples(TACH,ch,64)
blocks=[]
for ch in range(8):
    vals=[float(ch)+i/100.0 for i in range(144)]
    blocks.append((0x2000+ch*0x200,struct.pack('<144fI',*vals,16 if ch==0 else 0)))
b+=param(blocks)
b+=param([(0x1000,bytes(128))])  # 160-byte frame
b+=param([(0x3100,bytes(12))])   # VALUES event, 44-byte frame
assert len(b)==264+32800+8*1052+2*284+4700+160+44
p=BASE/'DEMO_SYNTHETIC.raw'
p.write_bytes(b)
print(p,len(b))
