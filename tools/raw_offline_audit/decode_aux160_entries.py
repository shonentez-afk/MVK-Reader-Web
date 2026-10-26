"""Decode four 16-byte AUX160 numeric entries without assuming descriptor meaning."""
import struct

CHANNEL_IDS = {0x00402130 + 512 * i: i for i in range(8)}
HEADER_BASE = 17296
HEADER_CHANNEL_STRIDE = 1024
ENTRY_OFFSETS = (32, 48, 64, 80)
HEADER_ENTRY_OFFSETS = (-8, 8, 24, 40)

def inspect_channel(frame160, header33064):
    if len(frame160) != 160 or len(header33064) < 33064:
        raise ValueError("Incorrect frame or header size")
    channel_tag = struct.unpack_from("<I", frame160, 28)[0]
    if channel_tag not in CHANNEL_IDS:
        raise ValueError("Not an ADC channel AUX160 frame")
    c = CHANNEL_IDS[channel_tag]
    base = HEADER_BASE + c * HEADER_CHANNEL_STRIDE
    results = []
    for i, offset in enumerate(ENTRY_OFFSETS):
        current, desc, reference, reserved = struct.unpack_from("<fIfI", frame160, offset)
        orig = struct.unpack_from("<fIfI", header33064, base + HEADER_ENTRY_OFFSETS[i])
        results.append({"entry":i,"current":current, "descriptor":desc,
                        "reference":reference,"reserved":reserved,
                        "descriptor_matches_header":desc==orig[1],
                        "reference_matches_header":struct.pack("<f", reference)==struct.pack("<f", orig[2]),
                        "reserved_matches_header":reserved==orig[3],
                        "header_initial_value":orig[0]})
    return {"adc":c+1,"entries":results}
