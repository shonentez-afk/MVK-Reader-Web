#!/usr/bin/env python3
"""Offline Stage 79 static checks of original IDR export. Never connects to devices."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("unit125",type=Path)
p.add_argument("--unit128",type=Path)
a=p.parse_args()
s=a.unit125.read_text(encoding="utf-8",errors="replace")
start=s.index("//00806A8C\n")
end=s.index("00807189",start)
sub=s[start:end]
anchors=["00806A8C","00806AC9", "'.tsxml'","@RewritText",
    'encoding="windows-1251"',"<MainRoot>","<DateTime>","<Culture>en-US</Culture>",
    '<From Units="ms">0</From>', '<To Units="ms">',"<ChannelsQuantity>1</ChannelsQuantity>",
    "<FrequencyPerChannel>","<DataFileName>",'<Channel Index="0">',
    "<ChannelName>","<ChannelNumber>","<ChannelFrequency>",
    "<Units>Count</Units>","<RealDataType>Byte</RealDataType>",
    "<RealDataType>Single</RealDataType>","<DataLength>","<DataOffset>0</DataOffset>",
    "<InternalChannelGain>","</MainRoot>","@Close"]
# The filename element may have prefix .\\ and thus match by opening tag.
missing=[x for x in anchors if x not in sub]
links=["00809719    call        00806A8C"]
missing += [x for x in links if x not in s]
if a.unit128:
 t=a.unit128.read_text(encoding="utf-8",errors="replace")
 missing += [x for x in ["0084605C","00846084","'.tsxml'"] if x not in t]
print("Stage79 static", "PASS" if not missing else "FAIL",len(anchors)+len(links)+(3 if a.unit128 else 0),"anchors", "missing:",missing)
raise SystemExit(bool(missing))
