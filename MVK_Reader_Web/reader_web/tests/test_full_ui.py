import unittest, tempfile, os, sys
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
class TestFullUI(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();os.environ['MVK_DATA_DIR']=cls.tmp.name
  import server
  cls.client=TestClient(server.app)
  p=Path('/mnt/data/MVK00000044-ADC1-2026-04-29--17-27-39.bin')
  with p.open('rb') as f,Path(str(p)+'.tsxml').open('rb') as x:
   rr=cls.client.post('/api/recordings',files={'binary':('test.bin',f),'description':('test.bin.tsxml',x)})
  assert rr.status_code==201,rr.text
  cls.rid=rr.json()['id']
 @classmethod
 def tearDownClass(cls): pass
 def test_capabilities_and_no_devices(self):
  c=self.client.get('/api/capabilities').json()
  self.assertFalse(c['device_commands_enabled']);self.assertFalse(c['modbus_enabled'])
  self.assertEqual(len(c['channels']),10)
 def test_wave_with_filter(self):
  r=self.client.get(f'/api/recordings/{self.rid}/waveform-plus?filter_id=oct:0.3333333333333333:100&seconds=0.5&points=800')
  self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['amplitude'])
 def test_octave(self):
  r=self.client.get(f'/api/recordings/{self.rid}/third-octave')
  self.assertEqual(r.status_code,200,r.text);self.assertGreater(len(r.json()['bands']),20)
 def test_reports(self):
  for ext,magic in [('pdf',b'%PDF'),('xlsx',b'PK')]:
   r=self.client.get(f'/api/recordings/{self.rid}/report.{ext}')
   self.assertEqual(r.status_code,200,r.text[:400]);self.assertTrue(r.content.startswith(magic));(Path(self.tmp.name)/('sample.'+ext)).write_bytes(r.content)
 def test_security_no_write_routes(self):
  for route in ['/api/devices','/api/device/reboot','/api/device/config']:
   self.assertIn(self.client.post(route).status_code,(404,405))
if __name__=='__main__':unittest.main()
