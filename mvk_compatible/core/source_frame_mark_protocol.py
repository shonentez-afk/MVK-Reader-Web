"""Stage111Z31DA local-only operator frame markers from actual Go decoder.

The GUI writes a bounded atomically published LOCAL request to its already
approved capture directory; the one passive Go process applies it BEFORE
the next complete decoded application frame. No command is ever sent to
the MVK01 instrument. Only the Go diagnostic archive with the same RAW
SHA may certify the resulting ten ADC/TACH counters and AUX tick bounds.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import zipfile

REQUEST_SCHEMA="MVK_NATIVE_LOCAL_FRAME_MARK_REQUEST_V1"
AUDIT_SCHEMA="MVK_NATIVE_LOCAL_FRAME_MARK_AUDIT_V1"
INBOX=".mvk_frame_marks_inbox"
AUDIT="SOURCE_FRAME_MARKS_NATIVE.json"
MAX_REQUESTS=64
MAX_AUDIT_SIZE=262144
MAX_REQUEST_SIZE=4096
FRAME_BOUNDARY="BEFORE_NEXT_REASSEMBLED_APPLICATION_FRAME"


def _strict_int(value,name,maxval=2**64-1):
    if type(value) is not int or not 0<=value<=maxval:
        raise ValueError("Source frame marker invalid "+name)
    return value


def _flags(obj,length,name):
    if not isinstance(obj,list) or len(obj)!=length or any(
            type(x) is not bool for x in obj):
        raise ValueError("Source frame mark original "+name+" flags invalid")
    return tuple(obj)


def submit_native_frame_mark(root:Path|str,sequence:int,session_id:str,
                             event:str,plan,*,now:datetime|None=None)->dict:
    """One atomic local request. IPC only; device command count is ZERO."""
    from .original_live_pagefile import OriginalLiveFilePlan
    if not isinstance(plan,OriginalLiveFilePlan):
        raise ValueError("Missing original Mode2 10/43/73 selection")
    _strict_int(sequence,"sequence",MAX_REQUESTS)
    if sequence==0:
        raise ValueError("Source mark sequence starts with 1")
    if (not isinstance(session_id,str) or
            not session_id.startswith("TEST_") or len(session_id)>160
            or "/" in session_id or "\\" in session_id or "\x00" in session_id):
        raise ValueError("Source frame mark is not attached to one Go run")
    if event not in ("data_begin","data_end","values_begin","values_end"):
        raise ValueError("Unknown original writer event")
    parent=Path(root)
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("Live source root does not exist or is a symlink")
    folder=parent/INBOX
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("No verified local Go frame marker inbox")
    stamp=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    body={
        "schema":REQUEST_SCHEMA,"sequence":sequence,
        "session_id":session_id,"event":event,
        "requested_utc":stamp.isoformat(),
        "channels":list(plan.channels),"spec":list(plan.spec),
        "values":list(plan.values),
    }
    if not any(plan.channels):
        raise ValueError("Original channel selection is empty")
    data=(json.dumps(body,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    if len(data)>MAX_REQUEST_SIZE:
        raise ValueError("Source write command exceeds local size limit")
    name=f"{sequence:04d}.json"
    path=folder/name
    if path.exists() or path.is_symlink():
        raise ValueError("Duplicate source write event sequence")
    temporary=None
    try:
        fd,filename=tempfile.mkstemp(prefix=".local_mark_",suffix=".pending",
                                    dir=folder)
        temporary=Path(filename)
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Only a process writing the pre-approved source GUI inbox can
        # trigger frame marks. No socket, instrument data or remote call.
        if path.exists() or path.is_symlink():
            raise ValueError("Operator mark target already exists")
        temporary.replace(path)
        temporary=None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "source":REQUEST_SCHEMA,"sequence":sequence,
        "event":event,"session_id":session_id,
        "queued_local_only":True,"device_commands_sent":False,
        "operator_requested_utc":body["requested_utc"],
        "await_authoritative_next_frame":True,
    }


def _read_json(path:Path,limit:int,label:str):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise ValueError("Source frame mark "+label+" missing or untrusted")
    try:
        return json.loads(path.read_bytes())
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Malformed "+label) from exc


def accept_native_frame_mark_audit(ledger,flow)->dict:
    """Replace unverified 900ms status-poll windows with REAL Go frame marks.

    Go diagnostic summary has an SHA for the exact sidecar, AND both
    independently attest the accepted Native ZIP RAW SHA and the same
    TEST_* run ID. Rejects missing/out-of-order/unacked events, mismatched
    masks, channel/AUX boundary rollback and any foreign-session capture.
    Never quietly falls back to cached Qt status when event marking was
    requested.
    """
    from .original_live_write_stages import OriginalLiveWriteLedger
    from .offline_measurement_flow import OfflineMeasurementFlow
    from .offline_export import require_members
    if (not isinstance(ledger,OriginalLiveWriteLedger) or
            not isinstance(flow,OfflineMeasurementFlow) or flow.direct_bin
            or not ledger.finished):
        raise ValueError("Source frame marks require accepted Native capture")
    if not ledger.frame_marks_required:
        return {"mode":"LEGACY_STATUS_POLL", "authoritative":False}
    if ledger.frame_marks_failed or not ledger.frame_mark_actions:
        raise ValueError("Original source marker requests were rejected")
    path=Path(flow.session.path)
    run=path.parent
    if (path.is_symlink() or run.is_symlink() or
            run.name!=ledger.session_id):
        raise ValueError("Foreign source frame marks cannot apply to archive")
    summary=_read_json(run/"summary.json",MAX_AUDIT_SIZE,"Go summary")
    doc_path=run/AUDIT
    if (doc_path.is_symlink() or not doc_path.is_file()
            or doc_path.stat().st_size>MAX_AUDIT_SIZE):
        raise ValueError("Go did not acknowledge operator frame boundaries")
    raw=doc_path.read_bytes()
    digest=sha256(raw).hexdigest()
    if (summary.get("source_frame_marks_sha256")!=digest or
            summary.get("source_frame_marks_count")!=len(ledger.frame_mark_actions)):
        raise ValueError("Authenticated Go frame-mark SHA/count mismatch")
    try:
        doc=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Unparseable source frame mark audit") from exc
    with zipfile.ZipFile(path) as archive:
        _,export_audit=require_members(archive)
    raw_sha=export_audit.get("source_raw_sha256")
    if (not isinstance(raw_sha,str) or len(raw_sha)!=64 or
            summary.get("raw_sha256")!=raw_sha or
            doc.get("source_raw_sha256")!=raw_sha):
        raise ValueError("Source frame marks are from a different RAW")
    if (doc.get("schema")!=AUDIT_SCHEMA or
            doc.get("session_id")!=ledger.session_id or
            doc.get("device_commands_sent") is not False or
            doc.get("source_frame_boundary") is not True or
            doc.get("original_delphi_file_parity_verified") is not False):
        raise ValueError("Source frame-mark provenance not read-only or wrong run")
    entries=doc.get("requests")
    if not isinstance(entries,list) or len(entries)!=len(
            ledger.frame_mark_actions) or len(entries)>MAX_REQUESTS:
        raise ValueError("Local operator events differ from Go frame receipts")
    end_frames=_strict_int(doc.get("end_frames_decoded"),"end frames")
    end_aux=_strict_int(doc.get("end_aux4700_updates"),"end AUX")
    end_counts=_counts(doc.get("end_channel_samples"))
    if (end_frames!=_strict_int(summary.get("frames_decoded"),"summary frames")
            or end_aux!=_strict_int(summary.get("aux4700_updates"),"summary AUX")
            or len(summary.get("channels",[]))!=10 or
            any(end_counts[i]!=_strict_int(summary["channels"][i].get(
                "samples"),"summary channel samples")
                for i in range(10))):
        raise ValueError("Go source final frame mark counters inconsistent")
    if end_aux>flow.session.updates:
        raise ValueError("Go AUX tick count exceeds SHA-accepted ZIP")
    by_kind={}
    reconstructed=[]
    for idx,(issued,receipt) in enumerate(
            zip(ledger.frame_mark_actions,entries),1):
        if not isinstance(receipt,dict):
            raise ValueError("Source frame mark record is not a dictionary")
        if (_strict_int(receipt.get("sequence"),"sequence",MAX_REQUESTS)!=idx
                or issued["sequence"]!=idx
                or receipt.get("event")!=issued["event"]
                or receipt.get("applied") is not True
                or receipt.get("boundary")!=FRAME_BOUNDARY
                or receipt.get("device_commands_sent") is not False):
            raise ValueError("Go refused or reordered an operator frame mark")
        _flags(receipt.get("channels"),10,"channels")
        _flags(receipt.get("spec"),43,"spec")
        _flags(receipt.get("values"),73,"values")
        if (tuple(receipt["channels"])!=tuple(issued["channels"])
                or tuple(receipt["spec"])!=tuple(issued["spec"])
                or tuple(receipt["values"])!=tuple(issued["values"])):
            raise ValueError("Original channel/result flags changed in Go frame mark")
        samples=_counts(receipt.get("channel_samples"))
        frames=_strict_int(receipt.get("frames_decoded"),"frames")
        aux=_strict_int(receipt.get("aux4700_updates"),"AUX")
        if frames>end_frames or aux>end_aux or any(
                samples[i]>end_counts[i] for i in range(10)):
            raise ValueError("Source frame mark after accepted RAW end")
        kind,part=receipt["event"].split("_")
        if part=="begin":
            if kind in by_kind:
                raise ValueError("Repeated source mark start before stop")
            by_kind[kind]=(receipt,samples,frames,aux)
        else:
            if kind not in by_kind:
                raise ValueError("Source stop mark has no start")
            start,start_samples,start_frames,start_aux=by_kind.pop(kind)
            if (frames<start_frames or aux<start_aux or
                    any(x<y for x,y in zip(samples,start_samples))):
                raise ValueError("Go source frame mark counter rollback")
            reconstructed.append({
                "kind":kind,
                "start_samples":start_samples,
                "end_samples":samples,
                "start_frames":start_frames,
                "end_frames":frames,
                "start_aux":start_aux,
                "end_aux":aux,
                "start_utc":start.get("requested_utc"),
                "end_utc":receipt.get("requested_utc"),
            })
    if by_kind or len(reconstructed)!=len(ledger.windows):
        raise ValueError("Unmatched source frame marks cannot be exported")
    corrected=[]
    for window,real in zip(ledger.windows,reconstructed):
        if real["kind"]!=window.kind:
            raise ValueError("Go source windows reordered unexpectedly")
        corrected.append(replace(
            window,start_samples=real["start_samples"],
            end_samples=real["end_samples"],
            start_aux=real["start_aux"],end_aux=real["end_aux"],
            start_frames=real["start_frames"],end_frames=real["end_frames"],
            boundary_mode=FRAME_BOUNDARY))
    ledger.windows=corrected
    ledger.frame_marks_verified=True
    return {
        "mode":FRAME_BOUNDARY,"authoritative":True,
        "source_raw_sha256":raw_sha,
        "verified_go_mark_audit_sha256":digest,
        "accepted_events":len(entries),
        "device_commands_sent":False,
        "full_original_delphi_parity_verified":False,
    }


def _counts(arr):
    if not isinstance(arr,list) or len(arr)!=10:
        raise ValueError("Original ten channel source counters missing")
    return tuple(_strict_int(v,"channel sample count") for v in arr)
