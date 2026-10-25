from pathlib import Path
import os,sys,tempfile,io,csv
from fastapi.testclient import TestClient
from openpyxl import load_workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reader_web'))
def test_export_same_filtered_spectrum():
 with tempfile.TemporaryDirectory() as d:
  os.environ['MVK_DATA_DIR']=d
  import server
  c=TestClient(server.app)
  base=Path('/mnt/data/MVK00000044-ADC1-2026-04-29--17-27-39.bin')
  with base.open('rb') as b,Path(str(base)+'.tsxml').open('rb') as x:
   resp=c.post('/api/recordings',files={'binary':('record.bin',b),'description':('record.bin.tsxml',x)})
  assert resp.status_code==201,resp.text
  rid=resp.json()['id'];p='?kind=velocity&df=0.25&lo=1&hi=100&filter_id=oct:0.3333333333333333:16'
  graph=c.get(f'/api/recordings/{rid}/spectrum'+p).json()
  j=c.get(f'/api/recordings/{rid}/report.json'+p).json()
  assert j['spectrum_metrics']==graph['metrics']
  assert j['spectrum_filter_id']=='oct:0.3333333333333333:16'
  csvr=c.get(f'/api/recordings/{rid}/spectrum.csv'+p)
  rows=list(csv.reader(io.StringIO(csvr.content.decode('utf-8-sig'))))
  assert len(rows)==len(graph['amplitude'])+1
  assert abs(float(rows[1][1])-graph['amplitude'][0])<1e-10
  book=load_workbook(io.BytesIO(c.get(f'/api/recordings/{rid}/report.xlsx'+p).content),read_only=True,data_only=True)
  vals=list(book['Спектр'].values)
  assert len(vals)==len(rows)
  assert all(abs(v[1]-g)<1e-8 for v,g in zip(vals[1:],graph['amplitude']))
  assert any(row[0]=='Фильтр' and row[1]=='oct:0.3333333333333333:16' for row in book['Сводка'].values)
  pdf=c.get(f'/api/recordings/{rid}/report.pdf'+p)
  assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
