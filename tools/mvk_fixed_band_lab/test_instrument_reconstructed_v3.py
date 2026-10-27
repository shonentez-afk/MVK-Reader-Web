import unittest
import numpy as np
from instrument_reconstructed_v3 import predict,W,S
class FrozenV3Tests(unittest.TestCase):
 def test_frozen_coefficients(self):
  self.assertAlmostEqual(W[3000],.4053022408746561)
  self.assertAlmostEqual(S[3000],.10487198698380487)
 def test_sine_rms(self):
  fs=4096;t=np.arange(fs*4)/fs
  y=predict(np.sqrt(2)*np.sin(2*np.pi*100*t),fs)
  self.assertAlmostEqual(y["10-3000"],1,delta=.015)
 def test_no_target_dependency(self):
  with self.assertRaises(ValueError):predict(np.zeros(10),4096)
if __name__=="__main__":unittest.main()
