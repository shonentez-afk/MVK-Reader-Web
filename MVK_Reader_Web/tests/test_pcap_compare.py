import socket
import struct
from pcap_session_compare import summarize, compare
from pcap_offline_analyzer import analyze


def packet(src, dst, sport, dport, data, seq=1):
    eth=b'\x00'*12+b'\x08\x00'
    tcp=struct.pack('!HHIIHHHH',sport,dport,seq,0,0x5018,8192,0,0)+data
    ip=bytearray(20); ip[0]=0x45; ip[2:4]=struct.pack('!H',len(tcp)+20); ip[8]=64; ip[9]=6
    ip[12:16]=socket.inet_aton(src);ip[16:20]=socket.inet_aton(dst)
    return eth+bytes(ip)+tcp


def capture(path, streaming):
    req=struct.pack('!HHHBBHH',1,0,6,1,3,0x2000,2)
    packets=[packet('10.4.0.1','10.4.0.2',32111,502,req)]
    if streaming:
        packets += [packet('10.4.0.2','10.4.0.1',9000,32112,b'unknown_measurements_01',100),
                    packet('10.4.0.2','10.4.0.1',9000,32112,b'unknown_measurements_02',123)]
    with path.open('wb') as f:
        f.write(b'\xd4\xc3\xb2\xa1'+struct.pack('<HHiiii',2,4,0,0,65535,1))
        for i, raw in enumerate(packets):
            f.write(struct.pack('<IIII',i+1,0,len(raw),len(raw)));f.write(raw)


def test_detect_added_unknown_stream(tmp_path):
    idle=tmp_path/'idle.pcap'; live=tmp_path/'live.pcap'
    capture(idle,False);capture(live,True)
    result=compare(idle,live)
    assert result['delta']['unknown_payload_bytes']==46
    assert result['with_time_signal']['unknown_flow_count']==1
    assert result['baseline_idle']['read_addresses']==[(8192,2)]
    assert result['safe_mode']=='offline_only_no_network_operations'


def test_empty_unknown_stream(tmp_path):
    a=tmp_path/'a.pcap'; b=tmp_path/'b.pcap'
    capture(a,False); capture(b,False)
    assert compare(a,b)['delta']['unknown_payload_bytes']==0
