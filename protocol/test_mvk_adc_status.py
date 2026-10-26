"""Synthetic unit tests. No device connections or RAW files."""
import unittest
from mvk_adc_status import decode_status

class StatusTests(unittest.TestCase):
    def test_healthy(self):
        d=decode_status(0)
        self.assertEqual(d["active"], [])
        self.assertEqual(d["unknown_mask"],0)
    def test_upper_voltage(self):
        d=decode_status(1024)
        self.assertEqual(d["active"][0]["code"],"sensor_dc_above_max")
        self.assertNotIn("Обрыв кабеля", " ".join(d["display_labels_ru"]))
        d2=decode_status(1024,cable_open_label=True)
        self.assertIn("Обрыв кабеля", " ".join(d2["display_labels_ru"]))
    def test_lower_voltage(self):
        self.assertEqual(decode_status(2048)["active"][0]["bit"],11)
    def test_unknown_retained(self):
        self.assertEqual(decode_status(0x80000000)["unknown_mask"],0x80000000)
    def test_combined(self):
        d=decode_status(1025)
        self.assertEqual([x["bit"] for x in d["active"]],[0,10])
    def test_reject(self):
        for bad in (-1,0x100000000,1.2,None):
            with self.assertRaises(ValueError):decode_status(bad)

if __name__=="__main__":unittest.main()
