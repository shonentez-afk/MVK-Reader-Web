import json
from fastapi.testclient import TestClient
from integrated import app
from collector.service import collector


def test_modbus_control_without_network(tmp_path, monkeypatch):
    old=collector.config
    file=tmp_path/'devices.json'
    file.write_text(json.dumps({'devices':[{'id':'test339','number':'339','ip':'192.0.2.1','port':502,'signal_port':10230,'enabled':False,'read_ranges':[{'address':4096,'count':2}],'interval_seconds':None},{'id':'empty339','number':'340','ip':'192.0.2.2','port':502,'enabled':False,'read_ranges':[],'interval_seconds':None}]}))
    collector.config=file
    try:
        collector.reload()
        client=TestClient(app)
        assert client.get('/api/mvk/devices/test339/connection').json()['signal']['enabled'] is False
        assert client.post('/api/mvk/devices/empty339/modbus/start',json={'interval_seconds':5}).status_code==409
        assert client.post('/api/mvk/devices/test339/modbus/start',json={'interval_seconds':0.1}).status_code==422
        r=client.post('/api/mvk/devices/test339/modbus/start',json={'interval_seconds':5})
        assert r.status_code==200 and collector.devices['test339']['enabled']
        assert client.get('/api/mvk/devices/test339/connection').json()['modbus']['status']=='not_polled'
        assert client.post('/api/mvk/devices/test339/modbus/start',json={'interval_seconds':5}).status_code==409
        r=client.post('/api/mvk/devices/test339/modbus/stop')
        assert r.status_code==200 and not collector.devices['test339']['enabled']
        assert collector.devices['test339']['interval_seconds'] is None
        assert client.get('/api/mvk/devices/missing/connection').status_code==404
    finally:
        collector.config=old;collector.reload()
