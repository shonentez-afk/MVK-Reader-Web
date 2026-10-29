#!/usr/bin/env python3
"""Independent QA only: compare every labeled Go AUX field to raw frame float32.

Usage: python check_calculated_against_raw.py PATH_TO_incoming.raw PATH_TO_aux4700.jsonl
No network, no files modified, original captures are not included in release.
"""
import json
import struct
import sys
from pathlib import Path


def check(raw_path, jsonl_path):
    data = Path(raw_path).read_bytes()
    records = [json.loads(s) for s in Path(jsonl_path).read_text(encoding='utf-8').splitlines() if s]
    offset = 0
    all_checks = 0
    updates = 0
    while offset + 8 <= len(data):
        kind, size = struct.unpack_from('<II', data, offset)
        if size < 8 or size > 0x20000 or offset + size > len(data):
            break
        if kind == 0xFF800C0D and size == 4700:
            for adc in range(8):
                row = records[updates*8+adc]
                base = offset + 28 + adc*584
                desc = struct.unpack_from('<I',data,base)[0]
                assert desc == (0x122<<16) | (0x2000 + adc*0x200), (updates,adc,hex(desc))
                values = struct.unpack_from('<144f',data,base+4)
                status = struct.unpack_from('<I',data,base+4+576)[0]
                # The four labeled groups map to native R4 register-word offsets:
                # 0x0002, 0x0060, 0x00A0, 0x00E0, divided by 2 for float32 indices.
                cases = [
                    ('third_octave_acceleration_rms', values[1:1+43]),
                    ('band_rms', values[48:48+24]),
                    ('band_peak_equiv', values[80:80+24]),
                    ('band_span_equiv', values[112:112+24]),
                ]
                for name, expected in cases:
                    actual=row[name]
                    if len(actual)!=len(expected): raise AssertionError((name,len(actual),len(expected)))
                    for i,(a,b) in enumerate(zip(actual,expected)):
                        if a!=b:raise AssertionError((updates,adc,name,i,a,b))
                        all_checks += 1
                if row['status_raw']!=status:raise AssertionError((updates,adc,'status',row['status_raw'],status))
                all_checks+=1
            updates+=1
        offset+=size
    assert len(records) == updates*8,(len(records),updates)
    print(f'PASS: {updates} AUX4700 x 8 channels, {all_checks} exact fields vs raw; trailing bytes={len(data)-offset}')
    return updates,all_checks

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: check_calculated_against_raw.py incoming.raw aux4700.jsonl')
    check(*sys.argv[1:])
