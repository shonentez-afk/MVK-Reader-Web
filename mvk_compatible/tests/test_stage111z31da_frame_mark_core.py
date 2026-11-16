"""Stage111Z31DA: exact NEXT decoded Go frame marks, synthetic captures only.

All event files are local, no connected device or network access. This
verifies SHA binding to the accepted Native archive, source mask order
and byte exact ADC interval extraction, not Delphi hardware parity.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile

import pytest

from .test_offline_core import fixture_zip
from .test_stage111z31cz_source_write_stages_core import (
    RUN,source_status,
)
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_live_pagefile import OriginalLiveFilePlan
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,OriginalLiveWriteLedger,export_source_write_windows,
)
from ..core.source_frame_mark_protocol import (
    AUDIT,AUDIT_SCHEMA,FRAME_BOUNDARY,INBOX,
    submit_native_frame_mark,
)


def synthetic_marked_run(tmp_path,*,tamper=None):
    run=tmp_path/RUN
    run.mkdir()
    archive=fixture_zip(run)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    before=source_status(adc_samples=0,aux=0,frames=1,raw=1024)
    after=source_status(adc_samples=512,aux=1,frames=30,raw=50000)
    ledger=OriginalLiveWriteLedger()
    ledger.observe(before)
    plan=OriginalLiveFilePlan().bind_status(before)
    inbox=tmp_path/INBOX
    inbox.mkdir()
    ledger.toggle("data",plan)
    mark=submit_native_frame_mark(tmp_path,1,RUN,"data_begin",plan)
    ledger.register_native_frame_mark(mark,plan)
    ledger.observe(after)
    ledger.toggle("data",plan)
    mark=submit_native_frame_mark(tmp_path,2,RUN,"data_end",plan)
    ledger.register_native_frame_mark(mark,plan)
    ledger.finish(accepted=True)
    for sequence in (1,2):
        filename=inbox/f"{sequence:04d}.json"
        request=json.loads(filename.read_text())
        assert request["session_id"]==RUN
        assert request["schema"]=="MVK_NATIVE_LOCAL_FRAME_MARK_REQUEST_V1"
    with zipfile.ZipFile(archive) as z:
        source_raw=json.loads(z.read("EXPORT_AUDIT.json"))["source_raw_sha256"]
    endcounts=[4096]*8+[0,0]
    recs=[]
    for i,kind in ((1,"data_begin"),(2,"data_end")):
        req=json.loads((inbox/f"{i:04d}.json").read_text())
        recs.append({
            "sequence":i,"event":kind,"requested_utc":req["requested_utc"],
            "applied_utc":"2026-11-16T08:40:00Z",
            "applied":True,"frames_decoded":10 if i==1 else 50,
            "aux4700_updates":0 if i==1 else 1,
            # Different from the 900ms status-poll boundaries:
            "channel_samples":([256]*8+[0,0] if i==1
                               else [768]*8+[0,0]),
            "channels":req["channels"],"spec":req["spec"],
            "values":req["values"],
            "device_commands_sent":False,"boundary":FRAME_BOUNDARY,
        })
    doc={
        "schema":AUDIT_SCHEMA,"session_id":RUN,
        "source_raw_sha256":source_raw,
        "end_frames_decoded":100,"end_aux4700_updates":2,
        "end_channel_samples":endcounts,
        "device_commands_sent":False,
        "source_frame_boundary":True,
        "original_delphi_file_parity_verified":False,
        "requests":recs,
    }
    if tamper=="foreign":
        doc["session_id"]="TEST_2026-11-16_09-00-00.000"
    if tamper=="denied":
        doc["requests"][1]["applied"]=False
    if tamper=="mask":
        doc["requests"][0]["channels"][0]=False
    if tamper=="rollback":
        doc["requests"][1]["channel_samples"][0]=128
    if tamper=="after-end":
        doc["requests"][1]["channel_samples"][0]=5000
    content=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode()
    digest=sha256(content).hexdigest()
    (run/AUDIT).write_bytes(content)
    if tamper=="modified-sha":
        digest="f"*64
    summary={
        "raw_sha256":source_raw,"frames_decoded":100,
        "aux4700_updates":2,
        "channels":[{"samples":n} for n in endcounts],
        "source_frame_marks_sha256":digest,
        "source_frame_marks_count":2,
    }
    (run/"summary.json").write_text(json.dumps(summary))
    if tamper=="absent":
        (run/AUDIT).unlink()
    return run,archive,flow,ledger


def test_go_marks_override_cached_qt_samples_with_byte_exact_export(tmp_path):
    run,archive,flow,ledger=synthetic_marked_run(tmp_path)
    assert ledger.windows[0].start_samples[0]==0
    assert ledger.windows[0].end_samples[0]==512
    result=export_source_write_windows(ledger,flow,run)
    assert result["verified_frame_boundaries"]
    assert result["native_mark_requests"]==2
    assert ledger.frame_marks_verified
    assert ledger.windows[0].start_samples[0]==256
    assert ledger.windows[0].end_samples[0]==768
    saved=(run/EXPORT_SUBDIR/"DATA01_ADC1_NATIVE_CALIBRATED.f32").read_bytes()
    with zipfile.ZipFile(archive) as z:
        orig=z.read(next(n for n in z.namelist()
                         if n.endswith(".bin") and "-ADC1-" in n))
    assert saved==orig[256*4:768*4]
    assert len(saved)==512*4
    receipt=json.loads(
        (run/EXPORT_SUBDIR/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert receipt["source_segment_boundaries_at_next_native_complete_frame"]
    assert not receipt["source_segment_boundaries_are_last_native_status_poll"]
    assert receipt["native_source_frame_mark_evidence"]["authoritative"]
    assert not receipt["hardware_command_sent"]
    assert not receipt["original_tmkvthread_byte_exact_recording"]


@pytest.mark.parametrize("tamper",(
    "foreign","denied","mask","rollback","after-end","modified-sha","absent",
))
def test_unsafe_frame_marks_never_fall_back_to_stale_900ms_windows(
        tmp_path,tamper):
    run,_,flow,ledger=synthetic_marked_run(tmp_path,tamper=tamper)
    with pytest.raises((ValueError,KeyError)):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()
    assert ledger.frame_marks_required
    assert not ledger.frame_marks_verified


def test_frame_mark_local_request_rejects_duplicate_foreign_or_symlink(
        tmp_path):
    inbox=tmp_path/INBOX
    inbox.mkdir()
    plan=OriginalLiveFilePlan()
    received=submit_native_frame_mark(tmp_path,1,RUN,"values_begin",plan)
    assert received["queued_local_only"]
    assert received["device_commands_sent"] is False
    with pytest.raises(ValueError):
        submit_native_frame_mark(tmp_path,1,RUN,"values_end",plan)
    with pytest.raises(ValueError):
        submit_native_frame_mark(tmp_path,2,"FOREIGN","data_begin",plan)
    with pytest.raises(ValueError):
        submit_native_frame_mark(tmp_path,2,RUN,"set_rate",plan)
    link=tmp_path/"linked"
    link.symlink_to(inbox,target_is_directory=True)
    with pytest.raises(ValueError):
        submit_native_frame_mark(link.parent/"linked",2,RUN,"data_begin",plan)


def test_legacy_synthetic_non_device_writer_keeps_explicit_poll_mode(
        tmp_path):
    run=tmp_path/RUN
    run.mkdir()
    archive=fixture_zip(run)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive))
    status=source_status()
    ledger=OriginalLiveWriteLedger()
    ledger.observe(status)
    plan=OriginalLiveFilePlan().bind_status(status)
    ledger.toggle("data",plan)
    ledger.observe(source_status(adc_samples=512,frames=30,raw=80000))
    ledger.toggle("data",plan)
    ledger.finish(accepted=True)
    assert not ledger.frame_marks_required
    result=export_source_write_windows(ledger,flow,run)
    assert not result["verified_frame_boundaries"]
    assert result["native_mark_requests"]==0


def test_marked_writer_cannot_rearm_after_bad_packet_even_if_network_recovers():
    writer=OriginalLiveWriteLedger()
    first=source_status()
    writer.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    writer.toggle("data",plan)
    writer.register_native_frame_mark({
        "source":"MVK_NATIVE_LOCAL_FRAME_MARK_REQUEST_V1",
        "sequence":1,"session_id":RUN,"event":"data_begin",
        "queued_local_only":True,"device_commands_sent":False,
    },plan)
    with pytest.raises(ValueError):
        writer.observe(source_status(
            adc_samples=512,aux=1,frames=30,raw=45000,
            packets_bad=True))
    assert writer.frame_marks_failed
    assert writer.data_stage==2
    assert not writer.trustworthy
    # A new valid receiver status may verify transport but MUST NOT make
    # the old source write channel selection safe again in the same run.
    writer.observe(source_status(
        adc_samples=768,aux=1,frames=40,raw=60000))
    assert not writer.trustworthy
    with pytest.raises(ValueError):
        writer.toggle("data",plan)
    assert writer.frame_marks_required
    assert not writer.frame_marks_verified
