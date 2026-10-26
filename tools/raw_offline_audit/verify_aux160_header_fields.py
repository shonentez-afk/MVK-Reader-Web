"""Verify AUX160 fixed fields originate from VAST_MVK initial metadata.
Use captured RAW only; no network operations.
"""
import argparse
import json
import struct
from pathlib import Path

FIELDS = (40, 56, 72, 88)
HEADER_BASE = 17296
HEADER_STRIDE = 1024
MARKER = b"\xdc\x0a\x80\xff"


def verify(raw):
    first = raw.find(MARKER)
    if first < 33064:
        raise ValueError("Missing complete VAST_MVK metadata")
    header = raw[:first]
    if header[24:32] != b"VAST_MVK":
        raise ValueError("VAST_MVK signature not at offset 24")
    positions = {i: [HEADER_BASE + HEADER_STRIDE*i+16*j
                     for j in range(4)] for i in range(8)}
    mismatches = []
    counts = [0]*8
    cursor = first
    while cursor + 8 <= len(raw):
        marker, size = struct.unpack_from("<II", raw, cursor)
        if not 8 <= size <= 100000 or cursor+size > len(raw):
            raise ValueError("Bad frame at %d" % cursor)
        if marker == 0xff800c0d and size == 160:
            tag = struct.unpack_from("<I", raw, cursor+28)[0]
            delta = tag - 0x00402130
            if delta % 512 == 0 and 0 <= delta//512 < 8:
                channel = delta//512
                counts[channel] += 1
                for j,off in enumerate(FIELDS):
                    src = raw[cursor+off:cursor+off+4]
                    ref = header[positions[channel][j]:positions[channel][j]+4]
                    if src != ref:
                        mismatches.append({"channel":channel+1,
                            "offset":off,"frame":counts[channel]})
        cursor += size
    return {"aux160_by_channel":counts,
            "compared_fields":sum(counts)*len(FIELDS),
            "mismatch_count":len(mismatches),
            "mismatches":mismatches[:20]}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("raw",nargs="+")
    for path in parser.parse_args().raw:
        report=verify(Path(path).read_bytes())
        print(json.dumps({"file":Path(path).name,**report},indent=2))
