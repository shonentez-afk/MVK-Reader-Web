"""Offline regression tests: no real TCP connections."""
import struct
import unittest
from read_only_capture_diagnostic import Audit, H

def fixture():
    head=bytearray(H)
    head[24:32]=b"VAST_MVK"
    for ch in range(8):
        struct.pack_into("<f",head,812+ch*512,0.010194)
        struct.pack_into("<f",head,836+ch*512,500+ch)
    f=bytearray(1052)
    struct.pack_into("<II",f,0,0xff800adc,1052)
    struct.pack_into("<I",f,12,256)
    return bytes(head)+bytes(f)

class Tests(unittest.TestCase):
    def test_fragments(self):
        raw=fixture()
        for n in (1,3,4096,40000):
            a=Audit()
            for pos in range(0,len(raw),n):a.feed(raw[pos:pos+n])
            self.assertEqual(a.frames["1052"],1)
            self.assertEqual(a.header[7]["gain"],507)
    def test_partial_header(self):
        a=Audit();a.feed(fixture()[:H-1])
        self.assertIsNone(a.header)
    def test_bad_signature(self):
        data=bytearray(fixture());data[24]=0
        with self.assertRaises(ValueError):Audit().feed(data)
    def test_bad_length(self):
        data=bytearray(fixture());struct.pack_into("<I",data,H+4,0)
        with self.assertRaises(ValueError):Audit().feed(data)

if __name__=="__main__":unittest.main()
