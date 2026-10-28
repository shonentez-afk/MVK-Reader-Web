#!/usr/bin/env python3
"""Stage 51: verify IDR pointer aliasing and same-buffer BIN write (offline)."""
from pathlib import Path
import struct
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse/idr_project/Projects")
a=(root/"_Unit115.pas").read_text(errors="replace")
b=(root/"_Unit125.pas").read_text(errors="replace")
checks={
"alloc returns ring pointer":"007D1B40    mov         eax,dword ptr [ebx+34]" in a and "007D1BF3    mov         eax,edi" in a,
"TmpStream aliases ring":"008081F6    call        TMvkChannelStorage.AllocBufferChunk" in b and "00808203    call        008020A8" in b,
"pointer assignment not copy":"008020A8    mov         dword ptr [eax+4],edx" in b,
"TCP reads into aliased memory":"00808229    call        dword ptr [ebx+0D0];TIdIOHandler.ReadStream" in b,
"float gets FRange in place":"007D23D5    fmul        dword ptr [ebx+4]" in a and "007D23E1    fstp        dword ptr [ebp+edi*4]" in a,
"process precedes BIN write":b.index("0080828C    call        TMvkChannelStorage.ProcessBufferChunk") < b.index("008082D6    mov         edx,dword ptr [edx+4]"),
"writer uses same FMemory":"008082D6    mov         edx,dword ptr [edx+4];TRecordMemoryStream.FMemory:Pointer" in b,
"FFT reads by dividing range":"007D22C8    fdiv        dword ptr [ebx+4]" in a
}
for name,ok in checks.items():print(("PASS" if ok else "FAIL"),name)
assert all(checks.values())
buf=bytearray(struct.pack("<3f",0.125,-0.25,0.5))
ring=memoryview(buf);tmp=memoryview(buf)
for i in range(3):
    struct.pack_into("<f",ring,i*4,struct.unpack_from("<f",ring,i*4)[0]*510.)
assert [round(struct.unpack_from("<f",tmp,i*4)[0],3) for i in range(3)] == [63.75,-127.5,255.]
print("PASS 8/8; alias test passed")
