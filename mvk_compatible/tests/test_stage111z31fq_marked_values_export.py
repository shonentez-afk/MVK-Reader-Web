"""E2E synthetic original Mode2 marked WriteValues: 0x3100, not AUX.

No instrument, user PC capture, private Pascal/IDP or raw artefacts here.
"""
from __future__ import annotations
import csv
from hashlib import sha256
import json
import struct
import zipfile

import pytest

from .test_offline_core import fixture_zip
from .test_stage111z31cz_source_write_stages_core import RUN, source_status
from .test_stage111z31fq_original_values_3100_timeline import frame, param, aux_frame
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_live_pagefile import OriginalLiveFilePlan
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,OriginalLiveWriteLedger,export_source_write_windows,
)
from ..core.source_frame_mark_protocol import (
    AUDIT,AUDIT_SCHEMA,FRAME_BOUNDARY,INBOX,submit_native_frame_mark,
)


def _sample(ch,index):
    f=bytearray(1052)
    struct.pack_into("<II",f,0,0xFF800ADC,len(f))
    struct.pack_into("<I",f,12,index)
    struct.pack_into("<I",f,20,ch)
    struct.pack_into("<I",f,24,65536)
    return bytes(f)


def _marked_original_values_run(tmp_path):
    run=tmp_path/RUN
    run.mkdir()
    parts=[frame(1,bytes(256))]
    for ch in range(8):
        parts.append(_sample(ch,0))
    parts.extend([aux_frame(),param((0x3100,b"ABCD"))])
    for ch in range(8):
        parts.append(_sample(ch,256))
    parts.extend([aux_frame(),param((0x3100,b"WXYZ")),
                  frame(0xDEADBEEF,bytes(4))])
    raw=b"".join(parts)
    digest=sha256(raw).hexdigest()
    (run/"incoming.raw").write_bytes(raw)
    archive=fixture_zip(run)
    # Update this self-contained fixture's accepted provenance to point
    # to the newly built, independent synthetic Go protocol byte stream.
    with zipfile.ZipFile(archive) as z:
        members={name:z.read(name) for name in z.namelist()}
    audit=json.loads(members["EXPORT_AUDIT.json"])
    audit["source_raw_sha256"]=digest
    members["EXPORT_AUDIT.json"]=json.dumps(audit).encode()
    provenance=json.loads(members["AUX_PROVENANCE.json"])
    provenance["source_raw_sha256"]=digest
    members["AUX_PROVENANCE.json"]=json.dumps(provenance).encode()
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for name,value in members.items():
            z.writestr(name,value)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1)
    before=source_status(adc_samples=0,aux=0,frames=1,raw=264)
    before["source_values_ticks_address_3100"]=0
    after=source_status(adc_samples=512,aux=2,
                        frames=len(parts),raw=len(raw))
    after["source_values_ticks_address_3100"]=2
    ledger=OriginalLiveWriteLedger()
    ledger.observe(before)
    plan=OriginalLiveFilePlan().bind_status(before)
    (tmp_path/INBOX).mkdir()
    ledger.toggle("values",plan)
    req1=submit_native_frame_mark(tmp_path,1,RUN,"values_begin",plan)
    ledger.register_native_frame_mark(req1,plan)
    ledger.observe(after)
    ledger.toggle("values",plan)
    req2=submit_native_frame_mark(tmp_path,2,RUN,"values_end",plan)
    ledger.register_native_frame_mark(req2,plan)
    ledger.finish(accepted=True)
    receipts=[]
    for n,(request,frames,aux,ticks,samples) in enumerate((
        (req1,1,0,0,[0]*10),
        (req2,len(parts)-1,2,2,[512]*8+[0,0]),
    ),1):
        receipts.append({
            "sequence":n,
            "event":request["event"],
            "requested_utc":request["requested_utc"],
            "applied_utc":"2026-11-18T03:00:00Z",
            "applied":True,
            "frames_decoded":frames,
            "aux4700_updates":aux,
            "source_values_ticks_address_3100":ticks,
            "channel_samples":samples,
            "channels":list(plan.channels),"spec":list(plan.spec),
            "values":list(plan.values),
            "device_commands_sent":False,
            "boundary":FRAME_BOUNDARY,
        })
    doc={
        "schema":AUDIT_SCHEMA,"session_id":RUN,"source_raw_sha256":digest,
        "end_frames_decoded":len(parts),"end_aux4700_updates":2,
        "end_source_values_ticks_address_3100":2,
        "end_channel_samples":[512]*8+[0,0],
        "device_commands_sent":False,
        "source_frame_boundary":True,
        "original_delphi_file_parity_verified":False,
        "requests":receipts,
    }
    content=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(content)
    summary={
        "raw_sha256":digest,
        "raw_bytes":len(raw),
        "frames_decoded":len(parts),
        "aux4700_updates":2,
        "values_ticks_address_3100":2,
        "incomplete_final_frame_bytes":0,
        "channels":[{"samples":n} for n in [512]*8+[0,0]],
        "source_frame_marks_sha256":sha256(content).hexdigest(),
        "source_frame_marks_count":2,
    }
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf8")
    return run,flow,ledger


def test_marked_values_export_is_driven_by_real_source_3100(tmp_path):
    run,flow,ledger=_marked_original_values_run(tmp_path)
    result=export_source_write_windows(ledger,flow,run)
    assert result["verified_frame_boundaries"]
    target=run/EXPORT_SUBDIR
    with (target/"VALUES01_SOURCE_3100_EVENTS.csv").open(
            encoding="utf-8-sig",newline="") as f:
        evidence=list(csv.DictReader(f,delimiter=";"))
    assert len(evidence)==2
    assert [int(x["SOURCE_3100_TICK_INDEX"]) for x in evidence]==[0,1]
    assert [x["PARAM_PAYLOAD_LE_HEX"] for x in evidence]==[
        b"ABCD".hex(),b"WXYZ".hex()]
    assert [int(x["LATEST_PRECEDING_AUX_INDEX"]) for x in evidence]==[0,1]
    with (target/"VALUES01_NATIVE_VERIFIED_SELECTED.csv").open(
            encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f,delimiter=";"))
    assert rows and {int(row["SOURCE_3100_TICK_INDEX"]) for row in rows}=={0,1}
    assert {int(row["PRECEDING_AUX_INDEX"]) for row in rows}=={0,1}
    receipt=json.loads((target/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert receipt["source_values_export_anchored_to_verified_3100"] is True
    assert receipt["source_3100_trigger_events_replayed"]==2
    assert receipt["source_values_csv_exact_delphi_layout_verified"] is False
    assert not receipt["original_tmkvthread_byte_exact_recording"]


def test_modified_native_raw_blocks_marked_values_without_output(tmp_path):
    run,flow,ledger=_marked_original_values_run(tmp_path)
    data=bytearray((run/"incoming.raw").read_bytes())
    data[200]^=1
    (run/"incoming.raw").write_bytes(data)
    with pytest.raises(ValueError,match="SHA"):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()
