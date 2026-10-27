"""Synthetic, offline tests of existing 4700-byte calculation decoder."""
import math
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from decode_4700 import decode_frame,MARKER,FRAME_SIZE,EXPECTED_TAG0

def frame_fixture():
    buf=bytearray(FRAME_SIZE)
    buf[:4]=MARKER
    struct.pack_into("<I",buf,4,FRAME_SIZE)
    for ch in range(8):
        offset=28+ch*584
        struct.pack_into("<I",buf,offset,EXPECTED_TAG0+512*ch)
        values=[0.]*144
        values[1]=ch+0.25
        values[43]=ch+43.
        values[48]=float(ch+1)
        values[80]=math.sqrt(2)*values[48]
        values[112]=2*values[80]
        struct.pack_into("<144f",buf,offset+4,*values)
        struct.pack_into("<I",buf,offset+580,1<<4)
    return bytes(buf)

class Test4700(unittest.TestCase):
    def test_eight_channel_calculated_frame(self):
        d=decode_frame(frame_fixture())
        self.assertEqual(len(d["channels"]),8)
        for i,c in enumerate(d["channels"]):
            self.assertEqual(len(c["third_octave_candidate"]),43)
            self.assertAlmostEqual(c["third_octave_candidate"][0],i+.25)
            self.assertAlmostEqual(c["third_octave_candidate"][-1],i+43.)
            self.assertAlmostEqual(c["bands"][0]["rms"],i+1)
            self.assertTrue(c["zero_padding"])
            self.assertIn("buffer_fs16_not_ready",c["status_active_flags"])
    def test_reject_bad_marker(self):
        f=bytearray(frame_fixture());f[0]=0
        with self.assertRaises(ValueError): decode_frame(f)
    def test_reject_bad_channel_tag(self):
        f=bytearray(frame_fixture())
        struct.pack_into("<I",f,28,0)
        with self.assertRaises(ValueError): decode_frame(f)

if __name__=="__main__":
    unittest.main()
