"""Independent original WriteValues event verification against REAL source RAW.

Go captures only when the original TMVKThread writer is open and PARAM
descriptor address 0x3100 arrives; _Unit125:008085A5 and 008066F0.
The numeric vendor TMvkCellList.GetValueText is NOT treated as known.
Each received register payload is independently replayed from RAW via
scan_original_values_3100, and its local Go event file is SHA-verified.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import re

from .original_source_values_tick_acceptance import verify_source_values_prefix_event

SCHEMA="MVK_SOURCE_LIVE_VALUES_3100_EVENTS_V1"
AUDIT="SOURCE_LIVE_VALUES_NATIVE_AUDIT.json"
HEXDIGEST=re.compile(r"[0-9a-f]{64}\Z")
MAX_AUDIT=1024*1024
MAX_EVENTS=64
MAX_FILE=32*1024*1024
BASE_EVENT_KEYS={"frame_index","source_values_tick_index","received_utc",
                 "param_address","register_words","param_payload_le_hex",
                 "param_payload_sha256"}


def _sha(x,name):
    if not isinstance(x,str) or not HEXDIGEST.fullmatch(x):
        raise ValueError("Original WriteValues invalid SHA "+name)
    return x


def _count(x,label,limit=(1<<64)-1):
    if type(x) is not int or not 0<=x<=limit:
        raise ValueError("Original WriteValues invalid counter "+label)
    return x


def _mask(x,count,label):
    if (not isinstance(x,list) or len(x)!=count or
            not all(type(v) is bool for v in x)):
        raise ValueError("Original WriteValues invalid "+label)
    return tuple(x)


def _file(run,name,max_bytes):
    if (not isinstance(name,str) or name!=Path(name).name or
            "/" in name or "\\" in name or "\x00" in name):
        raise ValueError("Original WriteValues path traversal")
    file=run/name
    if file.is_symlink() or not file.is_file() or file.stat().st_size>max_bytes:
        raise ValueError("Original WriteValues source event file missing/linked")
    return file


def verify_original_live_values(
        run:Path|str, *, summary:dict, source_sha:str,
        qt_values_windows:list[tuple[int,object]],
        replayed_events:dict[int,list[dict]],
)->dict|None:
    """Check Go original live VALUES against independent FQ replay.

    qt_values_windows: (global window number, source ledger window) for
    values-only windows. Go numbers 1..N independently of mixed DATA.
    Returns None only for older runs with no native values audit.
    If the summary contains a digest but the audit mismatches, fail closed.
    """
    folder=Path(run)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Original WriteValues source run missing")
    if not isinstance(summary,dict) or not isinstance(replayed_events,dict):
        raise ValueError("Original WriteValues source proof unavailable")
    raw_sha=_sha(source_sha,"source RAW")
    proof_sha=summary.get("source_live_values_audit_sha256")
    if proof_sha is None:
        return None
    proof_sha=_sha(proof_sha,"live native values")
    doc_bytes=_file(folder,AUDIT,MAX_AUDIT).read_bytes()
    if sha256(doc_bytes).hexdigest()!=proof_sha:
        raise ValueError("Original WriteValues audit SHA mismatch")
    try:
        doc=json.loads(doc_bytes)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Original WriteValues audit JSON corrupted") from exc
    if (not isinstance(doc,dict) or doc.get("schema")!=SCHEMA
            or doc.get("session_id")!=folder.name
            or doc.get("source_raw_sha256")!=raw_sha
            or summary.get("raw_sha256")!=raw_sha
            or doc.get("end_reason")!=summary.get("end_reason")
            or doc.get("end_frames_decoded")!=summary.get("frames_decoded")
            or doc.get("end_source_values_ticks_address_3100")!=
               summary.get("values_ticks_address_3100")
            or doc.get("end_aux4700_updates")!=summary.get("aux4700_updates")
            or doc.get("original_delphi_get_value_text_parity_verified") is not False
            or doc.get("original_win32_time_parity_verified") is not False
            or summary.get("capture_only_after_parser_error",False) is True
            or summary.get("source_tcp_multi_socket",False) is True):
        raise ValueError("Original WriteValues provenance/run mismatch")
    windows=doc.get("windows")
    if (not isinstance(windows,list) or len(windows)!=len(qt_values_windows)
            or not 1<=len(windows)<=8 or
            summary.get("source_live_values_windows")!=len(windows)):
        raise ValueError("Original WriteValues selected window mismatch")
    total_events=0
    out=[]
    last_tick=0
    last_frame=0
    for index,(record,other) in enumerate(zip(windows,qt_values_windows),1):
        if not isinstance(record,dict):
            raise ValueError("Original WriteValues event window invalid")
        global_index,qt=other
        if type(global_index) is not int or global_index<=0:
            raise ValueError("Original WriteValues Qt window index invalid")
        if record.get("window")!=index:
            raise ValueError("Original WriteValues Go window order changed")
        channels=_mask(record.get("channels"),10,"channels")
        spec=_mask(record.get("spec"),43,"spec")
        values=_mask(record.get("values"),73,"values")
        if (channels!=qt.channels or spec!=qt.spec or
                values!=qt.values):
            raise ValueError("Original WriteValues different Qt/Go masks")
        begin=_count(record.get("begin_source_values_tick"),"start tick")
        end=_count(record.get("end_source_values_tick"),"end tick")
        first=_count(record.get("begin_before_frame"),"start frame")
        last=_count(record.get("end_after_frame"),"end frame")
        if (begin!=qt.start_source_values_ticks or
                end!=qt.end_source_values_ticks or
                begin<last_tick or end<begin or
                first<last_frame or last<first):
            raise ValueError("Original WriteValues Go/Qt frame boundaries differ")
        last_tick=end
        last_frame=last
        if record.get("outcome") not in (
                "CLOSED_BY_OPERATOR","CLOSED_BY_SOURCE_THREAD"):
            raise ValueError("Original WriteValues interrupted source writer")
        if (record["outcome"]=="CLOSED_BY_SOURCE_THREAD" and
                summary.get("end_reason") not in (
                    "STOPPED_BY_USER","DURATION_REACHED","SIZE_LIMIT_REACHED")):
            raise ValueError("Original WriteValues false clean close")
        name=f"SOURCE_W{index:02d}_VALUES_3100_RECEIVED.jsonl"
        if record.get("name")!=name:
            raise ValueError("Original WriteValues source file name mismatch")
        content=_file(folder,name,MAX_FILE).read_bytes()
        if (len(content)!=_count(record.get("bytes"),"JSONL byte size",MAX_FILE)
                or sha256(content).hexdigest()!=_sha(record.get("sha256"),
                                                        "VALUES event JSONL")):
            raise ValueError("Original WriteValues event file SHA mismatch")
        expected=replayed_events.get(global_index)
        if (not isinstance(expected,list) or len(expected)!=end-begin or
                len(expected)>MAX_EVENTS or
                len(expected)!=_count(record.get("events"),"0x3100 events",
                                      MAX_EVENTS)):
            raise ValueError("Original WriteValues tick/events disagree")
        lines=content.splitlines(keepends=True)
        if len(lines)!=len(expected):
            raise ValueError("Original WriteValues missing/extra JSONL event")
        prefix_rows=[]
        rich_mode=None
        for a,b in zip(lines,expected):
            if not a.endswith(b"\n"):
                raise ValueError("Original WriteValues incomplete event line")
            try:
                event=json.loads(a)
            except (ValueError,UnicodeError) as exc:
                raise ValueError("Original WriteValues event JSON corrupted") from exc
            if not isinstance(event,dict):
                raise ValueError("Original WriteValues event not an object")
            keys=set(event)
            rich=keys==BASE_EVENT_KEYS|{"source_ordered_raw_tick"}
            if not rich and keys!=BASE_EVENT_KEYS:
                raise ValueError("Original WriteValues unexpected event fields")
            if rich_mode is not None and rich_mode!=rich:
                raise ValueError("Original WriteValues mixed event schemas")
            rich_mode=rich
            when=event.get("received_utc")
            if type(when) is not str:
                raise ValueError("Original WriteValues missing source timestamp")
            try:
                parsed=datetime.fromisoformat(when.replace("Z","+00:00"))
            except ValueError as exc:
                raise ValueError("Original WriteValues invalid timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError("Original WriteValues timestamp lacks UTC")
            if (event.get("frame_index")!=b["frame_index"]+1 or
                    event.get("source_values_tick_index")!=b["source_tick_index"] or
                    event.get("param_address")!="0x3100" or
                    event.get("register_words")!=b["register_words"] or
                    event.get("param_payload_le_hex")!=b["register_bytes_hex"] or
                    event.get("param_payload_sha256")!=
                       b["register_payload_sha256"]):
                raise ValueError("Original WriteValues source RX event disagrees")
            if rich:
                checked=verify_source_values_prefix_event(
                    event,prefix=b.get("_register_prefix"),
                    channels=channels,spec=spec,values=values)
                prefix_rows.append(checked["raw_line_bytes"])
        layout_evidence=None
        if rich_mode:
            layout_name=f"SOURCE_W{index:02d}_VALUES_3100_RAW_LAYOUT.csv"
            if record.get("source_raw_layout_name")!=layout_name:
                raise ValueError("Original WriteValues source RAW layout name mismatch")
            layout=_file(folder,layout_name,MAX_FILE).read_bytes()
            if (layout!=b"".join(prefix_rows) or
                    len(layout)!=_count(record.get("source_raw_layout_bytes"),
                                        "RAW layout bytes",MAX_FILE) or
                    len(prefix_rows)!=_count(record.get("source_raw_layout_rows"),
                                            "RAW layout rows",MAX_EVENTS) or
                    sha256(layout).hexdigest()!=_sha(record.get("source_raw_layout_sha256"),
                                                     "RAW layout")):
                raise ValueError("Original WriteValues source RAW layout differs from trigger proof")
            layout_evidence={"name":layout_name,"bytes":len(layout),
                             "sha256":record["source_raw_layout_sha256"]}
        total_events+=len(lines)
        out.append({
            "name":name,"window":global_index,"bytes":len(content),
            "sha256":record["sha256"],"events":len(lines),
            "source_raw_sha256":raw_sha,
            "original_source_3100_payloads_verified":True,
            "source_trigger_prefix_registers_verified":bool(rich_mode),
            "source_raw_layout":layout_evidence,
            "delphi_get_value_text_parity_verified":False,
        })
    if total_events!=summary.get("source_live_values_event_records"):
        raise ValueError("Original WriteValues total events counter disagrees")
    return {
        "source":"ORIGINAL_TMVKTHREAD_LIVE_WRITEVALUES_3100_V1",
        "native_audit_sha256":proof_sha,
        "verified_windows":len(out),"verified_events":total_events,
        "verified_files":out,
        "source_trigger_prefix_registers_verified":bool(total_events) and all(
            not item["events"] or item["source_trigger_prefix_registers_verified"]
            for item in out),
        "original_delphi_get_value_text_parity_verified":False,
    }
