import struct
from fastapi.testclient import TestClient
from collector.decoder import THIRD_OCTAVE_HZ, decode_snapshot
from collector.service import app, collector

def test_exact_centers():
    assert len(THIRD_OCTAVE_HZ)==43
    assert THIRD_OCTAVE_HZ[0]==0.63 and THIRD_OCTAVE_HZ[-1]==10000

def test_partial_snapshot_preserves_missing_values():
    data=struct.pack('>f',2.5)
    words=struct.unpack('>HH',data)
    v=decode_snapshot({'id':'test','ranges':[{'address':0x2002,'values':list(words)}]})
    c=v['channels'][0]
    assert c['third_octave_acceleration_m_s2'][0]==2.5
    assert all(x is None for x in c['third_octave_acceleration_m_s2'][1:])

def test_api_offline_and_live():
    with TestClient(app) as client:
        id=next(iter(collector.devices))
        with collector.lock:
            old=collector.live.get(id)
            collector.live.pop(id,None)
        try:
            r=client.get(f'/api/devices/{id}/third-octave?channel=1')
            assert r.status_code==200 and r.json()['status']=='not_polled'
            assert client.get(f'/api/devices/{id}/third-octave?channel=9').status_code==422
            assert client.get('/api/devices/unknown/third-octave').status_code==404
            decoded=decode_snapshot({'id':id,'ranges':[{'address':0x2002,'values':[0x4020,0]}]})
            with collector.lock:
                collector.live[id]={'id':id,'status':'connected','received_at':'test-ts','decoded':decoded}
            j=client.get(f'/api/devices/{id}/third-octave?channel=1').json()
            assert j['available_count']==1 and len(j['bands'])==43
            assert j['bands'][0]['rms_m_s2']==2.5 and j['bands'][1]['rms_m_s2'] is None
        finally:
            with collector.lock:
                if old is None:collector.live.pop(id,None)
                else:collector.live[id]=old
