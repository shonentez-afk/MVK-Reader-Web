import struct
from collector.decoder import decode_snapshot

def f(v):return list(struct.unpack('>HH',struct.pack('>f',v)))
def test_registers():
    a=0x2000
    snapshot={'id':'mvk44','received_at':'2026-10-21T10:00:00Z','ranges':[
       {'address':a,'values':f(12.5)},
       {'address':a+0x62,'values':f(9.29)},
       {'address':a+0xa2,'values':f(13.0)},
       {'address':a+0xe2,'values':f(25.0)},
       {'address':0x3000,'values':f(14.5)+f(0.1)+f(0.0)}]}
    d=decode_snapshot(snapshot)
    c=d['channels'][0]
    assert c['channel']==1 and c['voltage_v']==12.5
    assert abs(c['rms']['10-3000:velocity']['value']-9.29)<1e-5
    assert c['peak_equivalent']['10-3000:velocity']['value']==13
    assert c['peak_peak_equivalent']['10-3000:velocity']['value']==25
    assert c['rms']['filter1:velocity']['value'] is None
    assert d['tachometers'][0]['frequency_hz']==14.5

def test_partial_pair_is_not_decoded():
    d=decode_snapshot({'ranges':[{'address':0x2062,'values':[0x4114]}]})
    assert not d['channels']

def test_nonfinite_rejected():
    d=decode_snapshot({'ranges':[{'address':0x2062,'values':f(float('nan'))}]})
    assert not d['channels']
