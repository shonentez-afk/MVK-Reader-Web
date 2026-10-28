import unittest
import numpy as np
from p14_two_spectrum import third_octave_power, fixed_band_power, ThirdOctavePower

class P14Tests(unittest.TestCase):
    def test_octave_power_uses_squared_amplitude_weights(self):
        f=np.arange(5,dtype=float)
        p=np.ones(5)
        a=np.full((1,5),0.5)
        out=third_octave_power(f,p,np.array([1000.]),a)
        self.assertAlmostEqual(out.acceleration_power[0],1.25)

    def test_two_different_input_spectra(self):
        f=np.arange(10,dtype=float)
        p=np.ones(10)
        low=np.full(10,0.5)
        octaves=ThirdOctavePower(np.array([100.,200.,400.]),np.array([2.,3.,4.]))
        result=fixed_band_power(f,p,low,octaves,np.array([0.,.5,0.]),
                                 np.array([True,False,False]))
        self.assertAlmostEqual(result["energy_low"],2.5)
        self.assertAlmostEqual(result["energy_upper"],1.5)
        self.assertAlmostEqual(result["energy_interior"],2.)
        self.assertAlmostEqual(result["rms_m_s2"]**2,6.)

    def test_overlap_rejected(self):
        f=np.arange(10,dtype=float)
        octave=ThirdOctavePower(np.array([100.]),np.array([2.]))
        with self.assertRaises(ValueError):
            fixed_band_power(f,np.ones(10),np.ones(10),octave,
                             np.array([.5]),np.array([True]))
if __name__ == "__main__":
    unittest.main()
