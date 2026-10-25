from pcap_stream_diagnostics import _summarize, compare

def test_rates_and_gaps():
    obj = {'flows': [{'src':'10.0.0.1','src_port':502,'dst':'10.0.0.2','dst_port':49999,'first_timestamp':1.0,'last_timestamp':3.0,'tcp_payload_bytes':100,'packet_count':4,'tcp_gaps':1,'modbus_frames_total':2,'classification':'modbus_tcp_candidate'}]}
    entry = next(iter(_summarize(obj).values()))
    assert entry['bytes_per_second'] == 50
    assert entry['gaps'] == 1
    assert entry['caution']

def test_empty_pcaps(monkeypatch):
    monkeypatch.setattr('pcap_stream_diagnostics.analyze', lambda p: {'flows': []})
    assert compare('a','b')['flows'] == []

def test_new_unknown_flow(monkeypatch):
    f={'src':'10.0.0.1','src_port':3333,'dst':'10.0.0.2','dst_port':50000,'first_timestamp':0.,'last_timestamp':2.,'tcp_payload_bytes':200,'packet_count':2,'tcp_gaps':0,'modbus_frames_total':0,'classification':'unknown_tcp_stream'}
    monkeypatch.setattr('pcap_stream_diagnostics.analyze', lambda p: {'flows':[f] if p=='signal' else []})
    result=compare('idle','signal')['flows'][0]
    assert result['candidate_only'] and result['appeared_with_signal']
