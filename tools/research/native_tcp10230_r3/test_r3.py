"""Native R3 offline regression tests. No sockets or device connections."""
import os
import struct
import tempfile
import unittest
from pathlib import Path
from collections import Counter

from protocol import PARAM,ADC,Framer,RegisterImage,decode_records,ProtocolError
from tcp_r3 import (Segment,OrderedTcp,OverlapMismatch,
                    AppCaptureDecoder,iter_pcapng_tcp)
from r3_replay import verify_all_calculated


def raw_frame(kind,payload):
    return struct.pack('<II',kind,8+len(payload))+payload

def adc_frame(counter=256,channel=0):
    return raw_frame(ADC,struct.pack('<5I',0,counter,0,channel,65536)+struct.pack('<256f',*([.25]*256)))

def rec(addr,payload):
    assert len(payload)%4==0
    return struct.pack('<I',((len(payload)//2)<<16)|addr)+payload

def param(*blocks):
    return raw_frame(PARAM,bytes(16)+struct.pack('<I',len(blocks))+b''.join(blocks))

def seg(seq,payload,packet=1):return Segment(('abc',10230,'def',1234),seq,payload,packet)

class NativeR3Tests(unittest.TestCase):
    def test_full_register_snapshot(self):
        contents=bytes([0x5A])*32768
        data=param(rec(0,contents))
        self.assertEqual(len(data),32800)
        f=Framer()
        frames=f.feed(data[:100])+f.feed(data[100:])
        self.assertEqual(len(frames),1)
        blocks=decode_records(frames[0])
        self.assertEqual((blocks[0].address,blocks[0].words),(0,0x4000))
        i=RegisterImage()
        i.put(blocks[0])
        self.assertEqual(i.read(0,0x4000),contents)

    def test_sorted_out_of_order_tcp_no_loss(self):
        a=adc_frame(256)
        b=adc_frame(512)
        c=adc_frame(768)
        segs=[seg(200+len(a),b,1),seg(200,a,2),seg(200+len(a)+len(b),c,3)]
        p=OrderedTcp(segs)
        stream=b''.join(data for kind,data in p.reassemble() if kind=='data')
        self.assertEqual(stream,a+b+c)
        self.assertEqual(p.stats['missing_ranges'],0)
        self.assertEqual(p.stats['arrival_late_or_repeat'],1)
        self.assertEqual(len(Framer().feed(stream)),3)

    def test_sequence_rollover(self):
        p=OrderedTcp([seg(0xfffffff0,b'a'*16,1),seg(0,b'b'*12,2)])
        reconstructed=b''.join(x for kind,x in p.reassemble() if kind=='data')
        self.assertEqual(reconstructed,b'a'*16+b'b'*12)
        self.assertEqual(p.stats['missing_ranges'],0)

    def test_duplicate_overlap_identical(self):
        p=OrderedTcp([seg(100,b'0123456789'),seg(104,b'456789')])
        self.assertEqual(b''.join(b for k,b in p.reassemble() if k=='data'),b'0123456789')
        self.assertEqual(p.stats['overlap_segments'],1)
        self.assertEqual(p.stats['overlap_conflicts'],0)

    def test_conflicting_duplicate_failclosed(self):
        data=[seg(100,b'abcdefgh',1),seg(103,b'defX',2)]
        with self.assertRaises(OverlapMismatch):list(OrderedTcp(data).reassemble())
        p=OrderedTcp(data,conflict_policy='preserve_assembled')
        self.assertEqual(b''.join(b for k,b in p.reassemble() if k=='data'),b'abcdefgh')
        self.assertEqual(p.stats['overlap_conflicts'],1)
        self.assertEqual(p.stats['overlap_conflicting_bytes'],1)
        self.assertEqual(p.conflicts[0]['relative_start'],6)

    def test_gap_remains_explicit(self):
        a=adc_frame(0)
        b=adc_frame(512)
        p=OrderedTcp([seg(100,a),seg(100+len(a)+20,b)])
        items=list(p.reassemble())
        self.assertEqual([k for k,v in items],['data','gap','data'])
        self.assertEqual(items[1][1],20)
        self.assertEqual(p.stats['missing_bytes'],20)
        d=AppCaptureDecoder()
        frames=[]
        for kind,bytes_or_gap in items:
            if kind=='gap':d.discontinuity(bytes_or_gap)
            else:frames+=d.feed(bytes_or_gap)
        self.assertEqual(len(frames),2)
        self.assertEqual(d.stats['resync_anchors'],1)

    def test_seek_validates_anchor_after_corruption(self):
        d=AppCaptureDecoder()
        d.discontinuity(100)
        bad=struct.pack('<II',PARAM,32)+bytes(24)
        good=adc_frame()
        self.assertEqual(d.feed(b'bad'+bad+good[:50]),[])
        frames=d.feed(good[50:])
        self.assertEqual(len(frames),1)
        self.assertEqual(frames[0].kind,ADC)
        self.assertGreater(d.stats['quarantined_bytes'],0)

    def test_eight_channel_complete_semantic_verification(self):
        blocks=[]
        for channel in range(8):
            address=0x2000+channel*0x200
            vals=[float(channel+1 + 0.001*i) for i in range(144)]
            blocks.append(rec(address,struct.pack('<144f',*vals)+struct.pack('<I',0x10)))
        raw=param(*blocks)
        self.assertEqual(len(raw),4700)
        f=Framer().feed(raw)[0]
        image=RegisterImage()
        for b in decode_records(f):image.put(b)
        c=Counter()
        verify_all_calculated(f,image,c)
        self.assertEqual(c['float32_fields_bytewise_compared'],1152)
        self.assertEqual(c['uint32_status_bytewise_compared'],8)
        self.assertEqual(c['physical_fields_mapped'],920)
        self.assertEqual(c['status_fs16_not_ready_frames'],8)

    def test_pcapng_tcp_packet_extract(self):
        raw=adc_frame()
        tcp=struct.pack('!HHIIHHHH',10230,54321,12345,0,(5<<12)|0x18,4096,0,0)+raw
        ip=bytearray(20)
        ip[0]=0x45
        ip[8]=64
        ip[9]=6
        ip[12:16]=b'\x0a\x00\x00\x01'
        ip[16:20]=b'\x0a\x00\x00\x02'
        struct.pack_into('!H',ip,2,len(ip)+len(tcp))
        ethernet=bytes.fromhex('00112233445566778899aabb0800')+ip+tcp
        pad=bytes((-len(ethernet))%4)
        shb=struct.pack('<IIIHHqI',0x0a0d0d0a,28,0x1a2b3c4d,1,0,-1,28)
        idb=struct.pack('<IIHHII',1,20,1,0,65535,20)
        n=8+20+len(ethernet)+len(pad)+4
        epb=struct.pack('<IIIIIII',6,n,0,0,0,len(ethernet),len(ethernet))+ethernet+pad+struct.pack('<I',n)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.pcapng'
            path.write_bytes(shb+idb+epb)
            entries=list(iter_pcapng_tcp(path))
            self.assertEqual(len(entries),1)
            self.assertEqual(entries[0].sequence,12345)
            self.assertEqual(entries[0].payload,raw)

if __name__=='__main__':unittest.main(verbosity=2)
