import json, sqlite3
from collector.core import Collector

def create(tmp_path):
    config=tmp_path/'devices.json'
    config.write_text(json.dumps({'devices':[{'id':'MVK44','ip':'127.0.0.1','port':502,'enabled':False,'interval_seconds':None}]}),encoding='utf-8')
    return config,Collector(config,tmp_path/'db.sqlite3')

def test_diagnostics_no_device_access(tmp_path,monkeypatch):
    config,c=create(tmp_path)
    monkeypatch.setattr('collector.core.modbus_read',lambda *args: (_ for _ in ()).throw(AssertionError('device accessed')))
    status=c.database_diagnostics()
    assert status['status']=='ok' and status['device_requests']==0
    assert all(status['schema_tables'].values())

def test_restart_preserves_history_and_configuration(tmp_path):
    config,c=create(tmp_path)
    with c._connect() as db:
        db.execute('INSERT INTO measurements(device_id,received_at,channel_type,channel,metric,band,value,unit,source) VALUES (?,?,?,?,?,?,?,?,?)',('MVK44','2026-01-01T00:00:00Z','adc',1,'rms','10-3000:velocity',12.5,'mm/s','test'))
    c2=Collector(config,c.database)
    assert c2.devices['MVK44']['enabled'] is False
    assert c2.series('MVK44','adc',1,'rms','10-3000:velocity')[0]['value']==12.5
    assert c2.database_diagnostics()['status']=='ok'

def test_diagnostics_invalid_database(tmp_path):
    config,c=create(tmp_path)
    c.database=tmp_path/'missing'/'unavailable.sqlite3'
    assert c.database_diagnostics()['status']=='error'
