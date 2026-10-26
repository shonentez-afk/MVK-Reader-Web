"""Offline AUX160: test descriptor high bits versus current/reference without inferring semantics."""
import argparse
import json
import struct
from pathlib import Path

TAGS = {0x00402130+512*i:i+1 for i in range(8)}
OFFSETS = (32,48,64,80)

def analyze(data):
    pos=data.find(bytes.fromhex("dc0a80ff"))
    if pos<0:raise ValueError("No ADC marker")
    series={}
    while pos+8<=len(data):
        marker,size=struct.unpack_from("<II",data,pos)
        if size<8 or size>100000 or pos+size>len(data):break
        if marker==0xff800c0d and size==160:
            tag=struct.unpack_from("<I",data,pos+28)[0]
            if tag in TAGS:
                ch=TAGS[tag]
                for j,off in enumerate(OFFSETS):
                    value,descriptor,reference,reserved=struct.unpack_from("<fIfI",data,pos+off)
                    series.setdefault((ch,j),[]).append((value,descriptor,reference))
        pos+=size
    records=[]
    for (ch,j),pairs in sorted(series.items()):
        val,code,ref=pairs[0]
        records.append({"adc":ch,"entry":j+1,"frames":len(pairs),
                        "descriptor_hex":hex(code),
                        "unique_descriptors":len({x[1] for x in pairs}),
                        "high_bits_set":bool(code&0xc00),
                        "ratio_current_reference":val/ref if ref else None})
    return records

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("captured_payload",nargs="+")
    for file in ap.parse_args().captured_payload:
        print(json.dumps({"file":Path(file).name,
                          "records":analyze(Path(file).read_bytes())},indent=2))
