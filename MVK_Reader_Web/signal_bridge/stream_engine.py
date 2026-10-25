"""Read-only MVK TCP stream processor. No socket or device commands."""
import collections,struct,math
import numpy as np
from .signal_processing import spectra,time_stats
MEAS=0xFF800ADC
KNOWN={MEAS:{1052},0xFF8001AC:{284},0xFF800C0D:{44,76,160,4700}}
class Channels:
    def __init__(self,fs=65536,capacity=262144,gains=None):
        self.fs=fs;self.capacity=capacity;self.gains=gains or {}
        self.parts=[collections.deque() for _ in range(8)]
        self.sizes=[0]*8;self.blocks=[0]*8;self.gaps=[0]*8;self.duplicates=[0]*8;self.expected=[None]*8
    def feed(self,ch,index,payload):
        if not 0<=ch<8 or len(payload)!=1024:raise ValueError('bad channel or samples')
        x=np.frombuffer(payload,dtype='<f4').copy()
        if not np.isfinite(x).all():raise ValueError('nonfinite samples')
        if self.expected[ch] is not None:
            delta=(index-self.expected[ch])&0xffffffff
            if delta==0:pass
            elif delta<0x80000000:self.gaps[ch]+=delta
            else:self.duplicates[ch]+=1;return
        self.expected[ch]=(index+256)&0xffffffff
        self.parts[ch].append(x);self.sizes[ch]+=256;self.blocks[ch]+=1
        while self.sizes[ch]-len(self.parts[ch][0])>=self.capacity:
            self.sizes[ch]-=len(self.parts[ch].popleft())
    def signal(self,ch,count=None,calibrated=False):
        x=np.concatenate(list(self.parts[ch])) if self.parts[ch] else np.array([],dtype=np.float32)
        if count is not None:x=x[-count:]
        if calibrated:
            if ch not in self.gains:raise ValueError(f'ADC {ch+1}: gain not verified')
            return x.astype('float64')*self.gains[ch]
        return x
    def spectrum(self,ch,nperseg=65536,**kwargs):
        x=self.signal(ch,count=max(2*nperseg,nperseg),calibrated=True)
        return spectra(x,self.fs,nperseg=nperseg,**kwargs)
    def summary(self):return {'blocks':self.blocks,'samples_in_buffers':self.sizes,'sample_gaps':self.gaps,'duplicate_blocks':self.duplicates,'calibrated_channels':sorted(self.gains)}
class Framer:
    def __init__(self,channels):
        self.channels=channels;self.tail=bytearray();self.counts=collections.Counter();self.invalid=0
    def feed(self,data):
        self.tail.extend(data)
        while len(self.tail)>=8:
            marker,n=struct.unpack_from('<II',self.tail)
            if n not in KNOWN.get(marker,set()):
                self.invalid+=1;raise ValueError('unknown application header; do not silently resync')
            if len(self.tail)<n:break
            if marker==MEAS:
                ch=struct.unpack_from('<I',self.tail,20)[0]
                idx=struct.unpack_from('<I',self.tail,12)[0]
                self.channels.feed(ch,idx,self.tail[28:1052])
            self.counts[f'{marker:08X}/{n}']+=1
            del self.tail[:n]
    def summary(self):return {'messages':dict(self.counts),'unfinished_bytes':len(self.tail),'invalid_headers':self.invalid,**self.channels.summary()}
