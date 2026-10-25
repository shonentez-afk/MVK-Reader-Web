import json
from fastapi.testclient import TestClient
from integrated import app
from collector.service import collector

def test_device_management_sandbox(tmp_path):
    old = collector.config
    with collector.lock:
        original = json.loads(old.read_text(encoding='utf-8'))
    sandbox = tmp_path/'devices.json'
    sandbox.write_text(json.dumps(original),encoding='utf-8')
    collector.config=sandbox
    try:
        collector.reload()
        client=TestClient(app)
        payload={'id':'test_offline_338','number':'999','ip':'192.0.2.10','modbus_port':502,'signal_port':10230}
        assert client.post('/api/mvk/devices',json=payload).status_code==201
        assert client.post('/api/mvk/devices',json=payload).status_code==409
        assert next(x for x in client.get('/api/mvk/devices').json()['devices'] if x['id']==payload['id'])['enabled'] is False
        assert next(x for x in collector.devices.values() if x['id']==payload['id'])['interval_seconds'] is None
        payload['ip']='192.0.2.11'
        assert client.put('/api/mvk/devices/test_offline_338',json=payload).status_code==200
        assert collector.devices[payload['id']]['ip']=='192.0.2.11'
        payload['ip']='not-a-valid-ip'
        assert client.put('/api/mvk/devices/test_offline_338',json=payload).status_code==422
        assert collector.devices[payload['id']]['ip']=='192.0.2.11'
        assert client.delete('/api/mvk/devices/test_offline_338').status_code==200
        assert 'test_offline_338' not in collector.devices
        assert client.get('/api/mvk/capabilities').json()['can_start_signal_live'] is False
    finally:
        collector.config=old
        collector.reload()
