"""Reader/Collector API contracts for missing, partial and stale data. Offline only."""
from fastapi.testclient import TestClient
from collector import service


def test_absent_snapshot_and_invalid_id_no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Read-side HTTP triggered device network')
    monkeypatch.setattr('collector.core.modbus_read', forbidden)
    client = TestClient(service.app)
    device = next(iter(service.collector.devices))
    r = client.get('/api/devices/'+device+'/measurements')
    assert r.status_code == 200
    assert r.json().get('channels') == []
    assert client.get('/api/devices/not_existing/measurements').status_code == 404
    assert client.get('/api/devices/'+device+'/third-octave?channel=9').status_code == 422
    assert client.get('/api/devices/'+device+'/channel-status?channel=0').status_code == 422


def test_partial_live_payload_safe(monkeypatch):
    device = next(iter(service.collector.devices))
    data = {'id':device, 'status':'connected', 'received_at':'2026-10-22T00:00:00+00:00',
            'decoded':{'channels':[{'channel':1}], 'tachometers':[]}}
    monkeypatch.setattr(service.collector, 'live_view', lambda _: data)
    client=TestClient(service.app)
    d=client.get(f'/api/devices/{device}/diagnostics')
    assert d.status_code == 200 and d.json()['system'] is None
    t=client.get(f'/api/devices/{device}/third-octave?channel=1')
    assert t.status_code == 200 and t.json()['bands']==[]
    c=client.get(f'/api/devices/{device}/channel-status?channel=1')
    assert c.status_code == 200 and c.json()['indicators'] is None


def test_stale_never_exposed_as_current(monkeypatch):
    device = next(iter(service.collector.devices))
    monkeypatch.setattr(service.collector, 'live_view', lambda _: {'id':device,'status':'stale','received_at':'2020-01-01T00:00:00Z'})
    client=TestClient(service.app)
    assert client.get(f'/api/devices/{device}/measurements').json()['channels']==[]
    assert client.get(f'/api/devices/{device}/diagnostics').json()['system'] is None
    assert client.get(f'/api/devices/{device}/third-octave').json()['bands']==[]


def test_integrated_app_read_endpoints(monkeypatch):
    import integrated
    monkeypatch.setattr('collector.core.modbus_read',lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')))
    with TestClient(integrated.app) as client:
        assert client.get('/').status_code==200
        assert client.get('/collector/api/health').status_code==200
        assert client.get('/collector/api/devices').status_code==200
        assert client.get('/collector/api/server-status').status_code==200
