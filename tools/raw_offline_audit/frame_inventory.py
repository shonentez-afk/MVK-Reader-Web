#!/usr/bin/env python3
"""Full offline MVK stream frame inventory, no device or network access."""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

KNOWN = {
    ("dc0a80ff", 1052): "ADC sample frame",
    ("ac0180ff", 284): "auxiliary frame",
    ("0d0c80ff", 44): "other frame type",
    ("0d0c80ff", 76): "other frame type",
    ("0d0c80ff", 160): "other frame type",
    ("0d0c80ff", 4700): "other frame type",
}
ADC_MAGIC = bytes.fromhex("dc0a80ff")


def analyze(path):
    data = Path(path).read_bytes()
    start = data.find(ADC_MAGIC)
    if start < 0:
        raise ValueError("ADC marker not found")
    pos = start
    counts = collections.Counter()
    auxiliary_channels = collections.Counter()
    adc_channels = collections.Counter()
    unknown = []
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("Incomplete frame header at offset %d" % pos)
        kind = data[pos:pos + 4].hex()
        size = struct.unpack_from("<I", data, pos + 4)[0]
        if not (8 <= size <= 100000 and pos + size <= len(data)):
            raise ValueError("Invalid frame size at %d: %d" % (pos, size))
        key = (kind, size)
        counts[key] += 1
        if key not in KNOWN:
            unknown.append({"offset": pos, "marker": kind, "length": size})
        if kind == "dc0a80ff" and size == 1052:
            adc_channels[struct.unpack_from("<I", data, pos + 20)[0]] += 1
        if kind == "ac0180ff" and size == 284:
            auxiliary_channels[struct.unpack_from("<I", data, pos + 20)[0]] += 1
        pos += size
    return {
        "file": Path(path).name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "initial_unclassified_prefix_bytes": start,
        "frame_counts": [
            {"marker": k[0], "length": k[1], "count": n, "classification": KNOWN.get(k, "unknown")}
            for k, n in sorted(counts.items())
        ],
        "adc_channels_zero_based": dict(sorted(adc_channels.items())),
        "auxiliary_channels": dict(sorted(auxiliary_channels.items())),
        "unknown_frame_headers": unknown[:20],
        "fully_aligned_after_prefix": pos == len(data),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out")
    a = parser.parse_args()
    result = [analyze(p) for p in a.files]
    output = json.dumps(result, indent=2, ensure_ascii=False)
    print(output)
    if a.out:
        Path(a.out).write_text(output, encoding="utf-8")
