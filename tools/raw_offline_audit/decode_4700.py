"""Standalone offline decoder for MVK 4700-byte summary frames.
No networking, device control, or Reader Web startup.
"""
import argparse
import json
import math
import struct
from pathlib import Path

MARKER = bytes.fromhex("0d0c80ff")
FRAME_SIZE = 4700
CHANNELS = 8
RECORD_SIZE = 584
EXPECTED_TAG0 = 19013632
STATUS_FLAGS = {0: 'input_overload', 4: 'buffer_fs16_not_ready', 5: 'buffer_fs64_not_ready', 6: 'buffer_fs512_not_ready', 10: 'sensor_dc_above_max', 11: 'sensor_dc_at_or_below_min'}
PADDING = tuple(list(range(44, 46)) + list(range(72, 80)) +
                list(range(104, 112)) + list(range(136, 144)))


def decode_frame(frame):
    if len(frame) != FRAME_SIZE:
        raise ValueError("Expected 4700 bytes")
    if frame[:4] != MARKER or struct.unpack_from("<I", frame, 4)[0] != FRAME_SIZE:
        raise ValueError("Not an MVK 4700-byte frame")
    channels = []
    for index in range(CHANNELS):
        base = 28 + index * RECORD_SIZE
        tag = struct.unpack_from("<I", frame, base)[0]
        if tag != EXPECTED_TAG0 + 512 * index:
            raise ValueError("Unexpected channel tag at index %d" % index)
        values = struct.unpack_from("<144f", frame, base + 4)
        status = struct.unpack_from("<I", frame, base + 580)[0]
        if not all(math.isfinite(x) for x in values):
            raise ValueError("Non-finite float32 in channel %d" % index)
        ratios = []
        for i in range(24):
            rms, peak, span = values[48+i], values[80+i], values[112+i]
            ratios.append({
                "band_index": i, "rms": rms, "peak": peak, "span": span,
                "peak_rel_error": abs(peak-math.sqrt(2)*rms)/max(abs(peak), 1e-30),
                "span_rel_error": abs(span-2*peak)/max(abs(span), 1e-30)
            })
        channels.append({
            "adc": index + 1,
            "tag": tag,
            "voltage_candidate": values[0],
            "third_octave_candidate": list(values[1:44]),
            "crest_candidate": values[46],
            "broadband_rms_candidate": values[47],
            "bands": ratios,
            "status_bits_uint32": status,
            "status_active_flags": [name for bit, name in STATUS_FLAGS.items() if status & (1 << bit)],
            "status_unknown_mask": status & ~sum(1 << bit for bit in STATUS_FLAGS),
            "zero_padding": all(values[i] == 0 for i in PADDING)
        })
    return {"frame_counter": struct.unpack_from("<I", frame, 20)[0],
            "frame_size": FRAME_SIZE, "channels": channels,
            "provisional_mapping": True}


def iter_frames(raw):
    start = raw.find(bytes.fromhex("dc0a80ff"))
    if start < 0:
        raise ValueError("No ADC marker")
    position = start
    while position < len(raw):
        if position + 8 > len(raw):
            raise ValueError("Truncated frame header")
        size = struct.unpack_from("<I", raw, position + 4)[0]
        if not 8 <= size <= 100000 or position + size > len(raw):
            raise ValueError("Bad frame length at %d" % position)
        if raw[position:position+4] == MARKER and size == FRAME_SIZE:
            yield decode_frame(raw[position:position+size])
        position += size


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw", help="Saved RAW capture, not a network address")
    p.add_argument("--out", help="Local JSON path")
    a = p.parse_args()
    frames = list(iter_frames(Path(a.raw).read_bytes()))
    report = {"file": Path(a.raw).name, "frames": len(frames),
              "records": len(frames)*8, "data": frames}
    result = json.dumps(report, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(result, encoding="utf-8")
        print("Wrote", a.out)
    else:
        print(result)


if __name__ == "__main__":
    main()
