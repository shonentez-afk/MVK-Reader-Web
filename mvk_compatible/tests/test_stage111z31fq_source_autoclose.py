"""Source Task2 writer force-close: original 008089A8/00809414, local only."""
from __future__ import annotations
from hashlib import sha256
import json
import zipfile

import pytest

from .test_offline_core import fixture_zip
from .test_stage111z31cz_source_write_stages_core import RUN,source_status
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_live_pagefile import OriginalLiveFilePlan
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,OriginalLiveWriteLedger,export_source_write_windows,
)
from ..core.source_frame_mark_protocol import (
    AUDIT,AUDIT_SCHEMA,FRAME_BOUNDARY,INBOX,submit_native_frame_mark,
)


def _force_close_source(tmp_path,mutator=None):
    run=tmp_path/RUN
    run.mkdir()
    archive=fixture_zip(run)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive))
    before=source_status(adc_samples=0,aux=0,frames=1,raw=1024)
    after=source_status(adc_samples=512,aux=1,frames=30,raw=50000)
    ledger=OriginalLiveWriteLedger()
    ledger.observe(before)
    plan=OriginalLiveFilePlan().bind_status(before)
    (tmp_path/INBOX).mkdir()
    ledger.toggle("data",plan)
    mark=submit_native_frame_mark(tmp_path,1,RUN,"data_begin",plan)
    ledger.register_native_frame_mark(mark,plan)
    ledger.observe(after)
    # Native worker will finalize while "WriteData" is still ON.
    ledger.finish(accepted=True)
    assert len(ledger.windows)==1 and len(ledger.frame_mark_actions)==1
    with zipfile.ZipFile(archive) as z:
        raw_sha=json.loads(z.read("EXPORT_AUDIT.json"))["source_raw_sha256"]
    requested=json.loads((tmp_path/INBOX/"0001.json").read_text())
    ended="2026-11-18T04:40:00Z"
    counts=[4096]*8+[0,0]
    start={
        "sequence":1,"event":"data_begin",
        "requested_utc":requested["requested_utc"],
        "applied_utc":ended,
        "applied":True,"frames_decoded":10,
        "aux4700_updates":0,
        "channel_samples":[256]*8+[0,0],
        "channels":list(plan.channels),
        "spec":list(plan.spec),
        "values":list(plan.values),
        "device_commands_sent":False,
        "boundary":FRAME_BOUNDARY,
    }
    close={
        "event":"data_end","requested_utc":ended,
        "applied_utc":ended,"applied":True,
        "reason":"SOURCE_TMVKTHREAD_FORCED_WRITER_CLOSE",
        "frames_decoded":100,
        "aux4700_updates":2,
        "channel_samples":counts,
        "channels":list(plan.channels),
        "spec":list(plan.spec),
        "values":list(plan.values),
        "device_commands_sent":False,
        "boundary":"AT_SOURCE_TASK2_FINALIZE",
    }
    doc={
        "schema":AUDIT_SCHEMA,
        "session_id":RUN,
        "source_raw_sha256":raw_sha,
        "end_frames_decoded":100,
        "end_aux4700_updates":2,
        "end_channel_samples":counts,
        "device_commands_sent":False,
        "source_frame_boundary":True,
        "original_delphi_file_parity_verified":False,
        "requests":[start],
        "auto_closed_on_capture_end":[close],
    }
    summary={
        "raw_sha256":raw_sha,
        "end_reason":"STOPPED_BY_USER",
        "ended_utc":ended,
        "frames_decoded":100,
        "aux4700_updates":2,
        "channels":[{"samples":n} for n in counts],
        "source_frame_marks_count":1,
    }
    if mutator is not None:
        mutator(doc,summary)
    raw=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode()
    summary["source_frame_marks_sha256"]=sha256(raw).hexdigest()
    (run/AUDIT).write_bytes(raw)
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
    return run,flow,ledger


def test_auto_closed_source_writer_uses_go_final_counts_not_old_qt_status(tmp_path):
    run,flow,ledger=_force_close_source(tmp_path)
    assert ledger.windows[0].end_samples[0]==512 # last Qt poll
    report=export_source_write_windows(ledger,flow,run)
    assert report["verified_frame_boundaries"]
    assert ledger.frame_marks_verified
    assert ledger.windows[0].start_samples[0]==256
    assert ledger.windows[0].end_samples[0]==4096 # authentic Go final
    target=run/EXPORT_SUBDIR
    out=(target/"DATA01_ADC1_NATIVE_CALIBRATED.f32").read_bytes()
    with zipfile.ZipFile(run/"synthetic.zip") as z:
        raw=z.read(next(n for n in z.namelist() if n.endswith(".bin")
                       and "-ADC1-" in n))
    assert out==raw[256*4:4096*4]
    audit=json.loads((target/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert audit["native_source_frame_mark_evidence"][
        "source_thread_auto_closed_writers"]==1
    assert audit["native_source_frame_mark_evidence"]["accepted_events"]==1
    assert not audit["original_tmkvthread_byte_exact_recording"]


@pytest.mark.parametrize("tamper",[
    lambda d,s:d["auto_closed_on_capture_end"][0].update(
        channel_samples=[4095]+[4096]*7+[0,0]),
    lambda d,s:d["auto_closed_on_capture_end"][0].update(
        requested_utc="2026-11-18T04:20:00Z"),
    lambda d,s:d["auto_closed_on_capture_end"][0]["channels"].__setitem__(0,False),
    lambda d,s:s.update(end_reason="REMOTE_DISCONNECTED"),
    lambda d,s:d["auto_closed_on_capture_end"].append(
        dict(d["auto_closed_on_capture_end"][0])),
    lambda d,s:d["auto_closed_on_capture_end"][0].update(
        event="values_end"),
])
def test_tampered_go_task2_autoclose_fails_closed(tmp_path,tamper):
    run,flow,ledger=_force_close_source(tmp_path,tamper)
    with pytest.raises(ValueError):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()
