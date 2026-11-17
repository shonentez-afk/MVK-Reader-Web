"""Verify exact per-TCP raw copies after an original Task2 reconnect.

Go's incoming.raw is an unmodified byte concat for diagnostics, NEVER a
single continuous waveform after reconnect. The source-generated individual
raw files must match BOTH original byte offsets AND SHA256, and the manifest
must itself match the independent Go summary digest. No sockets or imports of
private PCAP/EXE/IDP files. No untrusted path traversal/symlinks.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

SCHEMA="MVK_SOURCE_TASK2_TCP_SEGMENTS_V1"
MANIFEST="SOURCE_TASK2_TCP_SEGMENTS.json"
_RUN=re.compile(r"TEST_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.\d{3}(?:_\d+)?\Z")
_SHA=re.compile("[0-9a-f]{64}\\Z")
MAX_BYTES=2*1024**3
MAX_SEGMENTS=128


def _safe_file(path:Path,size:int|None=None)->None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original TCP source segment file missing/unsafe")
    if size is not None and path.stat().st_size!=size:
        raise ValueError("Original TCP segment size does not match offset span")
    if path.stat().st_size>MAX_BYTES:
        raise ValueError("Original TCP source segment exceeds approved limit")


def _parse(path:Path,max_size:int)->dict:
    _safe_file(path)
    if path.stat().st_size>max_size:
        raise ValueError("Source socket audit document too large")
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Invalid source socket audit JSON") from exc
    if not isinstance(data,dict):
        raise ValueError("Source socket audit object required")
    return data


def _digest(path:Path, *,offset:int=0,size:int|None=None)->str:
    _safe_file(path)
    h=sha256()
    with path.open("rb") as f:
        f.seek(offset)
        remaining=size if size is not None else path.stat().st_size
        while remaining:
            data=f.read(min(1024*1024,remaining))
            if not data:raise ValueError("Source TCP RAW bytes truncated")
            h.update(data)
            remaining-=len(data)
    return h.hexdigest()


def verify_source_tcp_session_segments(root:Path|str)->dict:
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Native source parent directory missing/unsafe")
    runs=[p for p in root.iterdir()
          if p.is_dir() and not p.is_symlink()
          and _RUN.fullmatch(p.name) and (p/MANIFEST).exists()]
    if len(runs)!=1:
        raise ValueError("Need exactly one source TCP-segmented run")
    run=runs[0]
    summary=_parse(run/"summary.json",256_000)
    manifest_path=run/MANIFEST
    manifest=_parse(manifest_path,256_000)
    expected=summary.get("source_tcp_segments_manifest_sha256")
    if not isinstance(expected,str) or not _SHA.fullmatch(expected):
        raise ValueError("Go source segment manifest SHA missing")
    if _digest(manifest_path)!=expected:
        raise ValueError("Source TCP manifest SHA disagrees with Go summary")
    total=summary.get("raw_bytes")
    count=summary.get("source_tcp_connection_count")
    if (type(total) is not int or not 0<=total<=MAX_BYTES or
            type(count) is not int or not 1<=count<=MAX_SEGMENTS or
            summary.get("source_tcp_segment_copies_verified") is not True or
            summary.get("source_tcp_multi_socket") is not (count>1)):
        raise ValueError("Source TCP summary segment count/size/verification invalid")
    raw=run/"incoming.raw"
    _safe_file(raw,total)
    rawsha=summary.get("raw_sha256")
    if not isinstance(rawsha,str) or not _SHA.fullmatch(rawsha) or _digest(raw)!=rawsha:
        raise ValueError("Original incoming.raw SHA mismatch")
    if (manifest.get("schema")!=SCHEMA or
            manifest.get("session_id")!=run.name or
            manifest.get("instrument_ipv4")!=summary.get("target_ipv4") or
            manifest.get("source_raw_sha256")!=rawsha or
            manifest.get("source_tcp_connection_count")!=count or
            manifest.get("original_delphi_byte_parity_verified") is not False or
            manifest.get("single_rate_bin_certifiable") is not (
                count==1 and not summary.get("source_rate_transition_during_live",False))):
        raise ValueError("Source TCP segment manifest provenance contradicted")
    segments=manifest.get("segments")
    if not isinstance(segments,list) or len(segments)!=count:
        raise ValueError("Missing Go source TCP segment records")
    cursor=0
    verified=[]
    for index,item in enumerate(segments,1):
        if not isinstance(item,dict):
            raise ValueError("Invalid source TCP segment record")
        start=item.get("raw_offset_start")
        end=item.get("raw_offset_end_exclusive")
        size=item.get("raw_bytes")
        expected_file=f"SOURCE_TCP_SEGMENT_{index:04d}.raw"
        digest=item.get("raw_sha256")
        if (type(item.get("index")) is not int or item["index"]!=index or
                type(start) is not int or start!=cursor or
                type(end) is not int or end<start or end>total or
                type(size) is not int or size!=end-start or
                item.get("separate_raw_file")!=expected_file or
                not isinstance(digest,str) or not _SHA.fullmatch(digest)):
            raise ValueError("Source segment ordering, range, name or SHA invalid")
        separate=run/expected_file
        _safe_file(separate,size)
        if _digest(separate)!=digest or _digest(raw,offset=start,size=size)!=digest:
            raise ValueError("Source TCP fragment does not match original incoming RAW")
        verified.append({"segment":index,"bytes":size,"sha256":digest,
                         "end_reason":item.get("end_reason")})
        cursor=end
    if cursor!=total:
        raise ValueError("Source TCP segment coverage incomplete")
    return {
        "source":"MVK_SOURCE_TASK2_TCP_SEGMENTS_V1",
        "run_directory":str(run),
        "connection_count":count,
        "multiple_tcp_sessions":count>1,
        "original_raw_bytes":total,
        "original_raw_sha256":rawsha,
        "verified_segments":verified,
        "original_delphi_bin_parity_verified":False,
        "single_rate_export_allowed":count==1 and bool(manifest["single_rate_bin_certifiable"]),
    }
