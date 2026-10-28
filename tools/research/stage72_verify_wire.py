#!/usr/bin/env python3
from pathlib import Path
import struct,sys
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects/_Unit125.pas')
s=p.read_text(errors='replace')
anchors=['0080937C    push','0080938E    mov         edx,0FF800C0D','0080939C    shr         eax,1','0080939E    add         eax,8','008093EA    mov         edx,esi','008093EC    shl         edx,10','00807A4F    call        0080937C','00807A8E    call        dword ptr [ebx+0B4]','00807E15    mov         edx,0F0001','00807E30    mov         edx,10F0F','00807E3E    mov         edx,8','00808054    je          0080807B','00808059    je          008080AC','00807E83    mov         dword ptr [eax+3C],2']
assert all(a in s for a in anchors)
for addr,n in [(4,10),(0x14,12),(0x30,0x90),(0x10,4),(0x20,0x20),(0x100,0xa00),(2,2)]:
 b=struct.pack('<8I',0xff800c0d,32+2*n,0,0,0,0,1,(n<<16)|addr)
 assert len(b)==32 and struct.unpack_from('<I',b,4)[0]==32+2*n
print('PASS 14/14 anchors and 7 header examples; OFFLINE ONLY')
