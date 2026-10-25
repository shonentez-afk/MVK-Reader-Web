import json
import struct
from collector.core import Collector

def f(value):
    return list(struct.unpack('>HH',struct.pack('>f',value)))

def test_sql_measurement_history(tmp_path,monkeypatch):
    cfg=tmp_path/'devices.json'
    cfg.write_text(json.dumps({'devices':[{'id':'44','number':'44','ip':'127.0.0.1','port':502,'enabled':True,'interval_seconds':None,'read_ranges':[{'address':0x2062,'count':2}]}]}))
    c=Collector(cfg,tmp_path/'data.sqlite3')
    monkeypatch.setattr('collector.core.modbus_read',lambda *args,**kwargs:f(9.29))
    data=c.poll_once('44')
    assert data['status']=='connected'
    points=c.series('44','adc',1,'rms','10-3000:velocity')
    assert len(points)==1 and abs(points[0]['value']-9.29)<1e-5
    assert c.series('44','adc',2,'rms','10-3000:velocity')==[]
    assert c.history('44')[0]['address']==0x2062

def test_disabled_no_write(tmp_path,monkeypatch):
    cfg=tmp_path/'devices.json'
    cfg.write_text(json.dumps({'devices':[{'id':'44','ip':'127.0.0.1','port':502,'enabled':False,'interval_seconds':None,'read_ranges':[]}]}))
    c=Collector(cfg,tmp_path/'data.sqlite3')
    try:c.poll_once('44')
    except ValueError:pass
    else:assert False
    assert c.series('44','adc',1,'rms','10-3000:velocity')==[]
