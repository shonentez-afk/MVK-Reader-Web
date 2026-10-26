"""Offline AUX160 vs AUX4700 channel-voltage range audit for captured RAW files."""
import argparse
import json
import struct
from pathlib import Path

ADC_IDS = {0x00402130 + i*0x200: i for i in range(8)}
ADC_MAGIC = bytes.fromhex("dc0a80ff")

def audit(path):
    data = Path(path).read_bytes()
    pos = data.find(ADC_MAGIC)
    if pos < 0:
        raise ValueError("No ADC marker")
    v160 = [[] for _ in range(8)]
    v4700 = [[] for _ in range(8)]
    while pos + 8 <= len(data):
        marker, size = struct.unpack_from("<II", data, pos)
        if size < 8 or pos + size > len(data):
            raise ValueError("Invalid frame size at %s" % pos)
        if marker == 0xff800c0d and size == 160:
            key = struct.unpack_from("<I", data, pos + 28)[0]
            if key in ADC_IDS:
                v160[ADC_IDS[key]].append(struct.unpack_from("<f", data, pos+144)[0])
        elif marker == 0xff800c0d and size == 4700:
            for i in range(8):
                v4700[i].append(struct.unpack_from("<f", data, pos+32+i*584)[0])
        pos += size
    channels = []
    for i in range(8):
        a,b = v160[i],v4700[i]
        channels.append({
            "adc":i+1,"aux160_count":len(a),
            "aux160_nonzero":sum(x != 0 for x in a),
            "aux160_minmax":[min(a),max(a)] if a else None,
            "aux4700_count":len(b),
            "aux4700_nonzero":sum(x != 0 for x in b),
            "aux4700_minmax":[min(b),max(b)] if b else None})
    return {"file":Path(path).name,"channels":channels}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("raw",nargs="+")
    args=parser.parse_args()
    for name in args.raw:
        print(json.dumps(audit(name),ensure_ascii=False,indent=2))
