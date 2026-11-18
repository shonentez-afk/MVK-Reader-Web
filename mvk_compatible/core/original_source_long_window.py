"""On-demand original 2**21 ring GetSignal selection; local read-only IPC.

Qt requests one source bAdcHScale window, never 8*2M periodic samples.
The ONLY Go TCP owner verifies actual rxPos/validPos/device index and
responds with a SHA-bound atomically replaced one-channel ZIP.
This is NOT original Win32 x87/TQGrapher/Delphi numerical parity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import tempfile
import zipfile

import numpy as np

from .native_r6_live_preview import LivePreview, PreviewADC, DOMAIN, MAX_SAMPLES
from .native_r6_live_status import _utc_stamp
from .original_adc_view_controls import ADC_HORIZONTAL_MS
from .original_source_ring_receipt import BUFFER_ELEMENTS
from .original_sample_cursor32 import u32_preview_bounds, u32_matches_go_status

REQUEST_NAME="MVK_SOURCE_WINDOW_REQUEST.json"
RESULT_NAME="MVK_SOURCE_WINDOW_RESULT.zip"
REQUEST_SCHEMA="MVK_SOURCE_LIVE_WINDOW_REQUEST_V1"
RESULT_SCHEMA="MVK_SOURCE_LIVE_WINDOW_RESULT_V1"
MAX_DISK_BYTES=BUFFER_ELEMENTS*4+8192
REQUEST_ID_RE=re.compile(r"[0-9a-f]{32}\Z")
SHA_RE=re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class SourceWindowRequest:
    session_id: str
    request_id: str
    adc: int
    h_tag: int
    samples: int
    capture_end: int
    sample_rate_hz: int
    device_end_index: int


@dataclass(frozen=True)
class SourceLongWindow:
    request: SourceWindowRequest
    preview: LivePreview

    @property
    def received_samples(self) -> int:
        return self.request.capture_end


def _root(root: str | Path, status: dict) -> Path:
    path=Path(root).absolute()
    run=Path(status.get("run_directory","")).absolute()
    if (not path.is_dir() or path.is_symlink() or
            not run.is_dir() or run.is_symlink() or
            path.resolve()!=run.resolve() or
            path.name!=status.get("session_id")):
        raise ValueError("Source GetSignal: foreign or unsafe capture directory")
    return path


def _trusted_source(status:dict,adc:int,h_tag:int,
                    *,require_history:bool=True):
    if (not isinstance(status,dict) or
            status.get("phase")!="RECORDING" or
            status.get("capture_only") is not False or
            status.get("invalid_frames")!=0 or
            status.get("source_tcp_multi_socket") is True or
            status.get("source_rate_transition_during_live") is True or
            status.get("snapshot_stale") is not False or
            status.get("source_original_storage_verified") is not True or
            status.get("source_original_storage") is None or
            status.get("seconds_since_last_packet") is not None and
            status["seconds_since_last_packet"]>4):
        raise ValueError("Source GetSignal: no trustworthy active original ring")
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("Source GetSignal: ADC 1..8 required")
    if type(h_tag) is not int or not 0<=h_tag<len(ADC_HORIZONTAL_MS):
        raise ValueError("Source GetSignal: original H scale Tag 0..13 required")
    row=status["source_original_storage"]["channels"][adc-1]
    live=status["channels"][adc-1]
    rate=row["last_sample_rate_hz"]
    gate=(status.get("source_original_receive_gate")
          if status.get("source_original_receive_gate_verified") is True
          else None)
    admissible=live["samples"]
    skipped=0
    allowed_source_gaps=0
    if gate is not None:
        g=gate["channels"][adc-1]
        skipped=g["rate_skipped_elements"]+g["freeze_skipped_elements"]
        allowed_source_gaps=(g["rate_skipped_frames"]+
                             g["freeze_skipped_frames"])
        if gate["freeze_update"] or gate["selected_rate_hz"]!=rate:
            raise ValueError("Source GetSignal: MvkSampleRate/FreezeUpdate gate active")
        admissible=g["accepted_elements"]
        if admissible+skipped!=live["samples"]:
            raise ValueError("Source GetSignal: source gate/native RX mismatch")
    if (row["input_domain"]!=DOMAIN or rate==0 or
            rate not in live["sample_rates_hz"] or
            live["sequence_discontinuities"] or live["nonfinite_samples"] or
            row["rate_changes"] or row["rejected_nonfinite_frames"] or
            row["rx_pos_64"]!=admissible or
            row["sequence_gaps"]>allowed_source_gaps or
            row["next_device_sample_index"]!=live["next_sample_index"]):
        raise ValueError("Source GetSignal: uncalibrated/discontinuous ADC")
    count=rate*ADC_HORIZONTAL_MS[h_tag]//1000
    if count<=MAX_SAMPLES:
        return None
    if count>BUFFER_ELEMENTS:
        raise ValueError("Source GetSignal: more than original 2M capacity")
    if require_history and row["available_elements"]<count:
        return None
    return row,live,rate,count


def submit_source_long_window(root: str|Path,status:dict,adc:int,h_tag:int,
                              *,request_id:str|None=None)->SourceWindowRequest|None:
    """Create ONE small bounded request, without networking or device TX."""
    settings=_trusted_source(status,adc,h_tag)
    if settings is None:
        return None
    row,live,rate,count=settings
    path=_root(root,status)
    rid=secrets.token_hex(16) if request_id is None else request_id
    if not isinstance(rid,str) or REQUEST_ID_RE.fullmatch(rid) is None:
        raise ValueError("Source GetSignal: invalid local request ID")
    end=row["rx_pos_64"]
    if end<count:
        return None
    req=SourceWindowRequest(
        status["session_id"],rid,adc,h_tag,count,end,rate,
        row["next_device_sample_index"])
    data={
        "schema":REQUEST_SCHEMA,"session_id":req.session_id,
        "request_id":req.request_id,"adc":req.adc,
        "source_h_tag":req.h_tag,"samples":req.samples,
        "capture_end":req.capture_end,"sample_rate_hz":req.sample_rate_hz,
        "device_end_index":req.device_end_index,
    }
    encoded=json.dumps(data,separators=(",",":"),sort_keys=True).encode("ascii")
    if len(encoded)>1024:
        raise ValueError("Source GetSignal: oversized local request")
    tmp_name=None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path,prefix=".mvk_long_window_request_",delete=False
        ) as f:
            tmp_name=f.name
            os.chmod(tmp_name,0o600)
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name,path/REQUEST_NAME)
    finally:
        if tmp_name is not None:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
    return req


def load_source_long_window(root:str|Path,status:dict,
                            request:SourceWindowRequest,
                            *,now:datetime|None=None)->SourceLongWindow|None:
    """Fail closed on wrong run, stale epoch, SHA, N, rate and domain."""
    if not isinstance(request,SourceWindowRequest):
        raise ValueError("Source GetSignal: missing approved selection")
    settings=_trusted_source(status,request.adc,request.h_tag)
    if settings is None:
        raise ValueError("Source GetSignal: current source H scale is not long")
    row,live,rate,count=settings
    if rate!=request.sample_rate_hz or count!=request.samples:
        raise ValueError("Source GetSignal: selected source rate changed")
    path=_root(root,status)/RESULT_NAME
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_DISK_BYTES:
        raise ValueError("Source GetSignal: unsafe or oversized response")
    try:
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            entry=f"ADC{request.adc}.f32"
            if sorted(names)!=sorted((entry,"MANIFEST.json")):
                raise ValueError("Source GetSignal: invalid ZIP members")
            if (z.getinfo(entry).compress_type!=zipfile.ZIP_STORED or
                    z.getinfo(entry).file_size!=count*4 or
                    z.getinfo("MANIFEST.json").file_size>4096):
                raise ValueError("Source GetSignal: source ZIP oversized/rewritten")
            meta=json.loads(z.read("MANIFEST.json"))
            if not isinstance(meta,dict):
                raise ValueError("Source GetSignal: invalid manifest")
            # Old snapshots from a prior request are harmless and may
            # coexist until Go replaces the result; never show them.
            if meta.get("request_id")!=request.request_id:
                return None
            if (meta.get("schema")!=RESULT_SCHEMA or
                    meta.get("session_id")!=request.session_id or
                    meta.get("phase")!="RECORDING" or
                    meta.get("adc")!=request.adc or
                    meta.get("source_h_tag")!=request.h_tag or
                    meta.get("entry")!=entry or
                    meta.get("samples")!=count or
                    meta.get("capture_end")!=request.capture_end or
                    meta.get("sample_rate_hz")!=rate or
                    meta.get("next_sample_index")!=request.device_end_index or
                    meta.get("first_sample_index")!=
                        ((request.device_end_index-count)&0xffffffff) or
                    meta.get("input_domain")!=DOMAIN or
                    meta.get("calibration_already_applied") is not True or
                    meta.get("provisional_not_audited") is not True):
                raise ValueError("Source GetSignal: foreign or malformed source window")
            receipt_ts=_utc_stamp(meta.get("updated_utc"),
                                  "source long window updated_utc")
            reference=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
            if abs((reference-receipt_ts).total_seconds())>8:
                raise ValueError("Source GetSignal: stale or future source window")
            frame=meta.get("frames_decoded")
            raw=meta.get("raw_bytes")
            if (type(frame) is not int or type(raw) is not int or
                    frame<0 or raw<0 or
                    frame>status["frames_decoded"] or raw>status["raw_bytes"]):
                raise ValueError("Source GetSignal: newer than verified RAW")
            # The original ring may have advanced after Go took the
            # snapshot, but no requested byte may have been overwritten.
            start=request.capture_end-count
            if (request.capture_end>row["rx_pos_64"] or
                    start<row["first_readable_pos_64"] or
                    request.capture_end>live["samples"] or
                    not u32_preview_bounds(meta["first_sample_index"],
                                           meta["next_sample_index"],count) or
                    not u32_matches_go_status(
                        request.device_end_index,
                        row["next_device_sample_index"],
                        status_samples=row["rx_pos_64"],
                        window_samples=count,
                        captured_samples=request.capture_end)):
                raise ValueError("Source GetSignal: stale original storage source index")
            data=z.read(entry)
            digest=meta.get("sha256")
            if (not isinstance(digest,str) or SHA_RE.fullmatch(digest) is None
                    or hashlib.sha256(data).hexdigest()!=digest):
                raise ValueError("Source GetSignal: calibrated Float32 SHA mismatch")
            values=np.frombuffer(data,dtype="<f4")
            if len(values)!=count or not np.all(np.isfinite(values)):
                raise ValueError("Source GetSignal: nonfinite original ring data")
            values.setflags(write=False)
            preview=LivePreview(
                request.session_id,receipt_ts,raw,frame,
                {request.adc:PreviewADC(
                    request.adc,rate,meta["first_sample_index"],
                    meta["next_sample_index"],values,digest,
                    request.capture_end)},
            )
            return SourceLongWindow(request,preview)
    except (zipfile.BadZipFile,UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise ValueError("Source GetSignal: damaged atomic source window") from exc
