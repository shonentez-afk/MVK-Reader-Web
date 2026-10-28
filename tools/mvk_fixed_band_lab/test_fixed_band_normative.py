import unittest
import numpy as np
from scipy.signal import butter,sosfreqz
from fixed_band_normative import response,bin_psd,fixed_band_rms_from_psd

class Tests(unittest.TestCase):
    def test_cascade(self):
        fs=65536;f=np.linspace(0,fs/2,1001)
        a=sosfreqz(butter(3,10,btype="highpass",fs=fs,output="sos"),worN=f,fs=fs)[1]
        b=sosfreqz(butter(3,3000,btype="lowpass",fs=fs,output="sos"),worN=f,fs=fs)[1]
        np.testing.assert_allclose(response(f,fs,10,3000),a*b,atol=1e-12)
    def test_edges(self):
        h=np.abs(response(np.array([0,10,3000,32768]),65536,10,3000))
        self.assertAlmostEqual(h[0],0,places=12)
        self.assertAlmostEqual(h[1],2**-.5,delta=1e-4)
        self.assertAlmostEqual(h[2],2**-.5,delta=1e-4)
        self.assertLess(h[-1],1e-8)
    def test_sinusoid(self):
        fs=65536;t=np.arange(fs)/fs
        f,p=bin_psd(np.sqrt(2)*np.sin(2*np.pi*500*t),fs)
        v=fixed_band_rms_from_psd(f,p,fs,bands=((10,3000),))["10-3000"]
        self.assertAlmostEqual(v,abs(response(np.array([500]),fs,10,3000)[0]),places=6)
    def test_invalid_limits(self):
        with self.assertRaises(ValueError):response(np.array([0,1]),65536,3000,10)

if __name__=="__main__":unittest.main()
