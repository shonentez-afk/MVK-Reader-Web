"""Offline inventory of MVK auxiliary 44/160 byte frames (RAW only)."""
import struct
import collections
import sys
from pathlib import Path


def inspect(data):
    pos = data.find(bytes.fromhex('dc0a80ff'))
    if pos < 0:
        raise ValueError('ADC marker missing')
    counts = collections.Counter()
    subtypes = collections.Counter()
    while pos + 8 <= len(data):
        marker, length = struct.unpack_from('<II', data, pos)
        if length < 8 or pos + length > len(data):
            raise ValueError('Bad frame length at byte %d' % pos)
        if marker == 0xff800c0d and length in (44, 160):
            counts[length] += 1
            if length == 160:
                subtypes[struct.unpack_from('<I', data, pos+28)[0]] += 1
        pos += length
    return counts, subtypes


if __name__ == '__main__':
    for file in sys.argv[1:]:
        counts, subtypes = inspect(Path(file).read_bytes())
        print(Path(file).name, dict(counts), {hex(k):v for k,v in sorted(subtypes.items())})
