"""Audit AUX160 descriptor words versus measured/reference ratios; offline RAW only."""
import argparse
import collections
import json
import struct
from pathlib import Path

TAGS = {0x00402130 + 512*i:i+1 for i in range(8)}
OFFSETS = (32,48,64,80)

def audit(path):
    data=Path(path).read_bytes()
    pos=data.find(bytes.fromhex("dc0a80ff"))
    if pos<0:raise ValueError("Missing ADC marker")
    records=collections.defaultdict(list)
    while pos+8<=len(data):
        marker,size=struct.unpack_from("<II",data,pos)
        if size<8 or pos+size>len(data):raise ValueError("Bad frame boundary")
        if marker==0xff800c0d and size==160:
            tag=struct.unpack_from("<I",data,pos+28)[0]
            if tag in TAGS:
                channel=TAGS[tag]
                for i,off in enumerate(OFFSETS):
                    measured,code,reference,reserved=struct.unpack_from("<fIfI",data,pos+off)
                    records[(channel,i)].append((measured,code,reference,reserved))
        pos+=size
    result=[]
    for (channel,entry),rows in sorted(records.items()):
        codes=sorted(set(x[1] for x in rows))
        refs=sorted(set(struct.pack("<f",x[2]) for x in rows))
        ratios=[x[0]/x[2] for x in rows if x[2]!=0]
        result.append({"adc":channel,"entry":entry,"frames":len(rows),
                       "codes_hex":[hex(x) for x in codes],
                       "ref_bit_patterns":len(refs),
                       "ratio_min":min(ratios) if ratios else None,
                       "ratio_max":max(ratios) if ratios else None,
                       "reserved_nonzero":sum(x[3]!=0 for x in rows)})
    return {"file":Path(path).name,"entries":result}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("raw",nargs="+")
    for name in p.parse_args().raw:
        print(json.dumps(audit(name),ensure_ascii=False,indent=2))
