"""MVK01 native TCP/10230 frame decoder (offline core, no socket I/O).

Evidence: original MVKView IDR and verified RAW frames. No use of mvk_tcp_reader_v2.
"""
from dataclasses import dataclass
import struct
import math

ADC=0xFF800ADC
TACH=0xFF8001AC
PARAM=0xFF800C0D
ID=1
ACK=0x00010FF0
DENIED=0x00010FFF
EXPECTED={ADC:(1052,),TACH:(284,)}
# Structured frames are variable-sized; real full-register snapshot is 32800 B.
# Validate their record descriptors with decode_records(), not a short allowlist.
MAX=0x20000

class ProtocolError(ValueError): pass

@dataclass(frozen=True)
class Frame:
    kind:int
    length:int
    raw:bytes

@dataclass(frozen=True)
class Samples:
    channel:int
    rate:int
    sample_index:int
    values:tuple

@dataclass(frozen=True)
class RegisterBlock:
    address:int
    words:int
    payload:bytes

class Framer:
    def __init__(self): self.tail=bytearray()
    def feed(self,chunk):
        self.tail.extend(chunk)
        frames=[]
        while len(self.tail)>=8:
            kind,n=struct.unpack_from('<II',self.tail)
            if n<8 or n%4 or n>MAX or (kind in EXPECTED and n not in EXPECTED[kind]) or (kind==PARAM and n<32):
                raise ProtocolError('invalid frame envelope: kind=%08x length=%s'%(kind,n))
            if kind not in EXPECTED and kind not in (PARAM,ID,ACK,DENIED):
                raise ProtocolError('unknown frame type: %08x'%kind)
            if len(self.tail)<n: break
            raw=bytes(self.tail[:n]);del self.tail[:n]
            frames.append(Frame(kind,n,raw))
        return frames
    def finish(self):
        if self.tail:raise ProtocolError('truncated trailing frame (%d bytes)'%len(self.tail))

def decode_samples(frame, expected_rate=None):
    if frame.kind not in (ADC,TACH):raise ProtocolError('not samples')
    n=256 if frame.kind==ADC else 64
    if frame.length!=(28+4*n):raise ProtocolError('sample length mismatch')
    # Frame: 8-byte type/size, five uint32 header, then n float32.
    unk0,sequence,unk2,channel,rate=struct.unpack_from('<5I',frame.raw,8)
    if (frame.kind==ADC and channel>=8) or (frame.kind==TACH and channel not in (8,9)):
        raise ProtocolError('invalid sample channel')
    if rate not in (512,2048,8192,32768,65536):raise ProtocolError('invalid sample rate')
    if expected_rate is not None and rate!=expected_rate:raise ProtocolError('unexpected session sample rate')
    samples=struct.unpack_from('<%df'%n,frame.raw,28)
    if not all(map(math.isfinite,samples)):raise ProtocolError('non-finite sample')
    return Samples(channel,rate,sequence,samples)

def decode_records(frame):
    if frame.kind!=PARAM:raise ProtocolError('not a structured frame')
    # 20-byte structured header in body, followed by count descriptors.
    if frame.length<28:raise ProtocolError('short param frame')
    count=struct.unpack_from('<I',frame.raw,24)[0]
    if count>4096:raise ProtocolError('too many register blocks')
    pos=28;out=[]
    for _ in range(count):
        if pos+4>frame.length:raise ProtocolError('truncated register descriptor')
        desc=struct.unpack_from('<I',frame.raw,pos)[0];pos+=4
        address=desc&0xffff;words=desc>>16
        if not words or words%2 or address+words>0x4000 or pos+words*2>frame.length:
            raise ProtocolError('invalid register block')
        out.append(RegisterBlock(address,words,frame.raw[pos:pos+words*2]))
        pos+=words*2
    if pos!=frame.length:raise ProtocolError('trailing bytes in register message')
    return out

class RegisterImage:
    def __init__(self): self.data=bytearray(0x4000*2);self.valid=bytearray(0x4000)
    def put(self,block):
        a=block.address;b=a+block.words
        if not 0<=a<b<=0x4000 or len(block.payload)!=2*block.words:raise ProtocolError('invalid register image write')
        self.data[2*a:2*b]=block.payload;self.valid[a:b]=b'\x01'*block.words
    def read(self,address,words):
        if address<0 or words<1 or address+words>0x4000 or not all(self.valid[address:address+words]):
            raise ProtocolError('registers not available')
        return bytes(self.data[2*address:2*(address+words)])
    def f32(self,address):return struct.unpack('<f',self.read(address,2))[0]
    def u32(self,address):return struct.unpack('<I',self.read(address,2))[0]

BANDS=(.63,.8,1.,1.25,1.6,2.,2.5,3.15,4.,5.,6.3,8.,10.,12.5,16.,20.,25.,31.5,40.,50.,63.,80.,100.,125.,160.,200.,250.,315.,400.,500.,630.,800.,1000.,1250.,1600.,2000.,2500.,3150.,4000.,5000.,6300.,8000.,10000.)

def calculated(image, channel):
    if channel not in range(8):raise ValueError('channel must be 0..7')
    a=0x2000+0x200*channel
    values=[image.f32(a+2+2*i) for i in range(43)]
    rms=[image.f32(a+0x60+2*i) for i in range(24)]
    peak=[image.f32(a+0xA0+2*i) for i in range(24)]
    span=[image.f32(a+0xE0+2*i) for i in range(24)]
    status=image.u32(a+0x120)
    return {'adc':channel+1,'third_octave_hz':BANDS,'acceleration_rms':values,'band_rms':rms,'band_peak_equiv':peak,'band_span_equiv':span,'status_raw':status,'not_ready':{'fs16':bool(status&16),'fs64':bool(status&32),'fs512':bool(status&64)}}
