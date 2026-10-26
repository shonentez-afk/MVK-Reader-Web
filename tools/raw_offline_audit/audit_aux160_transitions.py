"""Offline regression check of newly captured MVK diagnostic RAW sessions.

Usage: python audit_aux160_transitions.py /path/to/capture.raw
No networking. Reports changes of descriptor/reference, including bitwise
agreement with current float32 at transition.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def audit(raw):
    if len(raw)<33064 or raw[24:32]!=b"VAST_MVK":
        raise ValueError("Missing initial VAST_MVK")
    position=33064
    prev={}
    counts={}
    events=[]
    while position+8<=len(raw):
        marker,length=struct.unpack_from("<II",raw,position)
        if not 8<=length<=100000 or position+length>len(raw):
            raise ValueError("Frame boundary error at offset %s" % position)
        if marker==0xff800c0d and length==160:
            tag=struct.unpack_from("<I",raw,position+28)[0]
            delta=tag-0x00402130
            if 0<=delta<4096 and delta%512==0:
                adc=delta//512+1
                index=counts.get(adc,0)
                counts[adc]=index+1
                for e,offset in enumerate((32,48,64,80),1):
                    cur,code,ref,res=struct.unpack_from("<fIfI",raw,position+offset)
                    reference_bits=struct.unpack_from("<I",raw,position+offset+8)[0]
                    current_bits=struct.unpack_from("<I",raw,position+offset)[0]
                    key=(adc,e)
                    if key in prev and prev[key]!=(code,reference_bits):
                        before=prev[key]
                        events.append({
                            "adc":adc,"entry":e,"aux160_index":index,
                            "raw_offset":position,
                            "old_descriptor":hex(before[0]),
                            "new_descriptor":hex(code),
                            "xor_descriptor":hex(before[0]^code),
                            "new_reference":ref,
                            "current":cur,
                            "new_reference_exactly_equals_current":
                                reference_bits==current_bits,
                            "reference_changed":before[1]!=reference_bits
                        })
                    prev[key]=(code,reference_bits)
        position+=length
    return {"sha256":hashlib.sha256(raw).hexdigest(),
            "frames_by_adc":counts,
            "transitions":events,
            "trailing_bytes":len(raw)-position}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("raw",nargs="+")
    args=p.parse_args()
    for name in args.raw:
        print(json.dumps({"file":Path(name).name,**audit(Path(name).read_bytes())},
                         ensure_ascii=False,indent=2))
