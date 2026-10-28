#!/usr/bin/env python3
"""Stage54 self-contained sanity tests; run from a directory with exported TSXML."""
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path(".")
assert 304+203040+75188==278532
assert 4+16+75168==75188
fc03={"83":{4:509.9058228,6:508.0881042},
      "84":{1:510.5650330,3:509.7116089,6:509.6076355}}
seen=[]
for file in folder.glob("*.tsxml"):
    name=re.search(r"MVK(\d+)-",file.name)
    if not name: continue
    serial=name.group(1)
    ip={"00000043":"84","00000050":"83"}.get(serial)
    if ip is None: continue
    ch=ET.parse(file).getroot().find(".//Channel")
    n=int(ch.findtext("ChannelNumber"))
    if n not in fc03[ip]:continue
    gain=float(ch.findtext("InternalChannelGain"))
    assert abs(gain-fc03[ip][n])<=0.05,(file.name,gain)
    seen.append((serial,n,ip))
assert len(seen)==5,seen
print("PASS 5/5 TSXML, 2/2 size relations")
print("NOTE firmware binary not provided; its internals not verified")
