"""One integrated Mode2 WriteValues cycle: button -> Go 0x3100 -> RAW -> Core.

Only generated local original-shaped test frames and archives; no device.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import json

import pytest

from .test_stage111z31fq_marked_values_export import _marked_original_values_run
from ..core.original_live_values_proof import (
    AUDIT,SCHEMA,verify_original_live_values,
)
from ..core.original_values_3100_timeline import scan_original_values_3100
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,export_source_write_windows,
)


def _with_go_values_events(tmp_path, *, multi_descriptor=False):
    run,flow,ledger=_marked_original_values_run(tmp_path,multi_descriptor=multi_descriptor)
    window=ledger.windows[0]
    assert window.kind=="values"
    summary=json.loads((run/"summary.json").read_text())
    source_sha=summary["raw_sha256"]
    events=scan_original_values_3100(
        run/"incoming.raw",
        expected_sha256=source_sha,
        expected_raw_bytes=summary["raw_bytes"],
        expected_frames=summary["frames_decoded"],
        expected_aux=summary["aux4700_updates"],
        expected_ticks=summary["values_ticks_address_3100"],
        expected_tail_bytes=summary["incomplete_final_frame_bytes"],
        ranges=[(1,window.start_source_values_ticks,
                 window.end_source_values_ticks)],
    )[1]
    assert len(events)==2
    now="2026-11-18T13:15:12.123Z"
    filename="SOURCE_W01_VALUES_3100_RECEIVED.jsonl"
    lines=[]
    for e in events:
        row={
            "frame_index":e["frame_index"]+1,
            "source_values_tick_index":e["source_tick_index"],
            "received_utc":now,
            "param_address":"0x3100",
            "register_words":e["register_words"],
            "param_payload_le_hex":e["register_bytes_hex"],
            "param_payload_sha256":e["register_payload_sha256"],
        }
        if multi_descriptor:
            row["source_param_descriptor_index"] = e["source_param_descriptor_index"]
        lines.append(json.dumps(row,separators=(",",":"))+"\n")
    data="".join(lines).encode()
    (run/filename).write_bytes(data)
    doc={
        "schema":SCHEMA,
        "session_id":run.name,
        "source_raw_sha256":source_sha,
        "end_reason":"STOPPED_BY_USER",
        "end_frames_decoded":summary["frames_decoded"],
        "end_source_values_ticks_address_3100":
            summary["values_ticks_address_3100"],
        "end_aux4700_updates":summary["aux4700_updates"],
        "original_delphi_get_value_text_parity_verified":False,
        "original_win32_time_parity_verified":False,
        "windows":[{
            "window":1,
            "begin_operator_sequence":1,
            "end_operator_sequence":2,
            "begin_source_values_tick":window.start_source_values_ticks,
            "end_source_values_tick":window.end_source_values_ticks,
            "begin_before_frame":window.start_frames,
            "end_after_frame":window.end_frames,
            "channels":list(window.channels),
            "spec":list(window.spec),
            "values":list(window.values),
            "name":filename,
            "events":len(events),
            "bytes":len(data),
            "sha256":sha256(data).hexdigest(),
            "outcome":"CLOSED_BY_OPERATOR",
        }],
    }
    payload=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(payload)
    summary.update(
        end_reason="STOPPED_BY_USER",
        source_live_values_audit_sha256=sha256(payload).hexdigest(),
        source_live_values_windows=1,
        source_live_values_event_records=len(events),
    )
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
    return run,flow,ledger,events


def test_mode2_go_live_values_full_cycle_with_source_3100_raw(tmp_path):
    run,flow,ledger,events=_with_go_values_events(tmp_path)
    summary=json.loads((run/"summary.json").read_text())
    receipt=verify_original_live_values(
        run,summary=summary,source_sha=summary["raw_sha256"],
        qt_values_windows=[(1,ledger.windows[0])],
        replayed_events={1:events})
    assert receipt["verified_windows"]==1
    assert receipt["verified_events"]==2
    assert not receipt["original_delphi_get_value_text_parity_verified"]
    result=export_source_write_windows(ledger,flow,run)
    assert result["source_live_values_3100_verified"] is True
    assert result["source_live_values_3100_events"]==2
    assert result["source_live_values_3100_windows"]==1
    export=run/EXPORT_SUBDIR
    source_file=run/"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"
    copied=export/source_file.name
    assert copied.read_bytes()==source_file.read_bytes()
    assert (export/"VALUES01_SOURCE_3100_EVENTS.csv").is_file()
    audit=json.loads((export/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert audit["source_live_values_3100_verified"] is True
    assert audit["source_values_csv_exact_delphi_layout_verified"] is False
    assert audit["original_tmkvthread_byte_exact_recording"] is False


@pytest.mark.parametrize("tamper",[
    lambda r,s,d: (r/"SOURCE_W01_VALUES_3100_RECEIVED.jsonl").write_bytes(
        (r/"SOURCE_W01_VALUES_3100_RECEIVED.jsonl").read_bytes()[:-2]+b"X\n"),
    lambda r,s,d: d["windows"][0].update(begin_source_values_tick=1),
    lambda r,s,d: d["windows"][0]["values"].__setitem__(0,False),
    lambda r,s,d: d["windows"][0].update(outcome="INTERRUPTED"),
    lambda r,s,d: d.update(original_delphi_get_value_text_parity_verified=True),
    lambda r,s,d: s.update(source_live_values_event_records=3),
])
def test_source_live_values_tamper_rejected_without_local_export(tmp_path,tamper):
    run,flow,ledger,events=_with_go_values_events(tmp_path)
    doc=json.loads((run/AUDIT).read_text())
    summary=json.loads((run/"summary.json").read_text())
    tamper(run,summary,doc)
    serialized=(json.dumps(doc,indent=2,ensure_ascii=False)+"\n").encode()
    (run/AUDIT).write_bytes(serialized)
    summary["source_live_values_audit_sha256"]=sha256(serialized).hexdigest()
    (run/"summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()


def test_values_source_does_not_use_audited_aux_as_row_trigger(tmp_path):
    run,flow,ledger,events=_with_go_values_events(tmp_path)
    summary=json.loads((run/"summary.json").read_text())
    doc=json.loads((run/AUDIT).read_text())
    doc["windows"][0]["events"]=summary["aux4700_updates"]+1
    serialized=(json.dumps(doc,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(serialized)
    summary["source_live_values_audit_sha256"]=sha256(serialized).hexdigest()
    (run/"summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError,match="tick/events disagree"):
        export_source_write_windows(ledger,flow,run)



def test_stop_export_keeps_both_rows_from_one_param(tmp_path):
    run,flow,ledger,_=_with_go_values_events(tmp_path,multi_descriptor=True)
    result=export_source_write_windows(ledger,flow,run)
    assert result["source_live_values_3100_verified"] is True
    assert result["source_live_values_3100_events"] == 2
    with (run/EXPORT_SUBDIR/"VALUES01_SOURCE_3100_EVENTS.csv").open(
            encoding="utf-8-sig",newline="") as file:
        rows=list(csv.DictReader(file, delimiter=";"))
    assert [(r["SOURCE_PARAM_DESCRIPTOR_INDEX"],r["PARAM_PAYLOAD_LE_HEX"]) for r in rows] == [
        ("0",b"ABCD".hex()),("2",b"WXYZ".hex())]
    assert rows[0]["RECEIVED_FRAME_INDEX"] == rows[1]["RECEIVED_FRAME_INDEX"]
