#!/usr/bin/env python3
"""MVK TCP/10230 read-only stream parser. Offline-tested; no commands sent."""
import argparse
import collections
import socket
import struct
import time
from pathlib import Path

PORT=10230
T_ID=1
T_ADC=0xFF800ADC
T_TACH=0xFF8001AC
T_STRUCTURED=0xFF800C0D
T_CONFIG_REPLY=0x00010FF1
T_DENIED=0x00011000
MAX_FRAME=0x20000
RATES={512,2048,8192,32768,65536}

class FrameParser:
    def __init__(self):
        self.buffer=bytearray()
        self.count=0
    def feed(self,data):
        self.buffer.extend(data)
        pos=0
        results=[]
        view=self.buffer
        while len(view)-pos>=8:
            typ,length=struct.unpack_from('<II',view,pos)
            if length<8 or length%4 or length>MAX_FRAME:
                raise ValueError(f'invalid frame type=0x{typ:08X} size={length} at buffered offset {pos}')
            if len(view)-pos<length:
                break
            results.append((typ,length,bytes(view[pos+8:pos+length])))
            pos+=length
        if pos: del self.buffer[:pos]
        self.count+=len(results)
        return results

def adc(frame):
    typ,length,body=frame
    if typ not in (T_ADC,T_TACH): raise ValueError('not ADC/tacho')
    required=1052 if typ==T_ADC else 284
    if length!=required or len(body)!=required-8: raise ValueError('bad ADC packet length')
    w0,seq,w2,channel,fs=struct.unpack_from('<5I',body)
    if (typ==T_ADC and channel not in range(8)) or (typ==T_TACH and channel not in (8,9)):
        raise ValueError('unexpected channel')
    if fs not in RATES: raise ValueError(f'unexpected sampling frequency: {fs}')
    return {'channel':channel,'fs':fs,'seq':seq,'payload':body[20:]}

def records(frame):
    typ,length,body=frame
    if typ!=T_STRUCTURED: raise ValueError('not structured')
    if len(body)<20: raise ValueError('short structured body')
    count=struct.unpack_from('<I',body,16)[0]
    if count>4096: raise ValueError('unreasonable record count')
    pos=20
    out=[]
    for _ in range(count):
        if pos+4>len(body): raise ValueError('truncated record header')
        word=struct.unpack_from('<I',body,pos)[0]
        pos+=4
        address=word&0xffff
        words=word>>16
        nbytes=words*2
        if words==0 or words%2 or address+words>0x4000 or pos+nbytes>len(body):
            raise ValueError(f'invalid record: address={address}, words={words}')
        out.append((address,words,body[pos:pos+nbytes]))
        pos+=nbytes
    if pos!=len(body): raise ValueError(f'{len(body)-pos} unexpected trailing bytes')
    return out

def inspect(frame):
    typ,length,body=frame
    if typ in (T_ADC,T_TACH):return ('sample',adc(frame))
    if typ==T_STRUCTURED:return ('structured',records(frame))
    if typ==T_ID:return ('identity',body)
    if typ==T_CONFIG_REPLY:return ('config_reply',body)
    if typ==T_DENIED:return ('operation_denied',body)
    return ('unknown',body)

def listen(ip,seconds=10.0,out=None):
    """Read only. Never sends application payload; no config/flash mutations."""
    p=FrameParser(); counts=collections.Counter(); samples=collections.Counter(); rates=collections.defaultdict(set)
    folder=Path(out) if out else None
    if folder: folder.mkdir(parents=True,exist_ok=True)
    files={}; start=time.monotonic()
    try:
        with socket.create_connection((ip,PORT),timeout=1.0) as s:
            s.settimeout(5.0)
            while time.monotonic()-start<seconds:
                chunk=s.recv(65536)
                if not chunk:break
                for frame in p.feed(chunk):
                    typ,ln,_=frame
                    counts[(typ,ln)]+=1
                    kind,info=inspect(frame)
                    if kind=='sample':
                        ch=info['channel']; rates[ch].add(info['fs']); samples[ch]+=len(info['payload'])//4
                        if folder and ch<8:
                            if ch not in files:files[ch]=(folder/f'ADC{ch+1}.bin').open('wb')
                            files[ch].write(info['payload'])
    finally:
        for f in files.values(): f.close()
    print('frames',p.count,'unconsumed_bytes',len(p.buffer))
    for (typ,length),num in sorted(counts.items()):print(f'0x{typ:08X} length={length} count={num}')
    for ch,n in sorted(samples.items()):print(f'channel={ch} samples={n} rates={sorted(rates[ch])}')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='Read-only MVK TCP reader (no control writes)')
    ap.add_argument('ip');ap.add_argument('--seconds',type=float,default=10);ap.add_argument('--out')
    a=ap.parse_args();listen(a.ip,a.seconds,a.out)
