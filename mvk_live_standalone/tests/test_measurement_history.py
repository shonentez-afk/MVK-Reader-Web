"""Archive regression: all eight real original AUX rows + SHA-checked NPZ history."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mvk_live_standalone.original_dsp import _THIRD_HZ
from mvk_live_standalone.measurement_history import (
    MeasurementHistory,MAX_OVERLAYS,VENDOR,LOCAL,metric_details,
)
from mvk_live_standalone.recordings import save_snapshot


def vendor_row(adc,update,utc="2026-11-18T08:00:00Z"):
    return {
        "adc":adc,"time_utc":utc,"update":update,"status_raw":0,
        "status_hex":"0x00000000",
        "not_ready":{"fs16":False,"fs64":False,"fs512":False},
        "nonfinite_fields":0,
        "third_octave_hz":_THIRD_HZ.tolist(),
        "third_octave_acceleration_rms":[adc*update*.1+i*.01 for i in range(43)],
        "band_rms":[adc*update*.2+i for i in range(24)],
        "band_peak_equiv":[adc*update*.4+i for i in range(24)],
        "band_span_equiv":[adc*update*.8+i for i in range(24)],
    }


def test_all_eight_calculated_adc_frames_are_persisted_and_trend_by_selected_adc(tmp_path):
    archive=MeasurementHistory(tmp_path/"archive")
    run=tmp_path/"TEST_2026-11-18_08-00-00.000"
    run.mkdir()
    rows=[]
    for tick in (1,2,3):
        for adc in range(1,9):
            row=vendor_row(adc,tick,f"2026-11-18T08:00:0{tick}Z")
            rows.append(json.dumps(row,ensure_ascii=False).encode()+b"\n")
    (run/"aux4700.jsonl").write_bytes(b"".join(rows))
    assert archive.sync_aux_jsonl(run,run.name,batch=240)==24
    assert archive.sync_aux_jsonl(run,run.name)==0
    # The index survives restart, and each original tick/ADC appears once.
    again=MeasurementHistory(tmp_path/"archive")
    assert len(again.entries(1,kind="vendor"))==3
    assert len(again.entries(8,kind="vendor"))==3
    assert len(again.entries(5,kind="window"))==0
    points,label,unit,truncated=again.trend(3,"band_peak_equiv:0")
    assert not truncated and len(points)==3
    assert [v for _,v in points]==pytest.approx([1.2,2.4,3.6])
    assert "Пик" in label and "единица" in unit
    lines,label,unit,_=again.trend(8,"third_octave:0")
    assert [v for _,v in lines]==pytest.approx([.8,1.6,2.4])
    assert unit=="м/с²"
    assert "0.63" in label
    original=again.get_vendor(again.entries(3,"vendor")[0])
    assert original.adc==3 and original.update==3 and original.has_extended


def test_jsonl_is_incremental_bounded_and_never_imports_partial_line(tmp_path):
    history=MeasurementHistory(tmp_path/"db")
    session="TEST_2026-11-18_08-00-00.000"
    folder=tmp_path/session
    folder.mkdir()
    row=json.dumps(vendor_row(2,1)).encode()+b"\n"
    partial=json.dumps(vendor_row(3,1)).encode()
    filename=folder/"aux4700.jsonl"
    filename.write_bytes(row+partial)
    assert history.sync_aux_jsonl(folder,session)==1
    assert [r.adc for r in history.entries(2,"vendor")]==[2]
    assert history.entries(3,"vendor")==[]
    with filename.open("ab") as f:f.write(b"\n")
    assert history.sync_aux_jsonl(folder,session)==1
    assert history.sync_aux_jsonl(folder,session)==0
    assert len(history.entries(3,"vendor"))==1
    # The file must only grow; no stale cursor replays after truncation.
    filename.write_bytes(row[:10])
    with pytest.raises(ValueError,match="обрезан"):
        history.sync_aux_jsonl(folder,session)
    with pytest.raises(ValueError):
        history.sync_aux_jsonl(folder,session,batch=100000)


def test_live_status_fallback_deduplicates_against_full_original_log(tmp_path):
    history=MeasurementHistory(tmp_path/"archive")
    session="TEST_2026-11-18_08-00-00.000"
    row=vendor_row(5,2)
    status={
        "session_id":session,"phase":"RECORDING",
        "source_tcp_multi_socket":False,
        "dsp_original_aux4700_channels":[row],
    }
    assert history.record_vendor_status(status)==1
    assert history.record_vendor_status(status)==0
    assert history.record_vendor_status({**status,"source_tcp_multi_socket":True})==0
    folder=tmp_path/session
    folder.mkdir()
    (folder/"aux4700.jsonl").write_text(json.dumps(row)+"\n")
    assert history.sync_aux_jsonl(folder,session)==1
    assert len(history.entries(5,"vendor"))==1


def test_original_dsp_nonfinite_is_missing_not_synthetic_zero(tmp_path):
    history=MeasurementHistory(tmp_path/"archive")
    row=vendor_row(1,1)
    row["band_peak_equiv"][7]=None
    history.record_vendor_row("TEST_A",row)
    pts,*_=history.trend(1,"band_peak_equiv:7")
    assert pts==[]
    pts,*_=history.trend(1,"band_peak_equiv:6")
    assert len(pts)==1 and pts[0][1]!=0
    row_bad=vendor_row(1,2)
    row_bad["band_rms"]=[1]*22
    with pytest.raises(ValueError):
        history.record_vendor_row("TEST_A",row_bad)


def test_npz_history_is_sha_validated_and_time_rms_local_not_vendor(tmp_path):
    history=MeasurementHistory(tmp_path/"archive")
    fs=8192
    x=(np.sqrt(2)*np.sin(2*np.pi*128*np.arange(8192)/fs)).astype("<f4")
    idx=history.capture_npz(x,adc=2,fs=fs,session="TEST_LOCAL",
                             capture_end=8192,
                             saved_utc="2026-11-18T08:12:00+00:00")
    assert idx>0
    assert len(history.entries(1,"window"))==0
    entry=history.entries(2,"window")[0]
    assert entry.source==LOCAL
    snap=history.get_window(entry)
    np.testing.assert_array_equal(snap.acceleration_m_s2,x)
    pts,label,unit,_=history.trend(2,"time_rms")
    assert len(pts)==1 and pts[0][1]==pytest.approx(1,rel=.02)
    assert unit=="м/с²"
    pts,label,unit,_=history.trend(2,"velocity_rms_10_1000")
    assert len(pts)==1 and unit=="мм/с"
    assert history.trend(2,"third_octave:4")[0]==[]
    assert history.capture_npz(x,adc=2,fs=fs,session="TEST_LOCAL",
                                capture_end=8192)==idx
    assert len(history.entries(2,"window"))==1
    assert len(history.entries(2,"all"))==1
    assert MAX_OVERLAYS>=2


def test_import_existing_npz_does_not_treat_file_time_as_device_measurement(tmp_path):
    archive=MeasurementHistory(tmp_path/"archive")
    fs=8192
    x=np.sin(2*np.pi*88*np.arange(8192)/fs).astype("<f4")
    external=tmp_path/"external.npz"
    save_snapshot(external,x,adc=6,rate_hz=fs,
                  session_id="OFFLINE_IMPORTED",capture_end=8192)
    idx=archive.import_npz(external,saved_utc="2026-11-18T11:00:00Z")
    assert idx==archive.import_npz(external)
    assert archive.entries(6,"window")[0].time_utc.startswith("2026-11-18T11")
    assert (archive.samples).exists()
    np.testing.assert_array_equal(
        archive.get_window(archive.entries(6,"window")[0]).acceleration_m_s2,x)
    with external.open("r+b") as f:
        f.seek(35)
        f.write(b"garbage")
    with pytest.raises((ValueError,OSError,Exception)):
        archive.import_npz(external)


def test_metric_family_keeps_units_separate():
    assert "мм/с" in metric_details("velocity_rms_10_1000")[1]
    assert metric_details("third_octave:2")[1]=="м/с²"
    assert "подтверждена" in metric_details("band_span_equiv:3")[1]
    with pytest.raises(ValueError):
        metric_details("third_octave:43")
    with pytest.raises(ValueError):
        metric_details("band_rms:24")
