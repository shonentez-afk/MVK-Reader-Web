import struct,unittest,math
from protocol import *

def pack(kind,payload):return struct.pack('<II',kind,8+len(payload))+payload

def rec(address,payload):
    assert len(payload)%4==0
    return struct.pack('<I',(len(payload)//2)<<16|address)+payload

def param(*records):
    payload=bytes(16)+struct.pack('<I',len(records))+b''.join(records)
    b=pack(PARAM,payload)
    assert len(b)%4==0
    return b

class Tests(unittest.TestCase):
    def test_split(self):
        f=Framer();b=pack(ACK,b'');self.assertEqual(f.feed(b[:3]),[]);self.assertEqual(len(f.feed(b[3:])),1);f.finish()
    def test_sample(self):
        raw=pack(ADC,struct.pack('<5I',0,256,0,2,65536)+struct.pack('<256f',*range(256)))
        x=decode_samples(Framer().feed(raw)[0],65536)
        self.assertEqual((x.channel,x.sample_index,len(x.values)),(2,256,256))
        with self.assertRaises(ProtocolError):decode_samples(Framer().feed(raw)[0],32768)
    def test_struct(self):
        p=param(rec(0x2002,struct.pack('<3f',1.5,2.5,3.5)))
        f=Framer().feed(p)[0];rr=decode_records(f);self.assertEqual(len(rr),1)
        i=RegisterImage()
        for r in rr:i.put(r)
        self.assertEqual(i.f32(0x2002),1.5)
        self.assertEqual(i.f32(0x2006),3.5)
    def test_partial_register_no_stale(self):
        i=RegisterImage();i.put(RegisterBlock(0x2002,2,struct.pack('<f',.5)))
        with self.assertRaises(ProtocolError):calculated(i,0)
    def test_invalid(self):
        with self.assertRaises(ProtocolError):Framer().feed(struct.pack('<II',ADC,12)+bytes(4))
        bad=pack(PARAM,bytes(16)+struct.pack('<I',1)+struct.pack('<I',(3<<16)|0x2000)+bytes(8))
        with self.assertRaises(ProtocolError):decode_records(Framer().feed(bad)[0])
    def test_eight_channels_full(self):
        i=RegisterImage();r=[]
        for ch in range(8):
            a=0x2000+ch*0x200
            floats=[float(ch+1+i/100) for i in range(144)]
            payload=struct.pack('<144f',*floats)+struct.pack('<I',0x30)
            r.append(rec(a,payload))
        b=param(*r);self.assertEqual(len(b),4700)
        for rr in decode_records(Framer().feed(b)[0]):i.put(rr)
        for ch in range(8):
            x=calculated(i,ch)
            self.assertEqual(len(x['acceleration_rms']),43)
            self.assertEqual(len(x['band_rms']),24)
            self.assertEqual(x['adc'],ch+1)
            self.assertTrue(x['not_ready']['fs16'])
            self.assertTrue(x['not_ready']['fs64'])
            self.assertFalse(x['not_ready']['fs512'])

if __name__=='__main__':unittest.main(verbosity=2)
