"""One integrated original source PARAM FreezeUpdate / VALUES post-Stop acceptance.

Provenance: private IDP, Delphi _Unit125.pas and SQLite function index.
Synthetic bytes only. No industrial TCP, no device command, no private files.
"""
from hashlib import sha256
import json
from pathlib import Path
from struct import pack

import pytest

from ..core.original_mode2_received_frames import (
    OriginalSourceReadFramer, TYPE_REGISTERS,
)
from ..core.original_param_gate_proof import (
    SOURCE_PARAM_GATE_NAME, SOURCE_PARAM_GATE_SCHEMA,
)
from ..core.original_values_3100_timeline import scan_original_values_3100


def param_frame(*blocks):
    """8-byte type/length + five u32 header words + address/data descriptors."""
    raw = bytearray(pack("<7I", TYPE_REGISTERS, 0, 0, 0, 0, 0, len(blocks)))
    for addr, payload in blocks:
        assert len(payload) and len(payload) % 4 == 0
        raw.extend(pack("<I", ((len(payload) // 2) << 16) | addr))
        raw.extend(payload)
    raw[4:8] = pack("<I", len(raw))
    return bytes(raw)


def aux4700():
    return param_frame(*(
        (0x2000 + channel * 0x200, bytes(580))
        for channel in range(8)
    ))


def test_original_task2_valid_28byte_empty_param_keeps_stage0():
    reader = OriginalSourceReadFramer()
    empty = param_frame()
    assert len(empty) == 28
    assert reader.feed(empty[:7]) == ()
    event, = reader.feed(empty[7:])
    assert event.kind == "PARAM"
    assert not event.processed
    assert event.register_block_count == 0
    assert event.source_stage == 0
    assert reader.register_frames_with_blocks == 0
    status = param_frame((0x1006, pack("<I", 0)))
    event, = reader.feed(status)
    assert event.processed
    assert event.source_stage == 1
    assert reader.register_frames_with_blocks == 1


def _record(frame, index, frozen):
    count = int.from_bytes(frame[24:28], "little")
    pos, found = 28, False
    for _ in range(count):
        desc = int.from_bytes(frame[pos:pos+4], "little")
        pos += 4
        addr, words = desc & 0xFFFF, desc >> 16
        if addr == 0x3100:
            found = True
        pos += words*2
    assert pos == len(frame)
    return {
        "schema": SOURCE_PARAM_GATE_SCHEMA,
        "frame_index_one_based": index,
        "frame_sha256": sha256(frame).hexdigest(),
        "descriptor_count": count,
        "freeze_update": frozen,
        "is_aux4700": len(frame) == 4700,
        "contains_values_3100": found,
    }


def test_original_go_param_gate_raw_replay_frozen_values_skip_and_sha(tmp_path):
    first = param_frame()
    frozen_values = param_frame((0x3100, bytes.fromhex("deadbeef")))
    frozen_aux = aux4700()
    accepted_aux = aux4700()
    accepted_values = param_frame((0x3100, bytes.fromhex("9abccdef")))
    frames = [first, frozen_values, frozen_aux, accepted_aux, accepted_values]
    raw = b"".join(frames)
    raw_path = tmp_path / "incoming.raw"
    raw_path.write_bytes(raw)
    records = b"".join((
        json.dumps(_record(frame, i+1, i in (1,2)),
                   sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for i, frame in enumerate(frames)
    ))
    gate = tmp_path / SOURCE_PARAM_GATE_NAME
    gate.write_bytes(records)
    kwargs = {
        "expected_sha256": sha256(raw).hexdigest(),
        "expected_raw_bytes": len(raw),
        "expected_frames": len(frames),
        "expected_aux": 1,
        "expected_ticks": 1,
        "expected_tail_bytes": 0,
        "ranges": [(1, 0, 1)],
        "param_gate_path": gate,
        "expected_param_gate_sha256": sha256(records).hexdigest(),
        "expected_param_gate_records": len(frames),
        "expected_frozen_param_frames": 2,
        "expected_frozen_aux": 1,
        "expected_frozen_values": 1,
    }
    verified = scan_original_values_3100(raw_path, **kwargs)
    assert set(verified) == {1}
    assert len(verified[1]) == 1
    accepted, = verified[1]
    assert accepted["source_tick_index"] == 0
    assert accepted["frame_index"] == 4
    assert accepted["register_bytes_hex"] == "9abccdef"
    assert accepted["latest_earlier_aux_index"] == 0
    # Without a genuine per-PARAM freeze record, RAW alone cannot know
    # that the earlier 0x3100 was suppressed by original FreezeUpdate.
    with pytest.raises(ValueError, match="Freeze requires verified PARAM gate"):
        scan_original_values_3100(raw_path, **{
            **kwargs, "param_gate_path": None,
            "expected_param_gate_sha256": None,
            "expected_param_gate_records": 0,
        })
    # A forged gate cannot silently transform frozen register data into
    # accepted originals, even if its JSON structure otherwise parses.
    tampered = records.replace(b'"freeze_update":true',
                               b'"freeze_update":false', 1)
    gate.write_bytes(tampered)
    with pytest.raises(ValueError, match="extra entries/count/SHA mismatch"):
        scan_original_values_3100(raw_path, **kwargs)
    gate.write_bytes(records)
    # Corrupt a recorded frame checksum while keeping an internally
    # consistent file SHA; the independent RAW check must still refuse.
    data = records.decode().splitlines()
    row = json.loads(data[1])
    row["frame_sha256"] = "0"*64
    data[1] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    mutated = ("\n".join(data) + "\n").encode()
    gate.write_bytes(mutated)
    with pytest.raises(ValueError, match="event contradicts RAW"):
        scan_original_values_3100(raw_path, **{
            **kwargs, "expected_param_gate_sha256": sha256(mutated).hexdigest()
        })
