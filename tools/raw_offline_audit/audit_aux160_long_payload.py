"""Offline audit of four constant AUX160 fields in saved TCP payload or RAW.
Accepts a reassembled TCP payload; pcapng normalization is a separate step.
"""
import argparse
import json
import struct
from pathlib import Path

MAGIC_ADC = bytes.fromhex("dc0a80ff")
AUX_MARKER = 0xff800c0d
CHANNEL_TAGS = {0x00402130 + 0x200*i:i+1 for i in range(8)}
OFFSETS = (40,56,72,88)

def audit(payload):
    start = payload.find(MAGIC_ADC)
    if start < 0:
        raise ValueError("ADC frame marker not found")
    pos = start
    series = {i:{off:[] for off in OFFSETS} for i in range(1,9)}
    counts = {}
    while pos+8 <= len(payload):
        marker,length = struct.unpack_from("<II",payload,pos)
        if length < 8 or length > 100000 or pos+length > len(payload):
            if pos+length > len(payload):
                break
            raise ValueError("Invalid frame at byte %d" % pos)
        counts[length] = counts.get(length,0)+1
        if marker==AUX_MARKER and length==160:
            tag=struct.unpack_from("<I",payload,pos+28)[0]
            if tag in CHANNEL_TAGS:
                channel=CHANNEL_TAGS[tag]
                for off in OFFSETS:
                    bits=struct.unpack_from("<I",payload,pos+off)[0]
                    series[channel][off].append(bits)
        pos+=length
    rows=[]
    for ch in range(1,9):
        for off in OFFSETS:
            vals=series[ch][off]
            rows.append({"adc":ch,"offset":off,"count":len(vals),
                         "unique_bit_patterns":len(set(vals)),
                         "first_float32":struct.unpack("<f",struct.pack("<I",vals[0]))[0] if vals else None})
    return {"counts":counts,"trailing_bytes":len(payload)-pos,"fields":rows}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("saved_tcp_payload",nargs="+")
    for filename in parser.parse_args().saved_tcp_payload:
        print(json.dumps({"file":Path(filename).name,**audit(Path(filename).read_bytes())},indent=2))
