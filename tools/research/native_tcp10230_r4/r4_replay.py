#!/usr/bin/env python3
"""Read-only R4 replay on complete archived TCP/10230, preserving ambiguity.

No outbound network operations. Data are decoded from a prior pcapng file and
only aggregate diagnostic counters are printed. The archive overlap workaround
must be selected explicitly; it never silently heals ambiguous TCP bytes.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from protocol import ADC,TACH,PARAM,ProtocolError
from tcp_r3 import OrderedTcp,AppCaptureDecoder,iter_pcapng_tcp
from session_r4 import NativeSession,Mode

def analyze(path, mode, expected_rate, capture_midstream, conflict_policy):
    flows=defaultdict(list)
    for item in iter_pcapng_tcp(path):flows[item.flow].append(item)
    report=[]
    for flow,segments in flows.items():
        ordered=OrderedTcp(segments,conflict_policy=conflict_policy)
        app=AppCaptureDecoder()
        session=NativeSession(mode=mode,expected_rate=expected_rate,
                              capture_midstream=capture_midstream)
        session.begin()
        for typ,data in ordered.reassemble():
            if typ=='gap':
                # Gap invalidates stream state; do not fill bytes or continue
                # applying later values to the same session silently.
                session.transport_break('missing captured TCP bytes')
                break
            for frame in app.feed(data):
                session.ingest(frame,validate_samples=False)
        if session.phase.value=='failed':
            raise ProtocolError('TCP capture has an unrecoverable stream break')
        app.finish()
        unfinished=app.stats.get('trailing_incomplete_bytes',0)
        out=session.end(unfinished_bytes=unfinished)
        out['transport']={
            'segments':ordered.stats.get('captured_segments',0),
            'tcp_missing_bytes':ordered.stats.get('missing_bytes',0),
            'overlap_conflicts':ordered.stats.get('overlap_conflicts',0),
            'overlap_conflicting_bytes':ordered.stats.get('overlap_conflicting_bytes',0),
            'overlap_policy':conflict_policy,
            'invalid_aligned_headers':app.stats.get('invalid_aligned_headers',0),
            'trailing_incomplete_bytes':unfinished,
        }
        if ordered.conflicts:
            out['warnings'].append('ambiguous overlapping TCP bytes in non-AUX control frames; archive-only preserve option')
        report.append(out)
    return {'flow_count':len(report),'flows':report,'offline_only':True}

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Native R4 offline-only state-machine replay')
    p.add_argument('capture')
    p.add_argument('--mode',choices=[e.value for e in Mode],default='task2')
    p.add_argument('--expected-rate',type=int,default=65536)
    p.add_argument('--capture-midstream',action='store_true')
    p.add_argument('--overlap-policy',choices=['reject','preserve_assembled'],default='reject')
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    result=analyze(a.capture,Mode(a.mode),a.expected_rate,
                   a.capture_midstream,a.overlap_policy)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out:a.out.write_text(text+'\n',encoding='utf-8')
    else:print(text)
