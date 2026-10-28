#!/usr/bin/env python3
"""Stage 49 offline anchor checks; requires IDR export and NumPy only for BIN sample tests."""
from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("mvkview_reverse/idr_project/Projects")
s=(root/"_Unit115.pas").read_text(errors="replace")
r=(root/"_Unit125.pas").read_text(errors="replace")
checks={
 "FRange_init_one":"007D0A61    mov         dword ptr [esi+4],3F800000" in s,
 "TCP_apply_true":"00808284    mov         cl,1" in r and "0080828C    call        TMvkChannelStorage.ProcessBufferChunk" in r,
 "ProcessBufferChunk_times_FRange":"007D23D5    fmul        dword ptr [ebx+4]" in s,
 "GetSpectrum_get_signal_scaled_flag":"007D149A    push        1" in s,
 "GetSpectrum_input_div_FRange":"007D22C8    fdiv        dword ptr [ebx+4]" in s,
 "GetSpectrum_three_linear_output_scales":all(x in s for x in ["007D1667    fmul","007D16F1    fmul","007D17B0    fmul"]),
 "GetSpectrum_remove_mean":"007D14B3    call        007D2344" in s,
 "byte_path_divide_255":"007D2321    fdiv        dword ptr ds:[7D2340]" in s,
}
for key,ok in checks.items(): print(("PASS" if ok else "FAIL"),key)
assert all(checks.values())
print("PASS 8/8 IDR static anchors")
