"""BS source-aware original pnMeasureControls Core and real Native VALUES table.

Synthetic fixtures only; no source originals or hardware. Zero device commands.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import csv
from zipfile import BadZipFile

import numpy as np
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.offline_export import OfflineSession
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_pagefile_recording import OriginalPageFileSelection
from ..core.native_r6_live_preview import LivePreview, PreviewADC
from ..core.original_measure_controls import (
    OriginalMeasureState,DFM_PANEL,DFM_BUTTONS,DFM_MEASURE_HEIGHT,
    DFM_VISIBLE_AT_DESIGN,ORIGINAL_RATE_RADIO_ITEMS,
    SOURCE,table_rows,export_verified_table_csv,
)


def _synthetic_preview(session="SYNTHETIC-CAPTURE",rate=32000):
    data=np.linspace(-.2,.2,2048,dtype="<f4")
    channel=PreviewADC(
        number=1,rate_hz=rate,first_index=1024,next_index=3072,
        samples=data,sha256=sha256(data.tobytes()).hexdigest())
    return LivePreview(
        session_id=session,
        updated_utc=datetime(2026,11,12,tzinfo=timezone.utc),
        raw_bytes=4096,frames_decoded=20,channels={1:channel},
    )


def test_source_original_five_button_geometry_tags_and_flag_semantics():
    assert DFM_PANEL==(6,6,843,41)
    assert DFM_MEASURE_HEIGHT==53
    assert DFM_VISIBLE_AT_DESIGN is False
    assert ORIGINAL_RATE_RADIO_ITEMS==5
    assert tuple(x[0] for x in DFM_BUTTONS)==(
        "bFreezeUpdate","bSampleRate","bWriteTable",
        "bWriteAdc","bWriteValues")
    assert tuple(x[1:5] for x in DFM_BUTTONS)==(
        (6,0,160,41),(172,0,160,41),(338,0,160,41),
        (504,0,160,41),(670,0,160,41))
    assert tuple(x[5] for x in DFM_BUTTONS)==(0,0,0,3,8)
    assert tuple(x[6] for x in DFM_BUTTONS)==tuple(range(5))


def test_original_measure_state_native_live_preview_freeze_does_not_write_device():
    model=OriginalMeasureState()
    assert model.mode=="idle"
    assert not model.frozen
    with pytest.raises(ValueError,match="active"):
        model.toggle_freeze()
    live=model.begin_live()
    assert live.mode=="live" and not live.frozen
    seen=live.accept_preview(_synthetic_preview())
    assert seen.preview_session_id=="SYNTHETIC-CAPTURE"
    assert seen.observed_sample_rate_hz==32000
    assert seen.observed_rates_per_adc==((1,32000),)
    frozen=seen.toggle_freeze()
    assert frozen.frozen
    assert seen.frozen is False
    newer=frozen.accept_preview(_synthetic_preview(rate=16000))
    assert newer.frozen and newer.observed_sample_rate_hz==16000
    assert newer.report()["original_thread_freeze_flag_set"] is False
    assert not newer.report()["native_recorder_filter_or_sample_rate_changed"]
    assert not newer.report()["device_commands_sent"]
    assert not newer.report()["original_sample_rate_menu_values_verified"]
    assert newer.invalidate_preview().observed_sample_rate_hz is None
    with pytest.raises(ValueError,match="another capture"):
        newer.accept_preview(_synthetic_preview("ANOTHER-CAPTURE"))
    assert newer.finish()==OriginalMeasureState()
    with pytest.raises(ValueError):
        OriginalMeasureState(mode="offline",frozen=True)


def test_original_table_export_all_eight_adc_current_real_dsp(tmp_path):
    archive=fixture_zip(tmp_path,sample_count=4096)
    old_hash=sha256(archive.read_bytes()).hexdigest()
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    original=OriginalMeasureState().open_offline(flow)
    assert original.mode=="offline"
    assert not original.report()["device_commands_sent"]
    data=table_rows(flow)
    assert len(data)==8*(24+43)
    assert data[0][0]==1 and data[0][1]=="VALUE"
    assert data[-1][0]==8 and data[-1][1]=="BAND"
    assert all(x[0] in tuple(range(1,9)) for x in data)
    out=tmp_path/"TABLE-2026-11-12--15-35-00.csv"
    report=export_verified_table_csv(flow,out)
    assert report["source"]==SOURCE and report["table_saved"]
    assert report["rows"]==536
    assert report["all_written_rows_reopened_and_verified"]
    assert report["device_io_executed"] is False
    assert not report["original_tmkvthread_write_table_executed"]
    assert not report["original_delphi_table_binary_parity_verified"]
    assert "source_file" not in report
    with out.open(encoding="utf-8-sig",newline="") as f:
        lines=list(csv.reader(f,delimiter=";"))
    assert len(lines)==1+536 and lines[1][0]=="1"
    assert lines[1][1]=="VALUE"
    assert report["checksum_sha256"]==sha256(out.read_bytes()).hexdigest()
    assert sha256(archive.read_bytes()).hexdigest()==old_hash
    with pytest.raises(ValueError,match="NEW"):
        export_verified_table_csv(flow,out)
    assert sha256(archive.read_bytes()).hexdigest()==old_hash


def test_table_respects_real_pagefile_checked_adc_spec_values(tmp_path):
    source=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(source),channel=4)
    flags=OriginalPageFileSelection.for_flow(flow)
    for adc in range(2,9):
        flags=flags.set_checked("channels",adc-1,False,flow=flow)
    for i in range(43):
        flags=flags.set_checked("spec",i,i==5,flow=flow)
    for i in range(67):
        flags=flags.set_checked("values",i,i in (0,24),flow=flow)
    assert flags.checked("channels")==(0,)
    rows=table_rows(flow,flags)
    assert len(rows)==3
    assert [r[1] for r in rows]==["VALUE","BAND","SPEC"] or [
        r[1] for r in rows]==["VALUE","SPEC","BAND"]
    assert all(row[0]==1 for row in rows)
    dest=tmp_path/"chosen_values.csv"
    result=export_verified_table_csv(flow,dest,selection=flags)
    assert result["rows"]==3
    assert result["selected_result_flags_used"]
    assert result["channels"]==[1]
    with dest.open(encoding="utf-8-sig",newline="") as f:
        data=list(csv.reader(f,delimiter=";"))
    assert len(data)==4
    assert not any(str(source) in repr(x) for x in (result,))


def test_direct_bin_table_refused_without_dsp_and_output_not_created(tmp_path):
    path,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    session=DirectBinSession.open(path)
    flow=OfflineMeasurementFlow.bind(session)
    with pytest.raises(ValueError,match="Native"):
        table_rows(flow)
    assert OriginalMeasureState().open_offline(flow).mode=="offline"
    out=tmp_path/"no_dsp.csv"
    with pytest.raises(ValueError,match="Native"):
        export_verified_table_csv(flow,out)
    assert not out.exists()
    assert path.is_file() and sidecar.is_file()


def test_source_table_does_not_accept_stale_malformed_or_overwrite(tmp_path):
    source=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(source))
    selections=OriginalPageFileSelection.for_flow(flow)
    no_rows=selections
    for i in range(43):
        no_rows=no_rows.set_checked("spec",i,False,flow=flow)
    for i in range(67):
        no_rows=no_rows.set_checked("values",i,False,flow=flow)
    with pytest.raises(ValueError,match="empty"):
        table_rows(flow,no_rows)
    blocked=tmp_path/"already.csv"
    blocked.write_text("DONOTTOUCH")
    with pytest.raises(ValueError,match="NEW"):
        export_verified_table_csv(flow,blocked)
    assert blocked.read_text()=="DONOTTOUCH"
    old_sha=sha256(source.read_bytes()).hexdigest()
    source.write_bytes(source.read_bytes()[:-512])
    with pytest.raises((ValueError,KeyError,BadZipFile)):
        export_verified_table_csv(flow,tmp_path/"not_created.csv")
    assert not (tmp_path/"not_created.csv").exists()
    assert sha256(source.read_bytes()).hexdigest()!=old_sha
