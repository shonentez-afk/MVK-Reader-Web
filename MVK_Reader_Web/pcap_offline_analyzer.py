"""Offline, read-only analysis of classic PCAP (Ethernet/IPv4/TCP).
No network sockets are created. No packet payloads are exported.
This tool helps identify Modbus/TCP vs unknown measurement streams.
"""
import argparse
import json
import socket
import struct
from collections import defaultdict
from pathlib import Path


def _packets(path):
    with open(path, 'rb') as f:
        header = f.read(24)
        if len(header) != 24:
            raise ValueError('Incomplete PCAP global header')
        magic = header[:4]
        if magic == b'\xd4\xc3\xb2\xa1':
            endian = '<'; scale = 1e6
        elif magic == b'\xa1\xb2\xc3\xd4':
            endian = '>'; scale = 1e6
        elif magic == b'\x4d\x3c\xb2\xa1':
            endian = '<'; scale = 1e9
        elif magic == b'\xa1\xb2\x3c\x4d':
            endian = '>'; scale = 1e9
        else:
            raise ValueError('Only classic PCAP is supported (not PCAPNG)')
        _, _, _, _, _, linktype = struct.unpack(endian + 'HHiiii', header[4:])
        if linktype != 1:
            raise ValueError('Only Ethernet PCAP is supported, linktype=%s' % linktype)
        while True:
            h = f.read(16)
            if not h:
                break
            if len(h) != 16:
                raise ValueError('Truncated packet record')
            sec, fraction, captured, original = struct.unpack(endian + 'IIII', h)
            if captured > 16_000_000:
                raise ValueError('Unreasonable packet size')
            pkt = f.read(captured)
            if len(pkt) != captured:
                raise ValueError('Truncated packet body')
            yield sec + fraction / scale, pkt, original


def _tcp(pkt):
    if len(pkt) < 14 or pkt[12:14] != b'\x08\x00':
        return None
    ip = pkt[14:]
    if len(ip) < 20 or ip[0] >> 4 != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 15) * 4
    if ihl < 20 or len(ip) < ihl + 20:
        return None
    if int.from_bytes(ip[6:8], 'big') & 0x1fff:
        return None  # skip fragments
    iplen = int.from_bytes(ip[2:4], 'big')
    ip = ip[:iplen]
    tcp = ip[ihl:]
    srcport, dstport, seq = struct.unpack('!HHI', tcp[:8])
    off = (tcp[12] >> 4) * 4
    if off < 20 or off > len(tcp):
        return None
    src = socket.inet_ntoa(ip[12:16]); dst = socket.inet_ntoa(ip[16:20])
    return (src, srcport, dst, dstport), seq, tcp[off:]


def analyze(path):
    flows = defaultdict(lambda: {'segments': [], 'packets': 0, 'bytes': 0, 'first': None, 'last': None})
    count = 0
    for ts, pkt, _ in _packets(path):
        count += 1
        parsed = _tcp(pkt)
        if parsed is None:
            continue
        key, seq, payload = parsed
        flow = flows[key]
        flow['packets'] += 1
        flow['bytes'] += len(payload)
        flow['first'] = ts if flow['first'] is None else min(flow['first'], ts)
        flow['last'] = ts if flow['last'] is None else max(flow['last'], ts)
        if payload:
            flow['segments'].append((seq, payload))
    result = []
    for (src, sport, dst, dport), f in sorted(flows.items()):
        segments = sorted(f['segments'])
        data = bytearray()
        expected = None
        gaps = 0
        for seq, payload in segments:
            if expected is None:
                expected = seq
            if seq > expected:
                gaps += 1
                expected = seq
            if seq + len(payload) <= expected:
                continue
            piece = payload[max(0, expected-seq):]
            data.extend(piece)
            expected += len(piece)
        frames = []
        modbus = dport == 502 or sport == 502
        if modbus:
            idx = 0
            while idx + 7 <= len(data):
                transaction, protocol, length = struct.unpack('!HHH', data[idx:idx+6])
                if protocol != 0 or not 2 <= length <= 254:
                    idx += 1
                    continue
                end = idx + 6 + length
                if end > len(data):
                    break
                frame = data[idx:end]
                entry = {'transaction_id': transaction, 'unit_id': frame[6], 'function': frame[7], 'response': sport == 502}
                if len(frame) >= 12 and sport != 502 and frame[7] == 3:
                    entry.update({'address': int.from_bytes(frame[8:10], 'big'), 'registers': int.from_bytes(frame[10:12], 'big')})
                if len(frame) >= 9 and sport == 502 and frame[7] == 3:
                    entry['response_data_bytes'] = frame[8]
                frames.append(entry)
                idx = end
        result.append({'src': src, 'src_port': sport, 'dst': dst, 'dst_port': dport,
                       'packet_count': f['packets'], 'tcp_payload_bytes': f['bytes'],
                       'reassembled_bytes': len(data), 'tcp_gaps': gaps,
                       'first_timestamp': f['first'], 'last_timestamp': f['last'],
                       'classification': 'modbus_tcp_candidate' if modbus else 'unknown_tcp_stream',
                       'modbus_frames': frames[:1000], 'modbus_frames_total': len(frames)})
    return {'note': 'Offline metadata only. Unknown TCP payload protocol remains unverified. No raw payload is included.',
            'packets_total': count, 'flows': result}


def main():
    a = argparse.ArgumentParser(description='Offline PCAP metadata/Modbus/TCP analyzer. No live connections.')
    a.add_argument('capture', help='Classic .pcap file, Ethernet IPv4/TCP')
    a.add_argument('--output', help='JSON report path (defaults to stdout)')
    args = a.parse_args()
    report = json.dumps(analyze(args.capture), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
    else:
        print(report)


if __name__ == '__main__':
    main()
