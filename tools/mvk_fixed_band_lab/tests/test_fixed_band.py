import unittest
import numpy as np
from mvk_stage13_fixed_band import hann_psd, integrate_three_zones, explicit_zones

class FixedBandTests(unittest.TestCase):
    def test_sine_rms(self):
        fs=8192
        t=np.arange(fs*8)/fs
        f,p=hann_psd(np.sqrt(2)*np.sin(2*np.pi*100*t),fs)
        zones=explicit_zones((5,10),(10,300),(300,500),
               lambda x: np.zeros_like(x),lambda x: np.zeros_like(x))
        self.assertAlmostEqual(integrate_three_zones(f,p,zones)["rms"],1.0,places=3)

    def test_power_weights(self):
        f=np.arange(101,dtype=float)
        p=np.ones_like(f)
        zones=explicit_zones((0,10),(10,20),(20,30),
               lambda x: np.full_like(x,.25),lambda x: np.full_like(x,.5))
        self.assertAlmostEqual(integrate_three_zones(f,p,zones)["rms"]**2,17.5)

    def test_overlap_rejection(self):
        f=np.arange(101,dtype=float)
        p=np.ones_like(f)
        zones=explicit_zones((0,20),(10,30),(30,40),
               lambda x: np.ones_like(x),lambda x: np.ones_like(x))
        with self.assertRaises(ValueError):
            integrate_three_zones(f,p,zones)

if __name__ == "__main__":
    unittest.main()
