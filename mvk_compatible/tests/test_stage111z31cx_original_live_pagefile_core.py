"""Source IDP ten-channel PageFile model, no sockets or device commands."""
from __future__ import annotations
import pytest
from ..core.original_live_pagefile import (
    OriginalLiveFilePlan,live_pagefile_channel_rows,
)


def test_original_live_pagefile_has_10_43_73_source_checkbox_flags():
    plan=OriginalLiveFilePlan()
    receipt=plan.receipt()
    assert receipt["source_channel_flag_count"]==10
    assert receipt["source_spec_flag_count"]==43
    assert receipt["source_value_flag_count"]==73
    assert plan.selected("channels")==tuple(range(8))
    assert plan.selected("spec")==tuple(range(43))
    assert plan.selected("values")==tuple(range(67))
    assert not receipt["selection_controls_native_r6_raw_capture"]
    assert not receipt["original_thread_write_data_flag_modified"]
    assert not receipt["device_commands_sent"]
    assert len(live_pagefile_channel_rows(None))==10


def test_10_channel_spec_and_values_checklists_are_independent():
    original=OriginalLiveFilePlan()
    selected=original.set_checked("channels",0,False)
    selected=selected.set_checked("channels",9,True)
    selected=selected.set_checked("spec",42,False)
    selected=selected.set_checked("values",66,False)
    assert original.channels[0] and not original.channels[9]
    assert not selected.channels[0] and selected.channels[9]
    assert not selected.spec[42] and not selected.values[66]
    assert selected.values[65] and selected.spec[41]
    assert selected.receipt()["selected_tach_indices"]==[2]


@pytest.mark.parametrize("group,length",(
    ("channels",10),("spec",43),("values",73),
))
def test_source_checkbox_counts_and_types_fail_closed(group,length):
    base=OriginalLiveFilePlan()
    with pytest.raises(ValueError):
        OriginalLiveFilePlan(**{group:(True,)*(length-1)})
    with pytest.raises(ValueError):
        OriginalLiveFilePlan(**{group:(True,)*(length-1)+(1,)})
    for bad in (-1,length,True,None,"0"):
        with pytest.raises(ValueError):
            base.set_checked(group,bad,True)
    with pytest.raises(ValueError):
        base.set_checked(group,0,1)


def test_live_session_cannot_inherit_prior_recording_masks():
    initial=OriginalLiveFilePlan()
    first=initial.bind_status({"session_id":"TEST_2026-11-16_09-00-00.000"})
    assert first.receipt()["has_native_session_identity"]
    assert first.bind_status(
        {"session_id":"TEST_2026-11-16_09-00-00.000"})==first
    with pytest.raises(ValueError):
        first.bind_status({"session_id":"TEST_2026-11-16_09-05-00.000"})
    with pytest.raises(ValueError):
        first.bind_status({})
    assert initial.session_id is None


def test_native_ten_channel_counts_not_fabricated_and_tach_raw_unknown():
    rows=live_pagefile_channel_rows({
        "phase":"RECORDING",
        "seconds_since_last_packet":0.2,
        "invalid_frames":0,
        "channels":[
            {"channel":i,"type":"ADC" if i<=8 else "TACH",
             "samples":i*100,
             "sample_rates_hz":[16000],
             "sequence_discontinuities":0,
             "nonfinite_samples":0}
            for i in range(1,11)]})
    assert len(rows)==10
    assert "100 отсчётов" in rows[0]
    assert "16000 Гц" in rows[0]
    assert "1000 отсчётов" in rows[9]
    assert "TACH RAW не подтверждён" in rows[9]
    assert "Гц" in rows[8]
    with pytest.raises(ValueError):
        live_pagefile_channel_rows({
            "phase":"RECORDING","invalid_frames":0,
            "channels":[{"channel":1,"type":"ADC"}]})


def test_selected_native_archive_reuses_sha_checked_offline_flow(tmp_path):
    from .test_offline_core import fixture_zip
    from ..core.offline_export import OfflineSession
    from ..core.offline_measurement_flow import OfflineMeasurementFlow
    archive=fixture_zip(tmp_path)
    session=OfflineSession.open(archive)
    flow=OfflineMeasurementFlow.bind(session,channel=1)
    plan=OriginalLiveFilePlan().set_checked("channels",0,False)
    plan=plan.set_checked("channels",9,True)
    plan=plan.set_checked("spec",8,False)
    plan=plan.set_checked("values",0,False)
    accepted,report=plan.apply_to_verified_flow(flow)
    assert accepted.channels[0] is False
    assert accepted.channels[1] is True
    assert accepted.channels[8:] == (False,False)
    assert accepted.spec[8] is False
    assert accepted.values[0] is False
    assert report["unsupported_original_tach_channels"]==[2]
    assert not report["hardware_write_commands_sent"]
