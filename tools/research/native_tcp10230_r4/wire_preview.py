"""OFFLINE ONLY: pure reconstruction of an observed MVKView rate-set frame.

Contains NO socket functionality, and does not encode arbitrary config/flash
writes. The 36-byte sample-rate command was observed in a real prior capture.
Original IDR _Unit125.pas 0x00809364/0x0080937C and 0x00807F45.
"""
import struct

PARAM=0xFF800C0D
RATES=frozenset((512,2048,8192,32768,65536))

def rate_message_preview(sample_rate):
    if sample_rate not in RATES:raise ValueError('unverified sample rate')
    # 8-dword header, 1 register descriptor and 1 dword payload.
    return struct.pack('<9I',PARAM,36,0,0,0,0,1,0x0002000E,sample_rate)

def parse_rate_message(message):
    if len(message)!=36:raise ValueError('not 36 bytes')
    m=struct.unpack('<9I',message)
    if m[:8]!=(PARAM,36,0,0,0,0,1,0x0002000E):raise ValueError('not an MVKView rate command')
    if m[8] not in RATES:raise ValueError('invalid sample rate')
    return m[8]
