import json
from pathlib import Path
from collector.core import Collector

def test_range_filters_before_limit(tmp_path):
    cfg=tmp_path/'devices.json'
    cfg.write_text(json.dumps({'devices':[{'id':'mvk44','number':44,'ip':'127.0.0.1','port':502,'enabled':False}]}))
    c=Collector(cfg,tmp_path/'archive.sqlite3')
    with c._connect() as db:
        for day,metric in [('2026-04-01','rms'),('2026-04-02','rms'),('2026-04-03','rms'),('2026-04-02','peak_equivalent')]:
            db.execute('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',('mvk44',day+'T10:00:00+00:00','adc',1,metric,'10-3000:velocity',float(day[-2:]),'mm/s','test'))
    x=c.series_range('mvk44','adc',1,'rms','10-3000:velocity','2026-04-02T00:00:00+00:00','2026-04-03T23:00:00+00:00',1)
    assert x['total']==2 and len(x['points'])==1 and x['truncated']
    assert x['points'][0]['value']==3
    assert c.series_range('mvk44','adc',1,'peak_equivalent','10-3000:velocity')['total']==1
