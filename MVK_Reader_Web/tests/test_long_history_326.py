import json
from pathlib import Path
from collector.core import Collector
from fastapi.testclient import TestClient
from collector.service import app,collector

def test_long_history_csv_and_envelope(tmp_path,monkeypatch):
    cfg=tmp_path/'devices.json'
    cfg.write_text(json.dumps({'devices':[{'id':'mvk44','number':44,'ip':'127.0.0.1','port':502,'enabled':False}]}))
    c=Collector(cfg,tmp_path/'series.sqlite3')
    with c._connect() as db:
        for i in range(6001):
            db.execute('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',('mvk44',f'2026-01-01T00:{i//60%60:02d}:{i%60:02d}+00:00','adc',1,'rms','10-3000:velocity',900. if i==3000 else float(i%10),'mm/s','test'))
    out=c.series_overview('mvk44','adc',1,'rms','10-3000:velocity',buckets=100)
    assert out['total']==6001 and out['sampled']
    assert max(x['value'] for x in out['points'])==900
    assert len(out['points'])<=200
    assert len(list(c.export_series_rows('mvk44','adc',1,'rms','10-3000:velocity')))==6001
    monkeypatch.setattr('collector.service.collector',c)
    client=TestClient(app)
    r=client.get('/api/devices/mvk44/history-export.csv')
    assert r.status_code==200 and len(r.text.splitlines())==6002
    assert '900.0' in r.text
    r=client.get('/api/devices/mvk44/series-overview?buckets=100')
    assert r.status_code==200 and r.json()['total']==6001
    assert client.get('/api/devices/mvk44/history-export.csv?start=not-a-date').status_code==422
