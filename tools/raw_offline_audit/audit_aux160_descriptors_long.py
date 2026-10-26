"""Inspect AUX160 descriptors in a reassembled MVK TCP payload or RAW.
No networking; for PCAPNG first perform offline TCP reassembly.
"""
import argparse
import json
import struct
from pathlib import Path

TAGS = {0x00402130 + 512*i:i+1 for i in range(8)}
OFFSETS = (32,48,64,80)

def inspect(blob):
    p=blob.find(bytes.fromhex("dc0a80ff"))
    if p<0: raise ValueError("No ADC frame found")
    results={ch:[] for ch in range(1,9)}
    while p+8<=len(blob):
        marker,n=struct.unpack_from("<II",blob,p)
        if n<8 or n>100000 or p+n>len(blob):
            break
        if marker==0xff800c0d and n==160:
            tag=struct.unpack_from("<I",blob,p+28)[0]
            if tag in TAGS:
                entries=[]
                for off in OFFSETS:
                    current,descriptor,ref,reserved=struct.unpack_from("<fIfI",blob,p+off)
                    entries.append({"descriptor":descriptor,
                                    "current":current,"reference":ref,
                                    "reserved":reserved})
                results[TAGS[tag]].append(entries)
        p+=n
    report=[]
    for ch,frames in results.items():
        if not frames: continue
        report.append({"adc":ch,"frames":len(frames),
            "descriptor_patterns":sorted(set(tuple(row["descriptor"] for row in f) for f in frames)),
            "reference_unique_counts":[len(set(struct.pack("<f",f[i]["reference"]) for f in frames)) for i in range(4)],
            "initial_references":[frames[0][i]["reference"] for i in range(4)]})
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("payload_files",nargs="+")
    for name in parser.parse_args().payload_files:
        print(json.dumps({"file":Path(name).name,"channels":inspect(Path(name).read_bytes())},
                         indent=2))
