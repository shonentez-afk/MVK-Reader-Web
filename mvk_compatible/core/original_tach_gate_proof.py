"""Independently replay a local TACH admission journal against immutable RAW."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import struct

SOURCE_TACH_GATE_NAME = "SOURCE_ORIGINAL_TACH_FRAME_GATE.dat"
SOURCE_TACH_GATE_SCHEMA = "MVK_SOURCE_TACH_FRAME_GATE_V1_LE64"
TACH = 0xFF8001AC
RATES = frozenset((512, 2048, 8192, 32768, 65536))
RECORD = struct.Struct("<QQIIBB6s32s")


class OriginalTachGateReader:
    def __init__(self, path, *, expected_sha256, expected_records, expected_frames):
        self.path = Path(path)
        if (type(expected_records) is not int or
                not 0 <= expected_records <= min(8_000_000, expected_frames) or
                not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or
                any(c not in "0123456789abcdef" for c in expected_sha256) or
                self.path.is_symlink() or not self.path.is_file() or
                self.path.stat().st_size != expected_records * RECORD.size):
            raise ValueError("Original TACH gate: invalid size/count/SHA")
        self.expected_sha256 = expected_sha256
        self.expected_records = expected_records
        self.count = 0
        self.last_index = 0
        self.digest = sha256()
        self.file = None

    def __enter__(self):
        self.file = self.path.open("rb")
        return self

    def __exit__(self, *_):
        if self.file is not None:
            self.file.close()
            self.file = None

    def consume(self, *, frame_index, frame):
        if self.file is None or len(frame) < 28 or len(frame) % 4:
            raise ValueError("Original TACH gate: invalid frame/reader")
        raw = self.file.read(RECORD.size)
        if len(raw) != RECORD.size:
            raise ValueError("Original TACH gate: missing admission record")
        index, epoch, selected, rate, channel, flags, reserved, digest = RECORD.unpack(raw)
        typ, length = struct.unpack_from("<II", frame)
        wire_channel, wire_rate = struct.unpack_from("<II", frame, 20)
        frozen = bool(flags & 1)
        admitted = bool(flags & 2)
        if (typ != TACH or length != len(frame) or index != frame_index or
                index <= self.last_index or epoch != 1 or selected not in RATES or
                rate != wire_rate or channel not in (8, 9) or channel != wire_channel or
                flags & ~3 or reserved != bytes(6) or digest != sha256(frame).digest() or
                admitted != (len(frame) > 28 and not frozen and rate == selected)):
            raise ValueError("Original TACH gate: admission contradicts RAW/local gate or socket epoch")
        self.digest.update(raw)
        self.count += 1
        self.last_index = index
        return channel - 8, admitted

    def finish(self):
        if (self.file is None or self.file.read(1) or self.count != self.expected_records or
                self.digest.hexdigest() != self.expected_sha256):
            raise ValueError("Original TACH gate: count/SHA/extra record mismatch")


def set_latch(data, valid, channel, value):
    addr = (0x30fe, 0x31fe)[channel]
    data[addr * 2:(addr + 2) * 2] = value.to_bytes(4, "little")
    valid[addr:addr + 2] = b"\x01\x01"


def apply_tach_bytes(data, valid, last, channel, payload):
    # Independently compare adjacent bytes, rather than copying the Go loop.
    changed = False
    for byte in payload:
        changed = changed or byte != last[channel]
        last[channel] = byte
    if changed:
        set_latch(data, valid, channel, 1)
