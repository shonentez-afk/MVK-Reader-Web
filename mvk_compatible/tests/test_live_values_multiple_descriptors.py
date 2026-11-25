"""Preserve every WriteValues row and prefix, even inside one PARAM frame."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from struct import pack
from types import SimpleNamespace

import pytest

from ..core.original_live_values_proof import AUDIT, verify_original_live_values
from ..core.original_local_tach_latch import SCHEMA as TACH_GATE_SCHEMA, TACH_TYPE
from ..core.original_values_3100_timeline import scan_original_values_3100
from ..core.original_source_values_tick_acceptance import verify_source_values_tick_files
from .test_mode2_original_param_freeze_gate_e2e import _record, param_frame
from .test_original_source_values_tick_acceptance import synthetic_tick
from .test_stage111z31ei_local_tach import replay


def _write_jsonl(path, rows):
    content = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
    path.write_bytes(content)
    return sha256(content).hexdigest()


def test_raw_replay_multiple_descriptor_prefixes_and_tach_reset(tmp_path):
    tach = pack("<7I", TACH_TYPE, 32, 0, 0, 0, 8, 65536) + b"\x01\x00\x00\x01"
    accepted = param_frame((0x2002, pack("<f", 1.5)), (0x3100, b"abcd"),
                           (0x2002, pack("<f", 2.5)), (0x3100, b"efgh"),
                           (0x2002, pack("<f", 3.5)))
    frozen = param_frame(*[(0x3100, b"skip")] * 4)
    raw = tach + accepted + frozen
    raw_file = tmp_path / "incoming.raw"
    raw_file.write_bytes(raw)
    tach_gate = tmp_path / "tach.jsonl"
    tach_gate_sha = _write_jsonl(tach_gate, [
        dict(schema=TACH_GATE_SCHEMA, frame_index_one_based=1,
             frame_sha256=sha256(tach).hexdigest(), channel=9,
             selected_rate_hz=65536, freeze_update=False,
             source_receive_gate_accepted=True)
    ])
    param_gate = tmp_path / "param.jsonl"
    records = [_record(accepted, 2, False), _record(frozen, 3, True)]
    for row, count in zip(records, (2, 4)):
        row["source_values_3100_descriptor_count"] = count
    param_gate_sha = _write_jsonl(param_gate, records)
    kwargs = dict(expected_sha256=sha256(raw).hexdigest(), expected_raw_bytes=len(raw),
                  expected_frames=3, expected_aux=0, expected_ticks=2, expected_tail_bytes=0,
                  ranges=[(1, 0, 2)], capture_register_prefix=True,
                  param_gate_path=param_gate, expected_param_gate_sha256=param_gate_sha,
                  expected_param_gate_records=2, expected_frozen_param_frames=1,
                  expected_frozen_values=4, tach_gate_path=tach_gate,
                  expected_tach_gate_sha256=tach_gate_sha, expected_tach_gate_records=1)
    before, after = scan_original_values_3100(raw_file, **kwargs)[1]
    assert (before["frame_index"], after["frame_index"]) == (1, 1)
    assert (before["source_param_descriptor_index"], after["source_param_descriptor_index"]) == (1, 3)
    assert (before["source_tick_index"], after["source_tick_index"]) == (0, 1)
    assert [r["_register_prefix"].dword_hex(0x2002, current=True) for r in (before, after)] == [
        pack("<f", 1.5).hex(), pack("<f", 2.5).hex()
    ]
    assert [r["_register_prefix"].dword_hex(0x30FE) for r in (before, after)] == [
        "01000000", "00000000"
    ]
    assert [r["register_bytes_hex"] for r in (before, after)] == [b"abcd".hex(), b"efgh".hex()]
    # A forged or legacy boolean-only count cannot attest to repeated triggers.
    for value in (1, None, True):
        if value is None:
            records[0].pop("source_values_3100_descriptor_count", None)
        else:
            records[0]["source_values_3100_descriptor_count"] = value
        kwargs["expected_param_gate_sha256"] = _write_jsonl(param_gate, records)
        with pytest.raises(ValueError, match="trigger descriptor count contradicts RAW"):
            scan_original_values_3100(raw_file, **kwargs)


def test_two_rows_in_one_frame_can_exceed_total_frame_count(tmp_path):
    raw = param_frame((0x3100, b"one!"), (0x3100, b"two!"))
    source = tmp_path / "incoming.raw"
    source.write_bytes(raw)
    rows = scan_original_values_3100(
        source, expected_sha256=sha256(raw).hexdigest(), expected_raw_bytes=len(raw),
        expected_frames=1, expected_aux=0, expected_ticks=2, expected_tail_bytes=0,
        ranges=[(1, 0, 2)])[1]
    assert [r["source_param_descriptor_index"] for r in rows] == [0, 1]


def test_live_evidence_stream_requires_wire_order_for_same_frame(tmp_path):
    event1, csv1 = synthetic_tick(frame=2, tick=0)
    event2, csv2 = synthetic_tick(frame=2, tick=1)
    event1["source_param_descriptor_index"] = 0
    event2["source_param_descriptor_index"] = 2
    evidence = tmp_path / "events.jsonl"
    raw_layout = tmp_path / "selected.csv"
    _write_jsonl(evidence, [event1, event2])
    raw_layout.write_bytes(csv1 + csv2)
    assert verify_source_values_tick_files(evidence, raw_layout)["accepted_actual_param_3100_ticks"] == 2
    event2["source_param_descriptor_index"] = 0
    _write_jsonl(evidence, [event1, event2])
    with pytest.raises(ValueError, match="reordered"):
        verify_source_values_tick_files(evidence, raw_layout)
    del event2["source_param_descriptor_index"]
    _write_jsonl(evidence, [event1, event2])
    with pytest.raises(ValueError, match="reordered"):
        verify_source_values_tick_files(evidence, raw_layout)


def test_actual_go_writer_proof_matches_every_descriptor(tmp_path):
    fixture_root = os.environ.get("MVK_MULTI_3100_FIXTURE_DIR")
    if not fixture_root:
        pytest.skip("requires Go-generated multi-descriptor fixture")
    source = Path(fixture_root) / "multi_3100" / "TEST_2026-11-16_10-01-00.000"
    run = Path(shutil.copytree(source, tmp_path / source.name))
    summary = json.loads((run / "summary.json").read_text())
    audit = json.loads((run / AUDIT).read_text())
    window, = audit["windows"]
    events = replay(run, summary)
    assert [item["source_param_descriptor_index"] for item in events[1]] == [1, 3]
    assert [item["_register_prefix"].dword_hex(0x2002, current=True) for item in events[1]] == [
        pack("<f", 1.0).hex(), pack("<f", 3.0).hex()
    ]
    assert [item["_register_prefix"].dword_hex(0x30fe) for item in events[1]] == [
        "01000000", "00000000"
    ]
    qt = SimpleNamespace(channels=tuple(window["channels"]), spec=tuple(window["spec"]),
                         values=tuple(window["values"]), start_source_values_ticks=0,
                         end_source_values_ticks=2)

    def checked():
        return verify_original_live_values(run, summary=summary, source_sha=summary["raw_sha256"],
                                           qt_values_windows=[(1, qt)], replayed_events=events)

    assert checked()["verified_events"] == 2
    assert checked()["source_trigger_prefix_registers_verified"]
    event_file = run / window["name"]
    base_events = [json.loads(line) for line in event_file.read_bytes().splitlines()]
    # A new-format event must agree with RAW even if all enclosing hashes
    # are recomputed. A legacy event is accepted only for a unique trigger.
    for value in (None, 0, True):
        fake = [row.copy() for row in base_events]
        if value is None:
            del fake[0]["source_param_descriptor_index"]
        else:
            fake[0]["source_param_descriptor_index"] = value
        window["sha256"] = _write_jsonl(event_file, fake)
        window["bytes"] = event_file.stat().st_size
        audit_bytes = json.dumps(audit).encode()
        (run / AUDIT).write_bytes(audit_bytes)
        summary["source_live_values_audit_sha256"] = sha256(audit_bytes).hexdigest()
        with pytest.raises(ValueError, match="descriptor"):
            checked()
