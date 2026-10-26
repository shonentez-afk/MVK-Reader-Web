"""Offline verification of 4700-byte MVK summary against documented layout."""
import argparse
import json
import math
import struct
from pathlib import Path

def inspect(path):
    raw = Path(path).read_bytes()
    cursor = raw.find(bytes.fromhex("dc0a80ff"))
    if cursor < 0:
        raise ValueError("No ADC marker")
    rows = []
    while cursor < len(raw):
        if cursor + 8 > len(raw):
            raise ValueError("Truncated header")
        marker, length = struct.unpack_from("<II", raw, cursor)
        if length < 8 or cursor + length > len(raw):
            raise ValueError("Invalid frame size")
        if marker == 0xff800c0d and length == 4700:
            for channel in range(8):
                base = cursor + 28 + channel * 584
                tag = struct.unpack_from("<I", raw, base)[0]
                values = struct.unpack_from("<144f", raw, base + 4)
                status = struct.unpack_from("<I", raw, base + 580)[0]
                rows.append((channel, tag, values, status))
        cursor += length
    comparisons = []
    zero_padding = True
    zero_matching = True
    for channel, tag, v, status in rows:
        zero_padding &= all(v[i] == 0 for i in
                            list(range(44,46)) + list(range(72,80)) +
                            list(range(104,112)) + list(range(136,144)))
        for i in range(24):
            rms, peak, peak_to_peak = v[48+i], v[80+i], v[112+i]
            if rms == 0:
                zero_matching &= peak == 0 and peak_to_peak == 0
            else:
                comparisons.append((abs(peak - math.sqrt(2)*rms) /
                                   max(abs(peak),1e-30),
                                   abs(peak_to_peak-2*peak) /
                                   max(abs(peak_to_peak),1e-30)))
    return {"file":Path(path).name,"channel_records":len(rows),
        "zero_padding_all":zero_padding,"zero_rms_pairs_match":zero_matching,
        "nonzero_pairs":len(comparisons),
        "peak_over_rms_max_relative_error":max((x[0] for x in comparisons),default=None),
        "peak_to_peak_max_relative_error":max((x[1] for x in comparisons),default=None),
        "statuses_uint32":sorted(set(status for _,_,_,status in rows)),
        "all_tags_expected":all(tag == 19013632+512*ch for ch,tag,_,_ in rows)}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw",nargs="+")
    args=p.parse_args()
    for path in args.raw:
        print(json.dumps(inspect(path),indent=2))
