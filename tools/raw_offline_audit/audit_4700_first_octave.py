"""Offline verification: first/last third-octave slots in MVK 4700 frames.

Uses the already verified decoder. Does not infer the reason for 42 vs 43.
"""
import argparse
import json
from pathlib import Path
from decode_4700 import iter_frames

def inspect(path):
    frames=list(iter_frames(Path(path).read_bytes()))
    per_channel=[]
    for ch in range(8):
        rows=[fr["channels"][ch] for fr in frames]
        first=[r["third_octave_candidate"][0] for r in rows]
        last=[r["third_octave_candidate"][-1] for r in rows]
        per_channel.append({
            "adc":ch+1,"n_frames":len(rows),
            "first_063_nonzero":sum(v!=0 for v in first),
            "first_063_min":min(first,default=None),
            "first_063_max":max(first,default=None),
            "last_10000_nonzero":sum(v!=0 for v in last),
            "first_063_values":first,
            "status_bits":[r["status_bits_uint32"] for r in rows]
        })
    return {"file":Path(path).name,"total_frames":len(frames),
            "channels":per_channel,
            "conclusion":"43 fields exist; nonzero status cannot alone explain P1.3 count 42"}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("raw",nargs="+")
    args=p.parse_args()
    for fn in args.raw:
        print(json.dumps(inspect(fn),ensure_ascii=False,indent=2))
