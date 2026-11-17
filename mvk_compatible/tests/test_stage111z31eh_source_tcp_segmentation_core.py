"""Two original Task2 TCP connections must never certify a joined BIN.

This fixture exercises the actual Go JSON contract, offsets and independent
SHA256. Private device captures are never uploaded or reproduced.
"""
from __future__ import annotations
from hashlib import sha256
import json
import pytest
from ..core.source_tcp_segments import (
 SCHEMA,MANIFEST,verify_source_tcp_session_segments,
)

def source_folder(tmp_path):
    root=tmp_path/"mvk_r6_session_local"
    run=root/"TEST_2026-11-17_01-01-01.001"
    run.mkdir(parents=True)
    raw_chunks=[b"MVK-SOCKET-ONE",b"MVK-SECOND-SOCKET" ]
    raw=b"".join(raw_chunks)
    (run/"incoming.raw").write_bytes(raw)
    def digest(value):return sha256(value).hexdigest()
    segments=[]
    cursor=0
    for index,piece in enumerate(raw_chunks,1):
        name=f"SOURCE_TCP_SEGMENT_{index:04d}.raw"
        (run/name).write_bytes(piece)
        segments.append({
            "index":index,"raw_offset_start":cursor,
            "raw_offset_end_exclusive":cursor+len(piece),
            "raw_bytes":len(piece),"separate_raw_file":name,
            "raw_sha256":digest(piece),"end_reason":"REMOTE_DISCONNECTED",
        })
        cursor+=len(piece)
    manifest={
        "schema":SCHEMA,"session_id":run.name,
        "instrument_ipv4":"192.168.0.30",
        "source_raw_sha256":digest(raw),
        "source_tcp_connection_count":2,
        "original_delphi_byte_parity_verified":False,
        "single_rate_bin_certifiable":False,"segments":segments,
    }
    blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode()
    (run/MANIFEST).write_bytes(blob)
    summary={
        "raw_bytes":len(raw),"raw_sha256":digest(raw),
        "target_ipv4":"192.168.0.30",
        "source_tcp_connection_count":2,
        "source_tcp_multi_socket":True,
        "source_tcp_segment_copies_verified":True,
        "source_tcp_segments_manifest_sha256":digest(blob),
    }
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
    return root,run,manifest,summary


def test_two_real_physical_socket_ranges_are_verified_not_one_merged_bin(tmp_path):
    root,run,_,_=source_folder(tmp_path)
    proof=verify_source_tcp_session_segments(root)
    assert proof["connection_count"]==2
    assert proof["multiple_tcp_sessions"]
    assert proof["original_raw_bytes"]==len(b"MVK-SOCKET-ONE")+len(b"MVK-SECOND-SOCKET")
    assert [x["bytes"] for x in proof["verified_segments"]]==[14,17]
    assert not proof["single_rate_export_allowed"]
    assert not proof["original_delphi_bin_parity_verified"]


def test_malformed_or_tampered_original_tcp_segment_fails_closed(tmp_path):
    root,run,_,_=source_folder(tmp_path)
    p=run/"SOURCE_TCP_SEGMENT_0002.raw"
    p.write_bytes(b"TAMPERED")
    with pytest.raises(ValueError,match="size"):
        verify_source_tcp_session_segments(root)


def test_source_manifest_replaced_without_go_sha_is_rejected(tmp_path):
    root,run,manifest,_=source_folder(tmp_path)
    manifest["single_rate_bin_certifiable"]=True
    (run/MANIFEST).write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="manifest SHA"):
        verify_source_tcp_session_segments(root)


def test_duplicate_or_foreign_original_run_refused(tmp_path):
    root,run,_,_=source_folder(tmp_path)
    other=root/"TEST_2026-11-17_01-01-01.002"
    other.mkdir()
    (other/MANIFEST).write_text("{}")
    with pytest.raises(ValueError,match="exactly one"):
        verify_source_tcp_session_segments(root)


def test_qt_capture_spec_requires_independent_approval_for_reconnect(tmp_path):
    from ..core.native_r6_bridge import CaptureSpec
    with pytest.raises(ValueError,match="разрешения SetRate"):
        CaptureSpec("192.168.0.30","192.168.0.5",10,128,tmp_path,
                    source_auto_reconnect=True).validate()
    spec=CaptureSpec("192.168.0.30","192.168.0.5",10,128,tmp_path,
                     source_rate_tx=True,source_auto_reconnect=True)
    root=spec.create_root()
    args=spec.native_args(root)
    assert "-source-task2-reconnect=true" in args
    assert "-source-task2-reconnect-approved=true" in args
    assert "-source-setrate-tx=true" in args
    assert "-source-setrate-tx-approved=true" in args
    assert "-approve=true" in args
