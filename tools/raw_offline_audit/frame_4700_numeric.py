#!/usr/bin/env python3
"""Inspect saved MVK 4700-byte frames, offline only; no sockets."""
import argparse
import collections
import json
import struct
from pathlib import Path

def inspect(filename):
    payload=Path(filename).read_bytes()
    pos=payload.find(bytes.fromhex("dc0a80ff"))
    if pos<0: raise ValueError("ADC marker not found")
    frames=[]
    while pos<len(payload):
        if pos+8>len(payload): raise ValueError("Truncated frame")
        marker,length=struct.unpack_from("<II",payload,pos)
        if length<8 or pos+length>len(payload): raise ValueError("Invalid frame")
        if marker==0xff800c0d and length==4700:
            frames.append(payload[pos:pos+length])
        pos+=length
    if not frames: raise ValueError("No 4700-byte frames")
    counters=[struct.unpack_from("<I",f,20)[0] for f in frames]
    values=[struct.unpack_from("<1167f",f,32) for f in frames]
    return dict(file=Path(filename).name,frames=len(frames),
        size=4700,float32_per_frame=1167,
        counter_deltas=dict(collections.Counter(
          (b-a)&0xffffffff for a,b in zip(counters,counters[1:]))),
        zero_at_all_frames=sum(all(v[i]==0 for v in values) for i in range(1167)),
        first_16=list(values[0][:16]),last_16=list(values[0][-16:]))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw",nargs="+")
    p.add_argument("--out")
    a=p.parse_args()
    report=json.dumps([inspect(f) for f in a.raw],indent=2,ensure_ascii=False)
    print(report)
    if a.out: Path(a.out).write_text(report,encoding="utf-8")
if __name__=="__main__": main()
