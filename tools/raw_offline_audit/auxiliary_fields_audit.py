"""Offline field inspection of saved MVK RAW frames. Does not use network."""
import sys
import struct
from collections import Counter
from pathlib import Path

for filename in sys.argv[1:]:
    payload = Path(filename).read_bytes()
    position = payload.find(bytes.fromhex('dc0a80ff'))
    totals = Counter()
    while position >= 0 and position + 8 <= len(payload):
        marker, length = struct.unpack_from('<II', payload, position)
        if length < 8 or position + length > len(payload):
            raise ValueError('Invalid frame length at %s' % position)
        totals[length] += 1
        position += length
    print(Path(filename).name, dict(totals), 'fully parsed:', position == len(payload))
