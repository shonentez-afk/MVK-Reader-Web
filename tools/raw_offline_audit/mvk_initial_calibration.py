"""Offline decode of MVK TCP/10230 initial VAST_MVK calibration metadata."""
import json
import struct
import sys
from pathlib import Path

HEADER_PREFIX = 33064
GAIN_OFFSET = 836
SENS_OFFSET = 812
STRIDE = 512

def decode(data):
    if len(data) < HEADER_PREFIX or data[24:32] != b"VAST_MVK":
        raise ValueError("Expected initial MVK header with VAST_MVK at +24")
    channels = []
    for i in range(8):
        s = struct.unpack_from("<f", data, SENS_OFFSET + i * STRIDE)[0]
        g = struct.unpack_from("<f", data, GAIN_OFFSET + i * STRIDE)[0]
        if not (0 < s < 1 and 0 < g < 1e6):
            raise ValueError("Implausible calibration")
        channels.append({"adc": i+1, "sensitivity_v_per_ms2": s,
                         "raw_to_acceleration_gain": g})
    return {"signature": "VAST_MVK", "channels": channels}

class StreamingHeaderDecoder:
    """Accumulate a fragmented initial header. No socket access."""
    def __init__(self):
        self.buffer = bytearray()
        self.calibration = None
        self.remaining_bytes = bytearray()

    def feed(self, chunk):
        if self.calibration is not None:
            self.remaining_bytes.extend(chunk)
            return self.calibration
        needed = HEADER_PREFIX - len(self.buffer)
        self.buffer.extend(chunk[:needed])
        self.remaining_bytes.extend(chunk[needed:])
        if len(self.buffer) < HEADER_PREFIX:
            return None
        self.calibration = decode(self.buffer)
        self.buffer.clear()
        return self.calibration


if __name__ == "__main__":
    for filename in sys.argv[1:]:
        with Path(filename).open("rb") as f:
            result = decode(f.read(HEADER_PREFIX))
        print(json.dumps({"file": Path(filename).name, **result}, indent=2))
