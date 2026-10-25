"""Regression tests for MVK01 read-only calibration math."""
import struct
import unittest
from mvk_calibration import (
    decode_cdab_float32, register_addresses, parse_channel,
    samples_to_acceleration,
)


def cdab(number):
    packed = struct.pack(">f", number)
    return packed[2:4] + packed[0:2]


class CalibrationTests(unittest.TestCase):
    def test_register_addresses(self):
        self.assertEqual(register_addresses(0), (0x0102, 0x010E))
        self.assertEqual(register_addresses(3), (0x0402, 0x040E))
        self.assertEqual(register_addresses(7), (0x0802, 0x080E))
        with self.assertRaises(ValueError):
            register_addresses(8)

    def test_actual_modbus_examples_adc4(self):
        self.assertAlmostEqual(decode_cdab_float32(bytes.fromhex("f3f243fe")), 509.90582275390625, places=5)
        self.assertAlmostEqual(decode_cdab_float32(bytes.fromhex("1c2143ff")), 510.2197570800781, places=5)
        self.assertAlmostEqual(decode_cdab_float32(bytes.fromhex("04bc3c27")), 0.010193999856710434, places=8)

    def test_roundtrip(self):
        for value in (0.010194, 509.90582, 5.21):
            self.assertAlmostEqual(decode_cdab_float32(cdab(value)), value, places=4)

    def test_parse_channel(self):
        cal = parse_channel(3, bytes.fromhex("04bc3c27"), bytes.fromhex("f3f243fe"))
        self.assertEqual(cal.channel, 3)
        self.assertGreater(cal.conversion_gain, 509)

    def test_multiply_not_divide(self):
        self.assertEqual(samples_to_acceleration([0.0, 0.5, -0.5], 510.0), [0.0, 255.0, -255.0])

    def test_reject_invalid(self):
        with self.assertRaises(ValueError):
            decode_cdab_float32(b"wrong")
        with self.assertRaises(ValueError):
            samples_to_acceleration([1.0], 0)
        with self.assertRaises(ValueError):
            samples_to_acceleration([float("nan")], 510.0)


if __name__ == "__main__":
    unittest.main()
