import json
from collector.core import Collector

def test_overview_stream_preserves_outliers_and_order(tmp_path):
    conf=tmp_path/'devices.json'
    conf.write_text(json.dumps({'devices':[{'id':'mvk44','number':44,'ip':'127.0.0.1','port':502,'enabled':False}]}))
    c=Collector(conf,tmp_path/'data.sqlite3')
    with c._connect() as db:
        db.executemany('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',
            [('mvk44',f'2026-01-01T00:{i//60:02d}:{i%60:02d}+00:00','adc',1,'rms','10-3000:velocity',
              900.0 if i==1001 else float(i%7),'mm/s','test') for i in range(2400)])
    out=c.series_overview('mvk44','adc',1,'rms','10-3000:velocity',buckets=75)
    assert out['total']==2400 and out['sampled']
    assert len(out['points'])<=150
    assert max(p['value'] for p in out['points'])==900.0
    assert [p['received_at'] for p in out['points']]==sorted(p['received_at'] for p in out['points'])
    with c._connect() as db:
        details=' '.join(str(r) for r in db.execute(
            'EXPLAIN QUERY PLAN SELECT received_at,value,unit,id FROM measurements WHERE device_id=? AND channel_type=? AND channel=? AND metric=? AND band=? ORDER BY received_at,id',
            ('mvk44','adc',1,'rms','10-3000:velocity')))
    assert 'idx_meas_series' in details

def test_isolation_by_device(tmp_path):
    conf=tmp_path/'devices.json'
    conf.write_text(json.dumps({'devices':[{'id':'mvk44','number':44,'ip':'127.0.0.1','port':502,'enabled':False},{'id':'mvk50','number':50,'ip':'127.0.0.1','port':502,'enabled':False}]}))
    c=Collector(conf,tmp_path/'data.sqlite3')
    with c._connect() as db:
        for d,v in [('mvk44',3),('mvk50',8)]:
            db.execute('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',
                (d,'2026-01-01T00:00:00+00:00','adc',1,'rms','10-3000:velocity',v,'mm/s','test'))
    assert c.series_overview('mvk44','adc',1,'rms','10-3000:velocity')['points'][0]['value']==3
    assert c.series_overview('mvk50','adc',1,'rms','10-3000:velocity')['points'][0]['value']==8
