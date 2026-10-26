import struct
import unittest
from mvk_initial_calibration import decode, HEADER_PREFIX, SENS_OFFSET, GAIN_OFFSET, STRIDE, StreamingHeaderDecoder

class TestInitialCalibration(unittest.TestCase):
    def test_decode(self):
        data = bytearray(HEADER_PREFIX)
        data[24:32] = b"VAST_MVK"
        for i in range(8):
            struct.pack_into("<f", data, SENS_OFFSET+i*STRIDE, 0.010194)
            struct.pack_into("<f", data, GAIN_OFFSET+i*STRIDE, 510+i)
        result = decode(data)
        self.assertEqual(len(result["channels"]), 8)
        self.assertEqual(result["channels"][3]["raw_to_acceleration_gain"], 513)
    def test_fragmented_stream_and_following_frames(self):
        raw = bytearray(HEADER_PREFIX)
        raw[24:32] = b"VAST_MVK"
        for i in range(8):
            struct.pack_into("<f", raw, SENS_OFFSET+i*STRIDE, 0.010194)
            struct.pack_into("<f", raw, GAIN_OFFSET+i*STRIDE, 510+i)
        for width in (1, 3, 1471, 4096, 35000):
            stream = StreamingHeaderDecoder()
            content = raw + b"NEXTFRAME"
            for start in range(0, len(content), width):
                stream.feed(content[start:start+width])
            self.assertEqual(stream.calibration["channels"][7]["raw_to_acceleration_gain"], 517)
            self.assertEqual(bytes(stream.remaining_bytes), b"NEXTFRAME")

    def test_truncated_stream_does_not_decode(self):
        stream = StreamingHeaderDecoder()
        self.assertIsNone(stream.feed(bytes(HEADER_PREFIX-1)))
        self.assertIsNone(stream.calibration)

    def test_reject_invalid_header(self):
        with self.assertRaises(ValueError):
            decode(b"not-a-header")

if __name__ == "__main__":
    unittest.main()
