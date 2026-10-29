"""Safe offline candidate BIN+TSXML writer from *calibrated* native ADC frames.

In the original IDR, ProcessBufferChunk multiplies the shared channel buffer
by FRange before the BIN stream writes it. This writer reproduces that ordering
with float32 storage and refuses any unknown gain or ADC index discontinuity.
It is NOT a byte-for-byte verified reproduction of original file writer or
multi-channel GUI recording controls. No sockets or device commands.
"""
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import struct
from xml.sax.saxutils import escape

from protocol import ADC,ProtocolError,decode_samples

@dataclass(frozen=True)
class AdcMetadata:
    name: str
    channel: int   # 0..7
    sample_rate: int
    gain: float
    units: str = 'м/с2'

    def validate(self):
        if not self.name or '<' in self.name or '>' in self.name or '&' in self.name:
            raise ValueError('invalid channel label')
        if not 0<=self.channel<8:raise ValueError('ADC index must be 0..7')
        if self.sample_rate not in (512,2048,8192,32768,65536):
            raise ValueError('unsupported sample rate')
        if not math.isfinite(self.gain) or self.gain<=0:
            raise ValueError('verified positive FRange required')
        try:self.units.encode('cp1251');self.name.encode('cp1251')
        except UnicodeEncodeError as e:raise ValueError('metadata not cp1251-compatible') from e


def calibrated_adc_bytes(payload,gain):
    if len(payload)!=1024:
        raise ProtocolError('ADC payload must be exactly 256 float32 samples')
    if not math.isfinite(gain) or gain<=0:
        raise ValueError('cannot produce physical BIN without verified gain')
    values=struct.unpack('<256f',payload)
    if not all(map(math.isfinite,values)):
        raise ProtocolError('nonfinite raw ADC sample')
    calibrated=[v*gain for v in values]
    if not all(map(math.isfinite,calibrated)):
        raise ProtocolError('nonfinite output')
    try:return struct.pack('<256f',*calibrated)
    except OverflowError as ex:raise ProtocolError('calibration overflows float32') from ex


def generate_tsxml(meta, filename, sample_count, created=None):
    meta.validate()
    if sample_count<0:raise ValueError('negative sample count')
    created=created or datetime.now()
    h=created.hour%12 or 12
    dt=f'{created.month}/{created.day}/{created.year} {h}:{created.minute:02d}:{created.second:02d} '+('AM' if created.hour<12 else 'PM')
    ms=sample_count*1000/meta.sample_rate
    # Match the original line-based TSXML layout, cp1251 declaration, en-US.
    def tag(n,v):return f'<{n}>{escape(str(v))}</{n}>'
    lines=['<?xml version="1.0" encoding="windows-1251"?>','<MainRoot>',
           tag('DateTime',dt),tag('Culture','en-US'),
           f'<From Units="ms">0</From>',f'<To Units="ms">{ms:.2f}</To>',
           tag('ChannelsQuantity',1),tag('FrequencyPerChannel',meta.sample_rate),
           tag('DataFileName','.\\'+filename),'<Channels>',
           '  <Channel Index="0">',
           '    '+tag('ChannelName',meta.name),
           '    '+tag('ChannelNumber',meta.channel+1),
           '    '+tag('ChannelFrequency',meta.sample_rate),
           '    '+tag('Units',meta.units),
           '    '+tag('RealDataType','Single'),
           '    '+tag('DataLength',sample_count*4),
           '    '+tag('DataOffset',0),
           '    '+tag('InternalChannelGain',format(meta.gain,'.9g')),
           '  </Channel>','</Channels>','</MainRoot>','']
    return ('\r\n'.join(lines)).encode('cp1251')

class CalibratedBinSink:
    """One-channel offline atomic writer; never masks dropped/duplicate samples.

    A partially failed recording intentionally remains `.partial`, without
    TSXML, so it cannot be mistaken for a complete calibrated MVK BIN.
    """
    def __init__(self, destination,meta,created=None):
        meta.validate()
        self.meta=meta
        self.path=Path(destination)
        if self.path.suffix.lower()!='.bin':raise ValueError('destination must be .bin')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.temp=Path(str(self.path)+'.partial')
        if self.path.exists() or self.temp.exists():
            raise FileExistsError('output or partial file exists; refusing overwrite')
        self.file=self.temp.open('xb')
        self.samples=0
        self.next_seq=None
        self.failed=False
        self.finished=False
        self.created=created

    def append(self,frame):
        if self.failed or self.finished or self.file.closed:
            raise RuntimeError('recording cannot accept more frames')
        try:
            if frame.kind!=ADC:raise ProtocolError('not ADC')
            smp=decode_samples(frame,expected_rate=self.meta.sample_rate)
            if smp.channel!=self.meta.channel:
                raise ProtocolError('ADC channel differs from recorder')
            if self.next_seq is not None and smp.sample_index!=self.next_seq:
                raise ProtocolError('ADC sequence discontinuity; would create a misleading BIN')
            buf=calibrated_adc_bytes(frame.raw[28:],self.meta.gain)
            self.file.write(buf)
            self.samples+=256
            self.next_seq=(smp.sample_index+256)&0xffffffff
        except (ProtocolError,ValueError,IOError,OverflowError):
            self.failed=True
            self.file.close()
            raise

    def finalize(self):
        if self.failed or self.finished or not self.samples:
            raise RuntimeError('recording is incomplete or empty')
        try:
            self.file.flush()
            self.file.close()
            if self.temp.stat().st_size!=self.samples*4:
                raise ProtocolError('short BIN write')
            xml=generate_tsxml(self.meta,self.path.name,self.samples,self.created)
            # Write metadata first; only expose .bin if metadata completes.
            xmltemp=Path(str(self.path)+'.tsxml.partial')
            with xmltemp.open('xb') as f:f.write(xml)
            finalxml=Path(str(self.path)+'.tsxml')
            if finalxml.exists():raise FileExistsError('TSXML exists; refusing overwrite')
            xmltemp.replace(finalxml)
            self.temp.replace(self.path)
            self.finished=True
            return {'samples':self.samples,'bytes':self.samples*4,
                    'bin':str(self.path),'tsxml':str(finalxml)}
        except Exception:
            self.failed=True
            self.file.close()
            raise

    def abort(self):
        if not self.file.closed:self.file.close()
        self.failed=True
        # Retain .partial only; deliberately no valid .bin or TSXML.
