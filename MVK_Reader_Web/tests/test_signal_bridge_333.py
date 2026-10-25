from fastapi.testclient import TestClient
from integrated import app

def test_signal_routes_present_and_no_device_commands():
    c=TestClient(app)
    h=c.get('/api/health');assert h.status_code==200 and h.json()['device_commands_enabled'] is False
    assert c.get('/api/signal/adc/0/waveform').status_code==422
    assert c.get('/api/signal/adc/4/spectrum?kind=velocity').status_code==422

def test_guard_still_blocks_remote_clients():
    c=TestClient(app,client=('192.0.2.44',12345))
    assert c.get('/api/signal/status').status_code==403

def test_signal_offline_data():
    c=TestClient(app)
    r=c.get('/api/signal/status');assert r.status_code in (200,404)
    if r.status_code==200:
        assert len(r.json()['channels'])==8
        assert c.get('/api/signal/adc/4/waveform?points=100').status_code==200
        assert c.get('/api/signal/adc/4/spectrum?high_hz=100').status_code==200
