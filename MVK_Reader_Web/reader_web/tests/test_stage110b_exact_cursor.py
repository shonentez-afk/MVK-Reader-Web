"""Stage110B: read-only exact point tests (only synthetic data)."""
import os,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from stage110_original_tabs import app,reduce_minmax,spectrum_for_zip
from test_stage110_original_tabs import make_fixture

class Stage110BExactCursorTests(unittest.TestCase):
 def setUp(self):
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
  self.path=make_fixture(Path(d.name))
  e=patch.dict(os.environ,{'MVK_STAGE110_SESSIONS_DIR':d.name})
  e.start();self.addCleanup(e.stop)
  self.client=TestClient(app)
  self.root='/api/stage110/sessions/STAGE110_SYNTHETIC'

 def test_waveform_sample_is_calibrated_and_not_decimated(self):
  r=self.client.get(self.root+'/waveform_cursor',params={
   'channel':2,'time_s':17/65536,'start_s':0,'seconds':.0625,'mode':'acdc'})
  self.assertEqual(r.status_code,200,r.text)
  d=r.json()
  self.assertEqual(d['sample_index'],17)
  self.assertEqual(d['precision'],'UNDECIMATED_SAMPLE')
  self.assertEqual(d['source'],'MVK_ADC_CALIBRATED_BIN')
  self.assertAlmostEqual(d['value_m_s2'],2*math.sin(2*math.pi*64*17/65536),places=6)

 def test_ac_is_window_mean_candidate_not_instrument_dsp(self):
  r=self.client.get(self.root+'/waveform_cursor',params={'time_s':.015,
   'start_s':0,'seconds':.0625,'mode':'ac'})
  self.assertEqual(r.status_code,200,r.text)
  d=r.json()
  self.assertAlmostEqual(d['value_m_s2'],d['stored_bin_value_m_s2']-d['window_mean_m_s2'],places=10)

 def test_wave_rejects_outside_window_and_invalid_mode(self):
  for p in ({'time_s':.5,'seconds':.0625},{'time_s':.01,'mode':'invalid'},{'time_s':'NaN'}):
   self.assertEqual(self.client.get(self.root+'/waveform_cursor',params=p).status_code,422)

 def test_fft_point_is_actual_bin(self):
  r=self.client.get(self.root+'/spectrum_cursor',params={'frequency_hz':64,
   'n_fft':4096,'mode':1,'start_s':0})
  self.assertEqual(r.status_code,200,r.text)
  d=r.json();self.assertEqual(d['bin_index'],4)
  self.assertEqual(d['frequency_hz'],64)
  self.assertIn('APP_DERIVED',d['source'])
  f=spectrum_for_zip(self.path,1,4096,1,0,max_hz=32768,max_points=262144)
  self.assertAlmostEqual(d['amplitude'],f['amplitude'][4],places=12)

 def test_nyquist_excluded_and_bad_n_rejected(self):
  for p in ({'frequency_hz':32768,'n_fft':4096},
            {'frequency_hz':64,'n_fft':1234}):
   self.assertEqual(self.client.get(self.root+'/spectrum_cursor',params=p).status_code,422)

 def test_minmax_preserves_extrema_and_temporal_order(self):
  t,v=reduce_minmax(np.array([2.,-8.,9.,3.,-4.,6.,5.,0.]),8.,100,4)
  self.assertEqual(t,[101/8,102/8,104/8,105/8])
  self.assertEqual(v,[-8.,9.,-4.,6.])

 def test_single_sample_buckets_are_not_duplicated(self):
  t,v=reduce_minmax(np.array([3.,2.]),8.,0,20)
  self.assertEqual(t,[0,.125]);self.assertEqual(v,[3.,2.])

if __name__=='__main__':unittest.main()
