#!/usr/bin/env python3
"""Verify real archived client-to-MVK TCP/10230 rate command, offline only.

Prints only source-independent counts and meaning; no IP address, serial or raw
capture payload is uploaded. Does not open any network connection.
"""
from collections import defaultdict
from pathlib import Path
import struct,json,sys
from wire_preview import rate_message_preview,parse_rate_message

def outgoing_segments(path):
    with Path(path).open('rb') as f:
        order=None
        while head:=f.read(8):
            if len(head)!=8:raise ValueError('incomplete block header')
            if head[:4]==b'\x0a\x0d\x0d\x0a':
                magic=f.read(4)
                order='<' if magic==b'\x4d\x3c\x2b\x1a' else '>' if magic==b'\x1a\x2b\x3c\x4d' else None
                if order is None:raise ValueError('pcapng endian')
                n=struct.unpack(order+'I',head[4:])[0]
                f.read(n-12)
                continue
            if order is None:raise ValueError('not pcapng')
            n=struct.unpack(order+'I',head[4:])[0]
            if n<12 or n>16000000:raise ValueError('pcapng block size')
            body=f.read(n-8)
            if len(body)!=n-8:raise ValueError('truncated block')
            if struct.unpack(order+'I',head[:4])[0]!=6:continue
            cap=struct.unpack_from(order+'I',body,12)[0]
            pkt=body[20:20+cap]
            if len(pkt)<54 or pkt[12:14]!=b'\x08\x00':continue
            ip=pkt[14:]
            if len(ip)<20 or (ip[0]>>4)!=4 or ip[9]!=6:continue
            ih=(ip[0]&15)*4
            if len(ip)<ih+20:continue
            tcp=ip[ih:struct.unpack_from('!H',ip,2)[0]]
            if len(tcp)<20:continue
            src,dst,seq=struct.unpack_from('!HHI',tcp)
            if dst!=10230:continue
            ofs=(tcp[12]>>4)*4
            if ofs<20 or len(tcp)<ofs:continue
            data=tcp[ofs:]
            if data:yield (ip[12:16],src,ip[16:20],dst),seq,data

def verify(path):
    flows=defaultdict(list)
    for flow,seq,data in outgoing_segments(path):flows[flow].append((seq,data))
    result=[]
    for packets in flows.values():
        packets.sort(key=lambda x:x[0])
        data=b'';expected=None
        for seq,chunk in packets:
            if expected is not None and seq!=expected:raise ValueError('outbound TCP has gaps/overlaps; review before matching')
            data+=chunk;expected=(seq+len(chunk))&0xffffffff
        if len(data)==36:
            rate=parse_rate_message(data)
            same=rate_message_preview(rate)==data
            result.append({'payload_segments':len(packets),'bytes':len(data),
                           'rate_command_detected':same,'sample_rate_hz':rate})
        else:result.append({'payload_segments':len(packets),'bytes':len(data),
                            'rate_command_detected':False,'sample_rate_hz':None})
    return {'outbound_flow_count':len(result),'flows':result}
if __name__=='__main__':
    for path in sys.argv[1:]:
        print(json.dumps({'capture_label':'capture_'+str(len(Path(path).name)),**verify(path)},ensure_ascii=False,indent=2))
