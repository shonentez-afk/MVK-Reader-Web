"""Offline ADC2 waveform peak/RMS audit aligned to AUX160 transitions.

Read an existing MVK RAW. No device access. Stdlib only.
"""
import argparse
import json
import math
import struct
from pathlib import Path

FS = 65536
ADC_CHANNEL = 1
GAIN_OFFSET = 836 + 512 * ADC_CHANNEL

def analyze(path):
    data = Path(path).read_bytes()
    if len(data) < 33064 or data[24:32] != b"VAST_MVK":
        raise ValueError("Missing complete VAST_MVK header")
    gain = struct.unpack_from("<f", data, GAIN_OFFSET)[0]
    samples = []
    events = []
    prior_descriptor = None
    position = 33064
    while position + 8 <= len(data):
        marker, size = struct.unpack_from("<II", data, position)
        if size < 8 or position + size > len(data):
            raise ValueError("Malformed frame at offset %d" % position)
        if (marker, size) == (0xff800adc, 1052):
            ch = struct.unpack_from("<I", data, position+20)[0]
            if ch == ADC_CHANNEL:
                samples.extend(struct.unpack_from("<256f", data, position+28))
        elif (marker, size) == (0xff800c0d, 160):
            tag = struct.unpack_from("<I", data, position+28)[0]
            if tag == 0x00402330:
                current, descriptor, reference, extra = struct.unpack_from(
                    "<fIff", data, position+80)
                if prior_descriptor is not None and descriptor != prior_descriptor:
                    events.append({"seconds_by_adc_samples":len(samples)/FS,
                                   "previous_descriptor":hex(prior_descriptor),
                                   "descriptor":hex(descriptor),
                                   "current":current,
                                   "reference":reference,
                                   "extra_float32":extra})
                prior_descriptor = descriptor
        position += size

    results = {}
    for duration in (0.01, 0.05, 0.1, 0.25, 0.5, 1.0):
        width = round(FS * duration)
        values = []
        for start in range(0,len(samples)-width+1,width):
            segment = samples[start:start+width]
            avg = sum(segment)/width
            centered = [x-avg for x in segment]
            rms = math.sqrt(sum(x*x for x in centered)/width)
            if rms:
                values.append(max(abs(x) for x in centered)/rms)
        results[str(duration)] = max(values) if values else None
    return {"file":Path(path).name,"fs_hz":FS,"gain":gain,
            "samples":len(samples),"maximum_crest_by_window_s":results,
            "aux160_transitions":events}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("raw",nargs="+")
    for filename in parser.parse_args().raw:
        print(json.dumps(analyze(filename),ensure_ascii=False,indent=2))
