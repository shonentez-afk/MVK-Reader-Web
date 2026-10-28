#!/usr/bin/env python3
"""Stage 50 offline static anchors for original IDR Pascal export."""
from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse/idr_project/Projects")
a=(root/"_Unit115.pas").read_text(errors="replace")
b=(root/"_Unit125.pas").read_text(errors="replace")
checks={
    "recv_tmpstream": "00808229    call" in b and "TIdIOHandler.ReadStream" in b,
    "copy_to_ring": "00808203    call        008020A8" in b,
    "process_range": "0080828C    call        TMvkChannelStorage.ProcessBufferChunk" in b and "007D23D5    fmul" in a,
    "write_from_tmp": "008082D6    mov         edx,dword ptr [edx+4];TRecordMemoryStream.FMemory:Pointer" in b and "008082DE    call        dword ptr [ebx+10]" in b,
    "fft_divides_range": "007D22C8    fdiv" in a,
    "fft_multiplies_range": "007D1667    fmul" in a,
}
for name,ok in checks.items(): print(("PASS" if ok else "FAIL"),name)
if not all(checks.values()):raise SystemExit(1)
print("PASS 6/6 static IDR anchors")
