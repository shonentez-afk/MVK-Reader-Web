"""Inspect paired numeric fields in MVK AUX160 frames from a stored RAW file."""
import argparse
import struct
from pathlib import Path
from collections import defaultdict

MAGIC = bytes.fromhex("dc0a80ff")
IDS = {0x00402130 + i*512: i+1 for i in range(8)}
OFFSETS = (32,40,48,56,64,72,80,88,144)

def audit(path):
    data=Path(path).read_bytes()
    pos=data.find(MAGIC)
    if pos<0: raise ValueError("No ADC marker")
    channels=defaultdict(list)
    while pos+8<=len(data):
        marker,size=struct.unpack_from("<II",data,pos)
        if size<8 or pos+size>len(data): raise ValueError("Bad frame boundary")
        if marker==0xff800c0d and size==160:
            cid=struct.unpack_from("<I",data,pos+28)[0]
            if cid in IDS:
                channels[IDS[cid]].append({str(offset):struct.unpack_from("<f",data,pos+offset)[0] for offset in OFFSETS})
        pos+=size
    print(Path(path).name)
    for channel in sorted(channels):
        rows=channels[channel]
        print("ADC",channel,"records",len(rows))
        for off in OFFSETS:
            values=[r[str(off)] for r in rows]
            print(" ",off,"first",values[0],"last",values[-1],"min",min(values),"max",max(values))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("raw",nargs="+")
    for name in ap.parse_args().raw:audit(name)
