import unittest
import numpy as np
from scipy.signal import firwin
from p12_p14_pipeline import decimate_fir,p12_hann_psd,p13_three_quantities,p14_from_two_spectra,reference_octave_windows

class PipelineTests(unittest.TestCase):
    def test_hann_sine(self):
        fs=8192;t=np.arange(fs*2)/fs
        s=p12_hann_psd(np.sqrt(2)*np.sin(2*np.pi*256*t),fs)
        self.assertAlmostEqual(float(s.acceleration_psd.sum()*(s.frequency_hz[1]-s.frequency_hz[0])),1.,places=6)
    def test_decimation_rejects_alias(self):
        fs=8192;t=np.arange(fs*2)/fs
        x=np.sin(2*np.pi*256*t)+np.sin(2*np.pi*3000*t)
        y=decimate_fir(x,4,firwin(129,0.21))
        f=np.fft.rfftfreq(len(y),1/(fs/4));sp=np.abs(np.fft.rfft(y))
        self.assertGreater(sp[np.argmin(abs(f-256))],50*sp[np.argmin(abs(f-952))])
    def test_octave_units_and_p14(self):
        fs=8192;t=np.arange(fs*2)/fs
        s=p12_hann_psd(np.sqrt(2)*np.sin(2*np.pi*256*t),fs)
        centers=np.array([250.])
        a=reference_octave_windows(s.frequency_hz,centers)
        v=reference_octave_windows(s.frequency_hz,centers,'velocity')
        d=reference_octave_windows(s.frequency_hz,centers,'displacement')
        r=p13_three_quantities(s,centers,a,v,d)
        self.assertAlmostEqual(r['acceleration_m_s2'].acceleration_power[0],1.,places=6)
        self.assertAlmostEqual(r['velocity_m_s'].acceleration_power[0],(1/(2*np.pi*256))**2,places=9)
        z=p14_from_two_spectra(s,r['acceleration_m_s2'],np.zeros_like(s.frequency_hz),np.zeros(1),np.array([True]))
        self.assertAlmostEqual(z['rms_m_s2'],1.,places=6)
    def test_missing_fir_is_error(self):
        with self.assertRaises(ValueError):decimate_fir(np.ones(100),4,[])
    def test_duplicate_zone_is_error(self):
        s=p12_hann_psd(np.ones(4096),4096)
        c=np.array([100.]);w=reference_octave_windows(s.frequency_hz,c)
        o=p13_three_quantities(s,c,w,w,w)['acceleration_m_s2']
        with self.assertRaises(ValueError):p14_from_two_spectra(s,o,np.zeros_like(s.frequency_hz),np.ones(1),np.array([True]))

if __name__=='__main__':unittest.main()
