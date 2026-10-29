"""Verified offline R3 TCP/10230 replay: order TCP, recover application framing,
validate all 144 calculation float32s and status for every received channel.
No sockets or device commands. No private sample data in JSON report.
"""
import argparse
from collections import Counter,defaultdict
import json
import math
from bisect import bisect_right
from pathlib import Path
import struct

from protocol import (ADC,TACH,PARAM,ID,ACK,DENIED,
                      RegisterImage, ProtocolError, decode_records,decode_samples,
                      calculated)
from tcp_r3 import iter_pcapng_tcp,OrderedTcp,AppCaptureDecoder


def read_captured_streams(path):
    flows=defaultdict(list)
    for seg in iter_pcapng_tcp(path):flows[seg.flow].append(seg)
    return flows


def verify_all_calculated(frame,image,counters):
    """Independent raw frame offset layout versus reconstituted register image.

    Compare all 144 float32 *bytes* and the status uint32 for all 8 channels;
    also verify 43+72 decoded semantically mapped physical measurements.
    """
    if frame.length!=4700:
        raise ProtocolError('not an 8-channel calculation frame')
    for ch in range(8):
        a=0x2000+0x200*ch
        base=28+ch*584
        descriptor=struct.unpack_from('<I',frame.raw,base)[0]
        if descriptor!=((0x122<<16)|a):
            raise ProtocolError('incorrect 4700 register descriptor')
        raw_floats=frame.raw[base+4:base+580]
        raw_status=frame.raw[base+580:base+584]
        if image.read(a,288)!=raw_floats or image.read(a+0x120,2)!=raw_status:
            raise ProtocolError('register image differs from raw bytes')
        counters['float32_fields_bytewise_compared']+=144
        counters['uint32_status_bytewise_compared']+=1
        vals=struct.unpack_from('<144f',frame.raw,base+4)
        if not all(math.isfinite(x) for x in vals):
            raise ProtocolError('nonfinite numeric calculation')
        model=calculated(image,ch)
        # The meaning of 43 third-octave + 24 RMS/peak/span is specified
        # by vendor register table, not inferred from the FFT.
        for key,indices in (
            ('acceleration_rms',range(1,44)),
            ('band_rms',range(48,72)),
            ('band_peak_equiv',range(80,104)),
            ('band_span_equiv',range(112,136)),
        ):
            if tuple(struct.pack('<f',v) for v in model[key]) != tuple(struct.pack('<f',vals[i]) for i in indices):
                raise ProtocolError('semantic field mapping mismatch: '+key)
            counters['physical_fields_mapped']+=len(indices)
        status=struct.unpack_from('<I',frame.raw,base+580)[0]
        if model['status_raw']!=status:
            raise ProtocolError('status mapping mismatch')
        for nm,bit in (('fs16',4),('fs64',5),('fs512',6)):
            if status & (1<<bit):counters['status_'+nm+'_not_ready_frames']+=1
        counters['channel_records_verified']+=1


