import io,os,sys,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
fixture=Path('/mnt/data/MVK00000044-ADC1-2026-04-29--17-27-39.bin')
class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        os.environ['MVK_DATA_DIR']=cls.temp.name
        import server
        cls.client=TestClient(server.app)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_health(self):
        j=self.client.get('/api/health').json()
        self.assertEqual(j['mode'],'offline-only');self.assertFalse(j['device_commands_enabled'])
    def test_upload_spectrum_export(self):
        if not fixture.exists():self.skipTest('Пример BIN не найден')
        with fixture.open('rb') as b,open(str(fixture)+'.tsxml','rb') as x:
            res=self.client.post('/api/recordings',files={'binary':('original.bin',b,'application/octet-stream'),'description':('original.bin.tsxml',x,'text/xml')})
        self.assertEqual(res.status_code,201,res.text)
        rid=res.json()['id'];self.assertEqual(res.json()['count'],691200)
        d=self.client.get(f'/api/recordings/{rid}').json();self.assertEqual(d['fs'],65536)
        w=self.client.get(f'/api/recordings/{rid}/waveform?points=1000');self.assertEqual(w.status_code,200)
        s=self.client.get(f'/api/recordings/{rid}/spectrum?df=0.25&hi=100').json()
        self.assertGreater(s['metrics']['peak_frequency_hz'],13)
        self.assertLess(s['metrics']['peak_frequency_hz'],15)
        self.assertEqual(self.client.get(f'/api/recordings/{rid}/spectrum.csv').status_code,200)
        self.assertEqual(self.client.get(f'/api/recordings/{rid}/report.json').status_code,200)
        self.assertEqual(self.client.delete(f'/api/recordings/{rid}').status_code,200)
    def test_invalid_upload(self):
        r=self.client.post('/api/recordings',files={'binary':('bad.bin',b'12'),'description':('bad.tsxml',b'<bad/>')})
        self.assertNotEqual(r.status_code,201)
if __name__=='__main__':unittest.main()
