from fastapi.testclient import TestClient
from integrated import app

def test_capabilities_safe():
    c=TestClient(app)
    j=c.get('/api/mvk/capabilities').json()
    assert j['tabs']['calculated']['port']==502
    assert j['tabs']['wave']['port']==10230
    assert j['can_start_signal_live'] is False

def test_registry_readonly():
    c=TestClient(app)
    r=c.get('/api/mvk/devices')
    assert r.status_code==200
    j=r.json()
    assert j['source']=='collector-config' and j['read_only'] is True
    assert all('id' in d and 'ip' in d for d in j['devices'])

def test_no_unsafe_method():
    c=TestClient(app)
    assert c.post('/api/mvk/devices',json={'ip':'192.0.2.84'}).status_code==405
