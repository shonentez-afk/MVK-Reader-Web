#!/usr/bin/env python3
"""Offline structural check of 4700-byte MVK frames (no device connection)."""
import argparse
import json
import struct
from pathlib import Path

ADC = bytes.fromhex("dc0a80ff")
AUX = bytes.fromhex("0d0c80ff")

def inspect(filename):
    raw = Path(filename).read_bytes()
    pos = raw.find(ADC)
    if pos < 0:
        raise ValueError("No ADC marker")
    frames = []
    while pos < len(raw):
        if pos + 8 > len(raw):
            raise ValueError("Incomplete frame header")
        size = struct.unpack_from("<I", raw, pos + 4)[0]
        if size < 8 or pos + size > len(raw):
            raise ValueError("Invalid message size at %d" % pos)
        if raw[pos:pos+4] == AUX and size == 4700:
            channel_tags = [struct.unpack_from("<I", raw, pos + 28 + ch * 584)[0]
                            for ch in range(8)]
            rows = [struct.unpack_from("<145f", raw, pos + 32 + ch * 584)
                    for ch in range(8)]
            frames.append({"offset":pos, "tags": channel_tags,
                "first_float": [row[0] for row in rows],
                "nonzero_counts": [sum(x != 0.0 for x in row) for row in rows]})
        pos += size
    if not frames:
        raise ValueError("No 4700 byte frames")
    tag_expected = [19013632 + 512 * i for i in range(8)]
    return {"file":Path(filename).name, "count":len(frames),
            "shape":"28 header + 8 x (4-byte tag + 145 float32)",
            "tag_expected":tag_expected,
            "tag_match_all":all(x["tags"] == tag_expected for x in frames),
            "first_frame":frames[0]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("raw", nargs="+")
    p.add_argument("--out")
    a = p.parse_args()
    output=json.dumps([inspect(x) for x in a.raw],indent=2,ensure_ascii=False)
    print(output)
    if a.out: Path(a.out).write_text(output,encoding="utf-8")
if __name__ == "__main__":
    main()
