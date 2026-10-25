from datetime import datetime, timezone, timedelta
from pathlib import Path
from collector.core import Collector

def test_freshness_does_not_poll(tmp_path, monkeypatch):
    import json
    conf=tmp_path/'devices.json'
    conf.write_text(json.dumps({'devices':[{'id':'mvk44','number':'44','ip':'127.0.0.1','port':15020,'enabled':False,'read_ranges':[],'interval_seconds':None}]}))
    c=Collector(conf,tmp_path/'test.sqlite3')
    monkeypatch.setattr('collector.core.modbus_read',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('device access')))
    c.live['mvk44']={'id':'mvk44','status':'connected','received_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),'ranges':[]}
    assert c.live_view('mvk44')['freshness']=='unknown'
    assert c.public_devices()[0]['status']=='connected'
    c.devices['mvk44']['interval_seconds']=2.0
    assert c.live_view('mvk44')['status']=='stale'
    assert c.public_devices()[0]['freshness']=='stale'
    c.live['mvk44']['received_at']=datetime.now(timezone.utc).isoformat()
    assert c.live_view('mvk44')['status']=='connected'
    assert c.live_view('mvk44')['freshness']=='current'
    c.live['mvk44']={'id':'mvk44','status':'connection_error','received_at':datetime.now(timezone.utc).isoformat()}
    assert c.live_view('mvk44')['status']=='connection_error'

def test_unpolled(tmp_path):
    import json
    p=tmp_path/'cfg.json';p.write_text(json.dumps({'devices':[{'id':'x','ip':'127.0.0.1','port':502,'enabled':False,'read_ranges':[],'interval_seconds':None}]}))
    c=Collector(p,tmp_path/'x.sqlite3')
    assert c.live_view('x')['status']=='not_polled'
    assert c.live_view('x')['freshness']=='unknown'
