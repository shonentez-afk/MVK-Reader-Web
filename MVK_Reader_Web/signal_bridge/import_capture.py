"""Offline-only PCAPNG -> 8-ADC snapshot. Never connects to instrument."""
import argparse,collections,json,struct
from pathlib import Path
import numpy as np
from .mvk_decode import pcapng,parse_tcp,assemble
from .stream_engine import Channels,Framer,KNOWN

def convert(path,device,out):
    st={'blocks':0,'block_types':collections.Counter(),'packets':0,'interfaces':[]}
    flows=collections.defaultdict(list)
    for _t,link,frame in pcapng(path,st):
        v=parse_tcp(frame,link)
        if v and v[0]==device and v[2]==10230 and v[6]:
            flows[(v[0],v[2],v[1],v[3])].append((v[4],v[6]))
    if len(flows)!=1:raise ValueError(f'Expected one instrument flow, got {len(flows)}; split capture first')
    records=next(iter(flows.values()))
    runs,q=assemble(records)
    channels=Channels(capacity=8_388_608)  # up to 128 seconds per ADC at 65536 Hz
    framer=Framer(channels)
    for _seq,run in runs:
        start=None
        for pos in range(min(20000,max(0,len(run)-8))):
            m,n=struct.unpack_from('<II',run,pos)
            if n not in KNOWN.get(m,set()):continue
            j=pos;ok=0
            while ok<12 and j+8<=len(run):
                mm,nn=struct.unpack_from('<II',run,j)
                if nn not in KNOWN.get(mm,set()) or j+nn>len(run):break
                j+=nn;ok+=1
            if ok>=12:start=pos;break
        if start is None:raise ValueError('Could not align at >=12 known messages')
        framer.feed(run[start:])
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for ch in range(8):np.save(out/f'adc{ch+1}.npy',channels.signal(ch),allow_pickle=False)
    report={'device':device,'source':str(Path(path).name),'fs_hz':65536,'tcp':q,'summary':framer.summary(), 'units':'raw ADC; no automatic physical calibration'}
    (out/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture');p.add_argument('--device',required=True);p.add_argument('--output',default='signal_data');a=p.parse_args()
    result=convert(a.capture,a.device,a.output)
    print(json.dumps({'device':result['device'],'summary':result['summary']},ensure_ascii=False))
