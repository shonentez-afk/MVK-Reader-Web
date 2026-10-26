"""Synthetic offline tests; no external files or devices."""
import math
import struct
import unittest

from decode_4700 import decode_frame, FRAME_SIZE, EXPECTED_TAG0


def fixture():
    data = bytearray(FRAME_SIZE)
    data[:4] = bytes.fromhex("0d0c80ff")
    struct.pack_into("<I", data, 4, FRAME_SIZE)
    struct.pack_into("<I", data, 20, 7)
    for ch in range(8):
        base = 28 + ch*584
        struct.pack_into("<I", data, base, EXPECTED_TAG0 + ch*512)
        struct.pack_into("<f", data, base+4+48*4, 2.0)
        struct.pack_into("<f", data, base+4+80*4, 2.0*math.sqrt(2))
        struct.pack_into("<f", data, base+4+112*4, 4.0*math.sqrt(2))
        struct.pack_into("<I", data, base+580, ch)
    return bytes(data)


class DecoderTests(unittest.TestCase):
    def test_eight_channels(self):
        result = decode_frame(fixture())
        self.assertEqual(len(result["channels"]), 8)
        self.assertEqual(result["frame_counter"], 7)
        self.assertEqual(result["channels"][7]["status_bits_uint32"], 7)
        self.assertTrue(all(ch["zero_padding"] for ch in result["channels"]))

    def test_numeric_relationships(self):
        r = decode_frame(fixture())
        for ch in r["channels"]:
            band = ch["bands"][0]
            self.assertLess(band["peak_rel_error"], 1e-6)
            self.assertLess(band["span_rel_error"], 1e-6)

    def test_sensor_voltage_status_flags(self):
        data = bytearray(fixture())
        struct.pack_into('<I', data, 28+580, 1024)
        struct.pack_into('<I', data, 28+584+580, 2048)
        result = decode_frame(bytes(data))
        self.assertEqual(result['channels'][0]['status_active_flags'], ['sensor_dc_above_max'])
        self.assertEqual(result['channels'][1]['status_active_flags'], ['sensor_dc_at_or_below_min'])
        self.assertEqual(result['channels'][0]['status_unknown_mask'], 0)

    def test_reject_truncated(self):
        with self.assertRaises(ValueError):
            decode_frame(fixture()[:-1])

    def test_reject_wrong_tag(self):
        value = bytearray(fixture())
        struct.pack_into("<I", value, 28, 12345)
        with self.assertRaises(ValueError):
            decode_frame(value)

    def test_reject_nan(self):
        value = bytearray(fixture())
        struct.pack_into("<f", value, 32, float("nan"))
        with self.assertRaises(ValueError):
            decode_frame(value)


if __name__ == "__main__":
    unittest.main()
