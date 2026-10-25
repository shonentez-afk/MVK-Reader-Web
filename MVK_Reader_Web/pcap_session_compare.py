"""Compare OFFLINE PCAP metadata from two MVKView recording sessions.
Does not open sockets or export payload. No commands are sent to instruments.
"""
import argparse
import json
from pathlib import Path
from pcap_offline_analyzer import analyze


def summarize(report):
    flows = report['flows']
    return {
        'packets_total': report['packets_total'],
        'flow_count': len(flows),
        'modbus_request_count': sum(sum(not x.get('response', False) for x in f['modbus_frames']) for f in flows),
        'modbus_response_count': sum(sum(x.get('response', False) for x in f['modbus_frames']) for f in flows),
        'unknown_flow_count': sum(f['classification'] == 'unknown_tcp_stream' for f in flows),
        'unknown_payload_bytes': sum(f['tcp_payload_bytes'] for f in flows if f['classification'] == 'unknown_tcp_stream'),
        'tcp_gaps': sum(f['tcp_gaps'] for f in flows),
        'unknown_flows': sorted([{
            'endpoints': f"{f['src']}:{f['src_port']} -> {f['dst']}:{f['dst_port']}",
            'payload_bytes': f['tcp_payload_bytes'],
            'packets': f['packet_count'],
            'duration_seconds': round(f['last_timestamp']-f['first_timestamp'], 6) if f['last_timestamp'] is not None else None,
        } for f in flows if f['classification'] == 'unknown_tcp_stream'], key=lambda x: -x['payload_bytes']),
        'read_addresses': sorted(set((frame['address'], frame['registers'])
            for f in flows for frame in f['modbus_frames'] if frame.get('function') == 3 and 'address' in frame)),
    }


def compare(idle, signal):
    a, b = summarize(analyze(idle)), summarize(analyze(signal))
    return {'baseline_idle': a, 'with_time_signal': b,
            'delta': {k: b[k]-a[k] for k in ('packets_total', 'flow_count', 'unknown_flow_count', 'unknown_payload_bytes', 'modbus_request_count', 'modbus_response_count')},
            'warning': ('These counts identify candidate traffic only, not a proven streaming protocol. '
                        'Different capture durations are not normalized. No decoded vibration samples.'),
            'safe_mode': 'offline_only_no_network_operations'}


def main():
    p = argparse.ArgumentParser(description='Offline MVKView capture comparison; metadata only.')
    p.add_argument('idle_pcap', help='Normal connection, no time-signal tab')
    p.add_argument('signal_pcap', help='Same instrument with time-signal tab open')
    p.add_argument('--output', help='Save JSON report (omit to print)')
    args = p.parse_args()
    s = json.dumps(compare(args.idle_pcap,args.signal_pcap), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(s, encoding='utf-8')
    else: print(s)

if __name__ == '__main__':
    main()
