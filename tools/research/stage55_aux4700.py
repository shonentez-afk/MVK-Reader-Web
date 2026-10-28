#!/usr/bin/env python3
"""Stage 55 offline AUX4700 measurement inspection.
Requires local cap_parse.py and real PCAPNG; no device traffic.
"""
import collections,math,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cap_parse as cp
for path in sys.argv[1:]:
 for flow in cp.device_streams(path):
  for _,payload in flow["runs"]:
   frames,err=cp.scan_frames(payload)
   blocks=[cp.parse_aux4700(payload,off)[1] for off,t,size in frames if t==cp.MARK_AUX and size==4700]
   if not blocks:continue
   print(path,"src",flow["src"],"frames",len(frames),"AUX4700",len(blocks),"tail",err)
   for ch in range(8):
    ids={block[ch]["id"]&65535 for block in blocks}
    assert ids=={0x2000+ch*0x200}
    vals=[block[ch]["words"][47] for block in blocks]
    print(ch+1,len(vals),min(vals),max(vals))
