#!/usr/bin/env python3
"""Offline MVK01 RAW frame audit. Never connects to instruments."""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

MAGIC = bytes.fromhex("dc0a80ff")
FRAME = 1052

def audit(path):
    raw = Path(path).read_bytes()
    offsets = []
    at = 0
    while True:
        at = raw.find(MAGIC, at)
        if at < 0:
            break
        offsets.append(at)
        at += len(MAGIC)
    valid = [i for i in offsets if i + FRAME <= len(raw) and
             struct.unpack_from("<I", raw, i + 4)[0] == FRAME]
    channels = collections.Counter()
    counters = {i: [] for i in range(8)}
    for i in valid:
        channel = struct.unpack_from("<I", raw, i + 20)[0]
        sample_index = struct.unpack_from("<I", raw, i + 12)[0]
        channels[channel] += 1
        if channel in counters:
            counters[channel].append(sample_index)
    gaps = collections.Counter(b - a for a, b in zip(offsets, offsets[1:]))
    summary = {
        "filename": Path(path).name, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "markers": len(offsets), "valid_frames": len(valid),
        "first_marker_offset": offsets[0] if offsets else None,
        "last_marker_offset": offsets[-1] if offsets else None,
        "channel_counts_zero_based": dict(sorted(channels.items())),
        "marker_spacing_top": gaps.most_common(12),
        "channels": {}
    }
    for ch, seq in counters.items():
        deltas = [((b - a) & 0xffffffff) for a, b in zip(seq, seq[1:])]
        summary["channels"][str(ch + 1)] = {
            "blocks": len(seq), "samples": len(seq) * 256,
            "first_sample_counter": seq[0] if seq else None,
            "last_sample_counter": seq[-1] if seq else None,
            "non_256_step_count": sum(step != 256 for step in deltas),
            "sample_counter_deltas": collections.Counter(deltas).most_common(5)
        }
    return summary

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw", nargs="+", help="RAW file(s), from private local storage")
    p.add_argument("--out", help="JSON report path (optional)")
    args = p.parse_args()
    result = [audit(filename) for filename in args.raw]
    report = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)

if __name__ == "__main__":
    main()
