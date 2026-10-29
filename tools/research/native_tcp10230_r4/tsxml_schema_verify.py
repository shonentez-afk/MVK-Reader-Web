#!/usr/bin/env python3
"""Compare our TSXML generator structure against user-provided original files.
Use only local inputs; no original metadata is printed in the output.
"""
import argparse, json
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from recording_r4 import AdcMetadata,generate_tsxml

def schema(t):
    return [(e.tag,tuple(sorted(e.attrib))) for e in t.iter()]

def verify(path):
    source=ET.parse(path).getroot()
    ch=source.find('./Channels/Channel')
    labels={name:ch.findtext(name) for name in ('ChannelName','ChannelNumber','ChannelFrequency','InternalChannelGain','Units','DataLength')}
    length=int(labels['DataLength'])
    got=ET.fromstring(generate_tsxml(
        AdcMetadata(labels['ChannelName'],int(labels['ChannelNumber'])-1,
                    int(labels['ChannelFrequency']),float(labels['InternalChannelGain']),labels['Units']),
        'SAMPLE.bin',length//4,datetime(2026,10,28,10,12,5)))
    return {'same_schema':schema(source)==schema(got),
            'same_metadata_fields':all(ch.findtext(k)==got.findtext('./Channels/Channel/'+k) for k in ('ChannelName','ChannelNumber','ChannelFrequency','Units','RealDataType','DataLength','DataOffset')),
            'same_duration_ms':source.findtext('To')==got.findtext('To')}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tsxml',nargs='+');a=p.parse_args()
    results=[verify(x) for x in a.tsxml]
    print(json.dumps({'files':len(results),'schema_pass':sum(x['same_schema'] for x in results),
        'metadata_fields_pass':sum(x['same_metadata_fields'] for x in results),
        'duration_pass':sum(x['same_duration_ms'] for x in results)},indent=2))
    if not all(all(x.values()) for x in results):raise SystemExit(1)
