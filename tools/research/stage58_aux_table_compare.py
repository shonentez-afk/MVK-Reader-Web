#!/usr/bin/env python3
"""Stage 58: compare archived AUX4700 to non-synchronized TABLE CSV.
Requires cap_parse.py on PYTHONPATH. Read-only, no device connections.
"""
import csv, glob, statistics, sys
from pathlib import Path
import cap_parse as cp

def values_table(path, channel):
    lines=Path(path).read_text(encoding="cp1251").splitlines()[1:]
    header=lines[0].split("|")
    column=f"АЦП {channel}"
    if column not in header:return {}
    pos=header.index(column)
    out={}
    for row in lines[1:]:
        cols=row.split("|")
        if len(cols)<=pos:continue
        try:out[cols[0]]=float(cols[pos].replace(",","."))
        except ValueError:pass
    return out

fields={
0:"Напряжение на датчике",
47:"Виброускорение, Х..25 кГц",
48:"Виброускорение, 10..3000 Гц",
49:"Виброскорость, 10..3000 Гц",
50:"Виброперемещение, 10..3000 Гц",
51:"Виброускорение, 10..2000 Гц",
54:"Виброускорение, 10..1000 Гц",
}
def compare(pcap,table_glob,channels):
    blocks=[]
    for stream in cp.device_streams(str(pcap)):
        for _,data in stream["runs"]:
            frames,_=cp.scan_frames(data)
            blocks += [cp.parse_aux4700(data,off)[1] for off,typ,n in frames
                       if typ==cp.MARK_AUX and n==4700]
    for channel in channels:
        tables=[values_table(p,channel) for p in glob.glob(table_glob)]
        tables=[t for t in tables if t]
        print(pcap,channel,"AUX",len(blocks),"TABLE",len(tables))
        for index,name in fields.items():
            measured=[b[channel-1]["words"][index] for b in blocks]
            exported=[t[name] for t in tables if name in t]
            if not measured or not exported:continue
            nearest=[min(abs(v-x) for x in measured) for v in exported]
            print(index,name,"AUX_RANGE",min(measured),max(measured),
                  "TABLE_RANGE",min(exported),max(exported),
                  "MEDIAN_NEAREST_ABS_DIFF",statistics.median(nearest))
if __name__=="__main__":
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(".")
    compare(root/"83 первый(1).pcapng",str(root/"TABLE-2026-10-27--11-18*.csv"),[4])
    compare(root/"84 отдельно(1).pcapng",str(root/"TABLE-2026-10-28--10-11*.csv"),[1,3,6])
