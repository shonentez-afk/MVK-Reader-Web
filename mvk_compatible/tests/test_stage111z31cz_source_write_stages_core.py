"""Source _Unit125:00809414 stages -> real checked Native interval output.

Synthetic input ONLY. Tests verify no instrument command and no original
Delphi BIN/TSXML claims. All operations run without TCP or physical device.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zipfile

import pytest

from ..core.original_live_pagefile import OriginalLiveFilePlan
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,OriginalLiveWriteLedger,
    STAGE_IDLE,STAGE_OPEN,STAGE_STREAMING,
    export_source_write_windows,
)
from ..core.original_connected_status import SYSTEM_STATUS_KEYS
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from .test_offline_core import fixture_zip
from .test_stage111z31cy_native_tach_evidence import (
    synthetic_tach_native_zip,
)

RUN="TEST_2026-11-16_08-16-18.000"


def source_status(*,session=RUN,adc_samples=0,tach_samples=0,
                  aux=0,frames=1,raw=512,packets_bad=False):
    if adc_samples%256 or tach_samples%64:
        raise AssertionError("Synthetic source must be 256 ADC / 64 TACH")
    return {
        "schema":"MVK_NATIVE_R6_LIVE_STATUS_V1",
        "read_only_no_app_payload_sent":True,
        "phase":"RECORDING",
        "session_id":session,
        "frames_decoded":frames,
        "raw_bytes":raw,
        "aux4700_updates":aux,
        "invalid_frames":0,
        "capture_only":False,
        "snapshot_stale":False,
        "seconds_since_last_packet":0.2,
        "channels":[
            {"channel":i,
             "type":"ADC" if i<=8 else "TACH",
             "frames":adc_samples//256 if i<=8 else tach_samples//64,
             "samples":adc_samples if i<=8 else tach_samples,
             "sample_rates_hz":[65536] if (
                i<=8 and adc_samples) else (
                [32768] if i>8 and tach_samples else []),
             "sequence_discontinuities":(
                1 if packets_bad and i==10 else 0),
             "nonfinite_samples":0}
            for i in range(1,11)],
    }


def test_real_source_write_data_and_values_stages_and_mask_latch():
    session=OriginalLiveWriteLedger()
    assert session.data_stage==session.values_stage==STAGE_IDLE
    source=source_status()
    assert session.observe(source)["has_verifiable_live_status"]
    plan=OriginalLiveFilePlan().bind_status(source)
    session.toggle("data",plan)
    assert session.data_stage==STAGE_OPEN
    assert session.values_stage==STAGE_IDLE
    assert session.receipt()["write_data_requested"]
    session.toggle("values",plan)
    assert session.values_stage==STAGE_STREAMING
    # Checkbox changes AFTER start cannot alter an active file mask.
    changed=plan.set_checked("channels",0,False)
    session.observe(source_status(adc_samples=512,aux=1,frames=30,raw=18000))
    assert session.data_stage==STAGE_STREAMING
    session.toggle("data",changed)
    session.toggle("values",changed)
    assert session.data_stage==session.values_stage==STAGE_IDLE
    assert len(session.windows)==2
    assert session.windows[0].channels[0] is True
    assert session.windows[1].spec==plan.spec
    assert session.windows[0].end_samples[0]==512
    assert session.windows[1].end_aux==1
    session.finish(accepted=True)
    assert session.finished
    assert not session.receipt()["hardware_commands_sent"]
    assert session.receipt()["native_full_raw_not_filtered"]
    with pytest.raises(ValueError):
        session.toggle("data",plan)
    assert len(SYSTEM_STATUS_KEYS)==15


@pytest.mark.parametrize("bad",(
    {"session":"TEST_2026-11-16_08-20-00.000"},
    {"adc_samples":256,"aux":0,"frames":0},
    {"adc_samples":256,"aux":0,"frames":5,"packets_bad":True},
))
def test_original_writer_stops_on_foreign_run_bad_counter_or_packet(bad):
    writer=OriginalLiveWriteLedger()
    first=source_status()
    writer.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    writer.toggle("data",plan)
    with pytest.raises(ValueError):
        writer.observe(source_status(**bad))
    assert writer.data_stage==STAGE_IDLE
    assert not writer.receipt()["write_data_requested"]
    assert writer.errors
    assert len(writer.windows)==0


def test_selected_two_original_write_buttons_generate_REAL_local_files(
        tmp_path):
    run=tmp_path/RUN
    run.mkdir()
    archive=fixture_zip(run)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    ledger=OriginalLiveWriteLedger()
    first=source_status()
    ledger.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    ledger.toggle("data",plan)
    ledger.toggle("values",plan)
    ledger.observe(source_status(
        adc_samples=512,aux=1,frames=30,raw=20000))
    ledger.toggle("data",plan)
    ledger.toggle("values",plan)
    ledger.finish(accepted=True)
    report=export_source_write_windows(ledger,flow,run)
    assert report["windows"]==2
    assert report["files_written"]==9
    folder=run/EXPORT_SUBDIR
    assert folder.exists()
    manifest=json.loads(
        (folder/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text("utf-8"))
    assert manifest["original_tmkvthread_byte_exact_recording"] is False
    assert not manifest["hardware_command_sent"]
    assert manifest["source_segment_boundaries_are_last_native_status_poll"]
    assert manifest["run_id"]==RUN
    assert len(manifest["files"])==9
    for i in range(1,9):
        name=f"DATA01_ADC{i}_NATIVE_CALIBRATED.f32"
        data=(folder/name).read_bytes()
        assert len(data)==512*4
        assert any(c["name"]==name and c["sha256"]==
                   sha256(data).hexdigest()
                   for c in manifest["files"])
        with zipfile.ZipFile(archive) as z:
            original=next(
                n for n in z.namelist() if f"-ADC{i}-" in n
                and n.endswith(".bin"))
            assert data==z.read(original)[:len(data)]
    csv=(folder/"VALUES02_NATIVE_VERIFIED_SELECTED.csv").read_text(
        encoding="utf-8-sig")
    assert csv.startswith("AUX_TICK_INDEX;ADC;CATEGORY")
    assert "\n" in csv
    assert session.updates>=1
    with pytest.raises(ValueError):
        export_source_write_windows(ledger,flow,run)


def test_tach_is_byte_preserved_and_never_relabelled_original(tmp_path):
    run=tmp_path/RUN
    run.mkdir()
    archive=synthetic_tach_native_zip(run)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    zero=source_status()
    first=source_status(adc_samples=512,tach_samples=0,
                        aux=0,frames=20,raw=13000)
    last=source_status(adc_samples=768,tach_samples=128,
                       aux=1,frames=45,raw=41000)
    ledger=OriginalLiveWriteLedger()
    ledger.observe(zero)
    ledger.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    for i in range(8):
        plan=plan.set_checked("channels",i,False)
    plan=plan.set_checked("channels",8,True)
    plan=plan.set_checked("channels",9,True)
    ledger.toggle("data",plan)
    ledger.observe(last)
    ledger.toggle("data",plan)
    ledger.finish(accepted=True)
    report=export_source_write_windows(ledger,flow,run)
    assert report["files_written"]==2
    for n in (1,2):
        filename=f"DATA01_TACH{n}_NATIVE_UNSCALED.f32"
        output=(run/EXPORT_SUBDIR/filename).read_bytes()
        with zipfile.ZipFile(archive) as z:
            assert output==z.read(
                f"TACH{n}_NATIVE_UNCALIBRATED.f32")
    assert not list((run/EXPORT_SUBDIR).glob("*.tsxml"))


def test_untrusted_stopped_run_does_not_create_local_directories(tmp_path):
    run=tmp_path/RUN
    run.mkdir()
    archive=fixture_zip(run)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1)
    ledger=OriginalLiveWriteLedger()
    initial=source_status()
    ledger.observe(initial)
    ledger.toggle("data",OriginalLiveFilePlan().bind_status(initial))
    ledger.finish(accepted=False)
    assert ledger.windows==[]
    assert export_source_write_windows(ledger,flow,run)["windows"]==0
    assert not (run/EXPORT_SUBDIR).exists()


def test_independent_operator_elapsed_and_immutable_finalize_boundary():
    from datetime import datetime,timezone,timedelta
    start=datetime(2026,11,24,1,0,0,tzinfo=timezone.utc)
    ledger=OriginalLiveWriteLedger()
    status=source_status()
    ledger.observe(status)
    plan=OriginalLiveFilePlan().bind_status(status)
    ledger.toggle("data",plan,now=start)
    ledger.toggle("values",plan,now=start+timedelta(seconds=2))
    times=ledger.elapsed_receipt(now=start+timedelta(seconds=65))
    assert times["data_elapsed_text"]=="00:01:05"
    assert times["values_elapsed_text"]=="00:01:03"
    assert not times["delphi_file_open_time_verified"]
    ledger.observe(source_status(adc_samples=512,aux=1,frames=30,raw=18000))
    ledger.begin_finalization(now=start+timedelta(seconds=70))
    assert ledger.receipt()["source_writer_finalizing"]
    assert ledger.elapsed_receipt(now=start+timedelta(seconds=999))[
        "data_elapsed_text"]=="00:01:10"
    with pytest.raises(ValueError,match="finalizing"):
        ledger.toggle("data",plan)
    ledger.observe(source_status(adc_samples=768,aux=2,frames=40,raw=23000))
    ledger.finish(accepted=True)
    assert len(ledger.windows)==2
    assert all(w.operator_end_utc==(start+timedelta(seconds=70)).isoformat()
               for w in ledger.windows)
    assert all(w.end_samples[0]==512 for w in ledger.windows)
    assert ledger.data_stage==ledger.values_stage==STAGE_IDLE
    assert ledger.elapsed_receipt()["data_elapsed_seconds"] is None
    ledger.finish(accepted=True)
    assert len(ledger.windows)==2


def test_two_active_writers_reserve_total_window_limit():
    ledger=OriginalLiveWriteLedger()
    status=source_status()
    ledger.observe(status)
    plan=OriginalLiveFilePlan().bind_status(status)
    for _ in range(7):
        ledger.toggle("data",plan)
        ledger.toggle("data",plan)
    ledger.toggle("data",plan)
    with pytest.raises(ValueError,match="eight"):
        ledger.toggle("values",plan)
    ledger.begin_finalization()
    ledger.finish(accepted=True)
    assert len(ledger.windows)==8


def test_failed_mark_finalize_does_not_raise_or_create_active_window():
    ledger=OriginalLiveWriteLedger()
    status=source_status()
    ledger.observe(status)
    plan=OriginalLiveFilePlan().bind_status(status)
    ledger.toggle("data",plan)
    ledger.frame_marks_required=True
    ledger.frame_marks_failed=True
    ledger.begin_finalization()
    ledger.finish(accepted=True)
    assert ledger.finished and not ledger.windows
    assert ledger.data_stage==STAGE_IDLE
