"""Synthetic-only proof of original 0x3100 VALUES triggers, not real PCAP."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import struct

import pytest

from ..core.original_values_3100_timeline import (
    PARAM, MAX_FRAME, scan_original_values_3100,
)


def frame(kind, body: bytes):
    size = 8 + len(body)
    assert size % 4 == 0
    return struct.pack("<II", kind, size) + body


def param(*records):
    body = bytearray(16)
    body.extend(struct.pack("<I", len(records)))
    for addr, data in records:
        assert len(data) and len(data) % 4 == 0
        body.extend(struct.pack("<I", (len(data) // 2) << 16 | addr))
        body.extend(data)
    return frame(PARAM, bytes(body))


def aux_frame():
    records = tuple((0x2000 + 0x200 * i, bytes(580)) for i in range(8))
    value = param(*records)
    assert len(value) == 4700
    return value


def make_raw(tmp_path, parts, *, tail=b""):
    binary = b"".join(parts) + tail
    source = tmp_path / "incoming.raw"
    source.write_bytes(binary)
    return source, dict(
        expected_sha256=sha256(binary).hexdigest(),
        expected_raw_bytes=len(binary),
        expected_frames=len(parts),
        expected_aux=sum(len(p) == 4700 for p in parts),
        expected_ticks=sum(PARAM == struct.unpack_from("<I", p)[0]
                           and b"\x00\x31" in p for p in parts),
        expected_tail_bytes=len(tail),
    )


def test_real_source_values_triggers_not_aux_and_native_window_bounds(tmp_path):
    parts = [
        frame(1, bytes(256)), aux_frame(),
        param((0x3100, b"\x01\x02\x03\x04")),
        param((0x3100, b"\x05\x06\x07\x08")),
        aux_frame(), param((0x3100, b"\x09\x0a\x0b\x0c")),
        frame(0xDEADBEEF, bytes(12)),
    ]
    src, config = make_raw(tmp_path, parts, tail=b"end")
    # A stopped source may have a short trailing fragment.
    events = scan_original_values_3100(
        src, **config, ranges=[(1, 0, 2), (2, 2, 3)])
    assert [e["source_tick_index"] for e in events[1]] == [0, 1]
    assert [e["frame_index"] for e in events[1]] == [2, 3]
    assert [e["latest_earlier_aux_index"] for e in events[1]] == [0, 0]
    assert events[2][0]["latest_earlier_aux_index"] == 1
    assert events[2][0]["register_bytes_hex"] == "090a0b0c"
    assert events[1][0]["register_payload_sha256"] == sha256(
        b"\x01\x02\x03\x04").hexdigest()


def test_aux_does_not_create_phantom_original_values_rows(tmp_path):
    parts = [frame(1,bytes(256)),aux_frame(),aux_frame()]
    src,config=make_raw(tmp_path,parts)
    events=scan_original_values_3100(src,**config,ranges=[(1,0,0)])
    assert events == {1:[]}
    assert config["expected_aux"] == 2 and config["expected_ticks"] == 0


@pytest.mark.parametrize("mutator", [
    lambda p,a: p.write_bytes(p.read_bytes()[:-1] + b"X"),
    lambda p,a: a.update(expected_ticks=a["expected_ticks"] + 1),
    lambda p,a: a.update(expected_aux=a["expected_aux"] + 1),
    lambda p,a: a.update(expected_tail_bytes=0),
    lambda p,a: a.update(expected_frames=a["expected_frames"] + 1),
    lambda p,a: a.update(expected_sha256="0" * 64),
])
def test_tampered_raw_or_mismatched_go_evidence_rejected(tmp_path,mutator):
    parts=[frame(1,bytes(256)),aux_frame(),param((0x3100,bytes(4)))]
    src,args=make_raw(tmp_path,parts,tail=b"X")
    mutator(src,args)
    with pytest.raises(ValueError):
        scan_original_values_3100(src,**args,ranges=[(1,0,1)])


def test_malformed_parameter_block_and_overwide_source_window_rejected(tmp_path):
    good=param((0x3100,bytes(4)))
    broken=good[:28] + struct.pack("<I", 4 << 16 | 0x3FFF) + bytes(4)
    src,args=make_raw(tmp_path,[frame(1,bytes(256)),broken])
    args["expected_ticks"]=1
    with pytest.raises(ValueError,match="register block"):
        scan_original_values_3100(src,**args,ranges=[(1,0,1)])
    src,args=make_raw(tmp_path,[frame(1,bytes(256)),good])
    with pytest.raises(ValueError,match="invalid tick bounds"):
        scan_original_values_3100(src,**args,ranges=[(1,1,0)])


def test_original_3100_payload_happens_before_first_aux(tmp_path):
    parts=[frame(1,bytes(256)),param((0x3100,b"1234")),aux_frame()]
    src,config=make_raw(tmp_path,parts)
    events=scan_original_values_3100(src,**config,ranges=[(1,0,1)])
    assert events[1][0]["latest_earlier_aux_index"] is None
