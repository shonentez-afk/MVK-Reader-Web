import struct
import unittest
from mvk_initial_calibration import decode, HEADER_PREFIX, SENS_OFFSET, GAIN_OFFSET, STRIDE

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
    def test_reject_invalid_header(self):
        with self.assertRaises(ValueError):
            decode(b"not-a-header")

if __name__ == "__main__":
    unittest.main()
