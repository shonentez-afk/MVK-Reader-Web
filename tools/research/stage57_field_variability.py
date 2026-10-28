#!/usr/bin/env python3
"""Stage 57: offline map variability of 128-byte channel records (requires cap_parse.py)."""
import sys,struct,collections,csv
from pathlib import Path
import cap_parse as cp

def inspect(path):
    results=[]
    for stream in cp.device_streams(str(path)):
        for _,data in stream["runs"]:
            frames,_=cp.scan_frames(data)
            items=collections.defaultdict(list)
            for off,t,length in frames:
                if t==cp.MARK_AUX and length==160:
                    hdr=struct.unpack_from("<I",data,off+28)[0]
                    if hdr>>16 != 64: raise ValueError("record size not 64 words")
                    items[hdr&0xffff].append(data[off+32:off+160])
            for ident,parts in sorted(items.items()):
                assert len(parts)==15
                for index in range(32):
                    words=[struct.unpack_from("<I",p,4*index)[0] for p in parts]
                    results.append((path.name,stream["src"],f"{ident:04X}",index,len(set(words)),sum(bool(w) for w in words)))
    return results

if __name__=="__main__":
    rows=[]
    for arg in sys.argv[1:]: rows.extend(inspect(Path(arg)))
    w=csv.writer(sys.stdout)
    w.writerow(["capture","source","record_id","word_index","distinct_values","nonzero_records"])
    w.writerows(rows)
