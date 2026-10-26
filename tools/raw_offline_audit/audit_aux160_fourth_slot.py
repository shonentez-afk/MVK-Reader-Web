"""Offline scan of AUX160 four-entry changes and neighboring AUX4700 readings."""
import argparse,json,struct
from pathlib import Path
TAGS={0x00402130+512*i:i for i in range(8)}
OFFSETS=(32,48,64,80)
def analyze(blob):
    if len(blob)<33064 or blob[24:32]!=b"VAST_MVK":raise ValueError("No full MVK header")
    p=33064;last={};counts={};events=[];aux=[]
    while p+8<=len(blob):
        magic,size=struct.unpack_from("<II",blob,p)
        if size<8 or p+size>len(blob):raise ValueError("Invalid frame length")
        if magic==0xff800c0d and size==4700:
            aux.append((p,[struct.unpack_from("<144f",blob,p+32+584*i) for i in range(8)]))
        elif magic==0xff800c0d and size==160:
            tag=struct.unpack_from("<I",blob,p+28)[0]
            if tag in TAGS:
                ch=TAGS[tag];i=counts.get(ch,0);counts[ch]=i+1
                for entry,off in enumerate(OFFSETS):
                    cur,desc,ref,extra=struct.unpack_from("<fIff",blob,p+off)
                    raw=blob[p+off:p+off+16]
                    old=last.get((ch,entry))
                    now=(desc,raw[8:12],raw[12:16])
                    if old and old!=now:
                        preceding=next((x for x in reversed(aux) if x[0]<p),None)
                        events.append(dict(adc=ch+1,entry=entry+1,index=i,
                            descriptor_before=hex(old[0]),descriptor_after=hex(desc),
                            current=cur,reference=ref,extra_float32=extra,
                            reference_equals_current=raw[:4]==raw[8:12],
                            aux4700_latest_peak_factor=preceding[1][ch][46] if preceding else None))
                    last[(ch,entry)]=now
        p+=size
    return dict(channel_frames=counts,events=events)
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("raw",nargs="+")
    for file in a.parse_args().raw:
        print(json.dumps(dict(file=Path(file).name,**analyze(Path(file).read_bytes())),indent=2))
