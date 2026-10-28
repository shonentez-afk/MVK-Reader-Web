#!/usr/bin/env python3
"""Stage80 offline IDR anchors: channel storage signal path. No device access."""
from pathlib import Path
import argparse
ap=argparse.ArgumentParser();ap.add_argument("unit115",type=Path)
a=ap.parse_args()
s=a.unit115.read_text(errors="replace")
anchors={
"constructor":"constructor TMvkChannelStorage.Create",
"get_signal":"function TMvkChannelStorage.GetSignal",
"availability":"007D0C51    call        TMvkChannelStorage.CheckDataAvailability",
"read_from_ring":"007D0CD6    call        007D2228",
"optional_filter":"007D0CF0    call        007D2344",
"envelope_length":"007D0C95    call        TMvkChannelStorage.GetAdjustedEnvelopeLength",
"envelope_ops":"007D0D0D    call        007D1C48",
"envelope_ops_2":"007D0D26    call        007D1E70",
"rate_out":"007D0D4F    mov         eax,dword ptr [eax+18]",
"rms":"007D0DCA    call        Sqrt",
"envelope_gain":"007D0D8F    fmul        dword ptr [esi+4]",
"byte_normalize":"007D2321    fdiv        dword ptr ds:[7D2340]",
"float_divide_gain":"007D22C8    fdiv        dword ptr [ebx+4]",
"missing_fill":"007D2284    call        @FillChar",
}
for label,marker in anchors.items():print(("PASS" if marker in s else "FAIL"),label)
print(sum(x in s for x in anchors.values()),"/",len(anchors))
raise SystemExit(not all(marker in s for marker in anchors.values()))
