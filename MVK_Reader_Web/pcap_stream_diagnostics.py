"""Read-only comparison of classic PCAP captures. Metadata only, no sample decoding."""
import argparse
import json
from pathlib import Path
from pcap_offline_analyzer import analyze


def _key(flow):
    # Avoid ephemeral client ports: identify the same service/direction across captures.
    a = (flow['src'], flow['src_port'])
    b = (flow['dst'], flow['dst_port'])
    if a[1] <= 1024 and b[1] > 1024:
        return (a[0], a[1], 'server_to_client')
    if b[1] <= 1024 and a[1] > 1024:
        return (b[0], b[1], 'client_to_server')
    return (a[0], a[1], b[0], b[1])


def _summarize(report):
    output = {}
    for f in report['flows']:
        key = str(_key(f))
        duration = max(0., (f['last_timestamp'] or 0) - (f['first_timestamp'] or 0))
        entry = output.setdefault(key, {'bytes': 0, 'packets': 0, 'gaps': 0, 'modbus_frames': 0, 'duration_s': 0., 'classification': f['classification'], 'connections': 0})
        entry['bytes'] += f['tcp_payload_bytes']
        entry['packets'] += f['packet_count']
        entry['gaps'] += f['tcp_gaps']
        entry['modbus_frames'] += f['modbus_frames_total']
        entry['duration_s'] = max(entry['duration_s'], duration)
        entry['connections'] += 1
    for value in output.values():
        d = value['duration_s']
        value['bytes_per_second'] = round(value['bytes'] / d, 2) if d > 0 else None
        value['caution'] = 'TCP segments incomplete: do not infer frame structure' if value['gaps'] else None
    return output


def compare(idle_pcap, signal_pcap):
    idle = _summarize(analyze(idle_pcap))
    signal = _summarize(analyze(signal_pcap))
    entries = []
    for key in sorted(set(idle) | set(signal)):
        a, b = idle.get(key), signal.get(key)
        rate_a = None if not a else a['bytes_per_second']
        rate_b = None if not b else b['bytes_per_second']
        entries.append({
            'service_key': key,
            'idle': a,
            'signal': b,
            'appeared_with_signal': a is None,
            'disappeared_with_signal': b is None,
            'rate_delta_bytes_per_second': round(rate_b - rate_a, 2) if rate_a is not None and rate_b is not None else None,
            'candidate_only': bool(b and b['classification'] == 'unknown_tcp_stream' and (a is None or (rate_a is not None and rate_b is not None and rate_b > rate_a))),
        })
    return {'analysis': 'offline_metadata_only', 'flows': entries,
            'limitations': ['Different capture windows and unrelated TCP traffic may bias comparisons',
                            'Traffic changes do not prove existence or format of waveform transfer',
                            'Packets may be truncated; TCP gaps invalidate payload frame inference',
                            'No instrument commands are issued']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('idle_pcap'); p.add_argument('signal_pcap'); p.add_argument('--output')
    args = p.parse_args()
    report = json.dumps(compare(args.idle_pcap, args.signal_pcap), indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
    else:
        print(report)

if __name__ == '__main__':
    main()
