import socket
import struct
from pathlib import Path
from pcap_offline_analyzer import analyze


def sample(src, dst, sport, dport, payload, seq=1):
    ethernet = b'\x00'*12+b'\x08\x00'
    tcp = struct.pack('!HHIIHHHH', sport, dport, seq, 0, 0x5018, 8192, 0, 0)+payload
    ip = bytearray(20)
    ip[0]=0x45; ip[2:4]=struct.pack('!H', 20+len(tcp)); ip[8]=64; ip[9]=6
    ip[12:16]=socket.inet_aton(src); ip[16:20]=socket.inet_aton(dst)
    return ethernet + bytes(ip) + tcp


def test_offline_modbus_and_unknown(tmp_path):
    req = struct.pack('!HHHBBHH', 10, 0, 6, 1, 3, 0x2000, 2)
    pkts = [sample('10.0.0.1','10.0.0.2',5678,502,req[:5],100),
            sample('10.0.0.1','10.0.0.2',5678,502,req[5:],105),
            sample('10.0.0.2','10.0.0.1',2001,5678,b'\x02\x03\x05')]
    file = tmp_path/'lab.pcap'
    with file.open('wb') as f:
        f.write(b'\xd4\xc3\xb2\xa1'+struct.pack('<HHiiii',2,4,0,0,65535,1))
        for p in pkts:
            f.write(struct.pack('<IIII',10,100,len(p),len(p)));f.write(p)
    r=analyze(file)
    assert len(r['flows']) == 2
    modbus=[x for x in r['flows'] if x['dst_port']==502][0]
    assert modbus['modbus_frames'][0]['address']==0x2000
    assert modbus['modbus_frames'][0]['registers']==2
    assert all('payload' not in str(k) for x in r['flows'] for k in x if k != 'tcp_payload_bytes')


def test_reject_pcapng(tmp_path):
    p=tmp_path/'a.pcapng';p.write_bytes(b'\x0a\x0d\x0d\x0a'+b'\0'*24)
    try: analyze(p)
    except ValueError as e: assert 'PCAPNG' in str(e)
    else: raise AssertionError('must reject')
