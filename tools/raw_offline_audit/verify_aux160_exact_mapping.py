"""Offline comparison of AUX160 against preceding AUX4700 frame.
Run: python verify_aux160_exact_mapping.py capture.raw
"""
import struct
import sys
from pathlib import Path

EXPECTED = {32: 55, 48: 66, 64: 47, 80: 46}
CH_IDS = {0x00402130 + 512*c: c for c in range(8)}

def check(path):
    d = Path(path).read_bytes()
    p = d.find(bytes.fromhex("dc0a80ff"))
    if p < 0:
        raise ValueError("ADC frame not found")
    source, target = [], []
    while p + 8 <= len(d):
        magic, n = struct.unpack_from("<II", d, p)
        if n < 8 or p+n > len(d):
            raise ValueError("Invalid frame at byte %d" % p)
        if magic == 0xff800c0d and n == 160:
            ident = struct.unpack_from("<I", d, p+28)[0]
            if ident in CH_IDS:
                vals = {offset: struct.unpack_from("<f", d, p+offset)[0]
                        for offset in EXPECTED}
                source.append((p, CH_IDS[ident], vals))
        if magic == 0xff800c0d and n == 4700:
            for c in range(8):
                vals = struct.unpack_from("<144f", d, p+32+c*584)
                target.append((p,c,vals))
        p += n
    for c in range(8):
        a=[t for t in source if t[1]==c]
        b=[t for t in target if t[1]==c]
        print("ADC",c+1,"AUX160",len(a),"AUX4700",len(b))
        for offset,idx in EXPECTED.items():
            matches=0; tested=0
            for pos,_,v in a:
                nearest=max((k for k in range(len(b)) if b[k][0] < pos), default=-1)
                if nearest<0 or nearest>=len(b):continue
                tested+=1
                if struct.pack("<f",v[offset])==struct.pack("<f",b[nearest][2][idx]):
                    matches+=1
            print(" ",offset,"=>",idx,matches,"/",tested)
if __name__=="__main__":
    for name in sys.argv[1:]: check(name)