def decode_flow(segments,conflict_policy='reject'):
    ordered=OrderedTcp(segments,conflict_policy=conflict_policy)
    app=AppCaptureDecoder()
    image=RegisterImage()
    counts=Counter()
    frame_counts=Counter()
    samples_expected={}
    rate_counts=Counter()
    frame_types_other=Counter()
    decoded_stream_offset=0
    frame_starts=[]
    frame_ends=[]
    frame_labels=[]
    control_frames={}
    conflicting_frame_kinds=Counter()
    for kind,data in ordered.reassemble():
        if kind=='gap':
            app.discontinuity(data)
            image=RegisterImage()  # stale values must not survive an unknown gap
            samples_expected.clear()
            counts['register_epoch_resets']+=1
            continue
        for frame in app.feed(data):
            frame_start=decoded_stream_offset
            decoded_stream_offset+=frame.length
            frame_starts.append(frame_start)
            frame_ends.append(decoded_stream_offset)
            frame_labels.append(f'{frame.kind:08X}/{frame.length}')
            if frame.kind==PARAM and frame.length==160:
                control_frames[frame_start]=frame.raw
            frame_counts[f'0x{frame.kind:08X}/{frame.length}']+=1
            if frame.kind in (ADC,TACH):
                x=decode_samples(frame,expected_rate=65536 if frame.kind==ADC else None)
                k=(frame.kind,x.channel)
                prev=samples_expected.get(k) if frame.kind==ADC else None
                if prev is not None and prev!=x.sample_index:
                    delta=(x.sample_index-prev)&0xffffffff
                    if delta<0x80000000:
                        counts['sample_forward_sequence_discontinuities']+=1
                        counts['sample_missing_counter_units']+=delta
                    else:
                        counts['sample_backward_sequence_discontinuities']+=1
                if frame.kind==ADC:
                    samples_expected[k]=(x.sample_index+len(x.values))&0xffffffff
                rate_counts[str(x.rate)]+=1
                counts['adc_frames' if frame.kind==ADC else 'tach_frames']+=1
            elif frame.kind==PARAM:
                records=decode_records(frame)
                for record in records:image.put(record)
                counts['structured_frames']+=1
                counts['register_blocks']+=len(records)
                if frame.length==32800:
                    assert len(records)==1 and records[0].address==0 and records[0].words==0x4000
                    counts['full_register_images']+=1
                if frame.length==4700:
                    verify_all_calculated(frame,image,counts)
                    counts['aux4700_frames']+=1
            else:
                counts['service_frames']+=1
                frame_types_other[f'{frame.kind:08X}/{frame.length}']+=1
    app.finish()
    for conflict in ordered.conflicts:
        pos=conflict['relative_start']
        idx=bisect_right(frame_starts,pos)-1
        if idx>=0 and pos<frame_ends[idx]:
            frame_kind=frame_labels[idx]
            conflicting_frame_kinds[frame_kind]+=1
            conflict['inside_frame_kind']=frame_kind
            offset=pos-frame_starts[idx]
            conflict['offset_within_frame']=offset
            if frame_kind==f'{PARAM:08X}/160' and offset>=32:
                control=control_frames[frame_starts[idx]]
                descriptor=struct.unpack_from('<I',control,28)[0]
                base=descriptor&0xffff
                conflict['structured_register_base']=hex(base)
                conflict['structured_register_word']=hex(base+(offset-32)//2)
                conflict['structured_payload_word_number']=(offset-32)//4
        else:
            conflicting_frame_kinds['unmapped_trailing_or_skipped']+=1
            conflict['inside_frame_kind']='unmapped'

    return {
        'tcp':dict(ordered.stats),
        'overlap_conflict_spans':ordered.conflicts,
        'conflict_intersected_frames':dict(conflicting_frame_kinds),
        'application':dict(app.stats),
        'frames':dict(sorted(frame_counts.items())),
        'samples_rate_frame_counts':dict(rate_counts),
        'services':dict(frame_types_other),
        'checks':dict(counts),
    }


def replay(path,conflict_policy='reject'):
    streams=read_captured_streams(path)
    output={'capture':Path(path).name,'flow_count':len(streams),'flows':[]}
    for flow,segs in streams.items():
        results=decode_flow(segs,conflict_policy=conflict_policy)
        output['flows'].append({'flow':':'.join([flow[0],str(flow[1]),flow[2],str(flow[3])]),**results})
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--overlap-policy',choices=('reject','preserve_assembled'),default='reject',help='reject by default; alternative marks ambiguous retransmissions')
    a=p.parse_args()
    result=replay(a.capture,conflict_policy=a.overlap_policy)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    for stream in result['flows']:
        print('tcp',stream['tcp'])
        print('application',stream['application'])
        print('checks',stream['checks'])
        print('frames',stream['frames'])
        print('conflicted frame kinds',stream['conflict_intersected_frames'])
    print('Wrote',a.out)
