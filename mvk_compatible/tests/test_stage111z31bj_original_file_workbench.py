"""Stage111Z31BJ: original File page presents REAL checked Core data.

No original executable, x32dbg, device or private measurement bytes.
The tests reuse deterministic Native ZIP and original BIN/TSXML fixtures.
"""
import copy
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.direct_bin_session import DirectBinSession
from mvk_compatible.core.offline_measurement_flow import OfflineMeasurementFlow
from mvk_compatible.core.original_file_workbench import (
    SOURCE, source_file_workbench,
)


def test_native_zip_one_selected_adc_tick_presents_24_and_43_real_banks(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    flow=OfflineMeasurementFlow.bind(session,channel=2)
    no_values=source_file_workbench(flow)
    assert len(no_values.value_rows)==1
    assert len(no_values.spectrum_rows)==1
    assert not no_values.dsp_verified_for_selection
    assert not no_values.device_action_allowed
    source=flow.source_record()
    verified=flow.status_snapshot()
    result=source_file_workbench(flow,verified_status=verified)
    assert result.source_basename==source["data_file_label"]
    assert result.sample_count==source["sample_count"]
    assert result.bin_sha256==source["source_bin_sha256"]
    assert result.selected_channel==2
    assert result.available_channels==tuple(range(1,9))
    assert len(result.value_rows)==24
    assert len(result.spectrum_rows)==43
    assert verified["channels"][1]["parameters_24"][0]["name"] in result.value_rows[0]
    assert verified["channels"][1]["third_octave"][0]["name"] in result.spectrum_rows[0]
    assert result.report()["dsp_verified_for_selection"]
    assert result.report()["original_runtime_parity_verified"] is False
    assert result.report()["device_action_allowed"] is False
    assert any(x[0]=="SHA256 источника BIN" and x[1]==source["source_bin_sha256"]
               for x in result.metadata)
    assert any(x[0]=="Тик VALUES" and "/" in x[1] for x in result.metadata)


def test_native_zip_rejects_stale_tick_and_cross_channel_banks(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    flow=OfflineMeasurementFlow.bind(session,channel=3)
    snapshot=flow.status_snapshot()
    wrong_tick=flow.select(tick_index=0)
    if wrong_tick.tick_index!=flow.tick_index:
        with pytest.raises(ValueError,match="session/tick"):
            source_file_workbench(wrong_tick,verified_status=snapshot)
    tampered=copy.deepcopy(snapshot)
    tampered["channels"][2]["channel"]=8
    with pytest.raises(ValueError,match="banks"):
        source_file_workbench(flow,verified_status=tampered)
    tampered=copy.deepcopy(snapshot)
    tampered["channels"][2]["parameters_24"][0]["value"]=float("nan")
    with pytest.raises(ValueError,match="Non-finite"):
        source_file_workbench(flow,verified_status=tampered)
    tampered=copy.deepcopy(snapshot)
    tampered["serial"]="other-original-device"
    with pytest.raises(ValueError,match="session/tick"):
        source_file_workbench(flow,verified_status=tampered)


def test_direct_bin_file_page_never_invents_original_dsp(tmp_path):
    bin_path,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    session=DirectBinSession.open(bin_path)
    flow=OfflineMeasurementFlow.bind(session)
    model=source_file_workbench(flow)
    rec=flow.source_record()
    assert model.selected_channel==4
    assert model.available_channels==(4,)
    assert model.sample_count==8192
    assert model.sample_rate_hz==rec["sample_rate_hz"]
    assert model.bin_sha256==rec["source_bin_sha256"]
    assert not model.dsp_verified_for_selection
    assert len(model.spectrum_rows)==1
    assert len(model.value_rows)==1
    assert "Нет подтверждённых приборных VALUES/AUX" in model.value_rows[0]
    assert "не подтверждён" in model.spectrum_rows[0]
    assert "нет аппаратных VALUES/AUX" in model.source_note
    assert not model.report()["device_action_allowed"]
    assert model.report()["source"]==SOURCE
    with pytest.raises(ValueError,match="standalone BIN"):
        source_file_workbench(flow,verified_status={
            "source":"MVK_DSP","serial":session.serial,"tick":0,
        })


def test_native_zip_absent_peak_never_copies_rms_into_peak(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path,sample_count=4096))
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    snapshot=copy.deepcopy(flow.status_snapshot())
    snapshot["channels"][0]["parameters_peak_24"]=None
    snapshot["channels"][0]["parameters_peak_peak_24"]=None
    view=source_file_workbench(flow,verified_status=snapshot)
    assert len(view.value_rows)==24
    assert "ПИК —" in view.value_rows[0]
    assert "ПИК-ПИК —" in view.value_rows[0]
