"""Source IDP ten-channel PageFile model, no sockets or device commands."""
from __future__ import annotations
import pytest
from ..core.original_live_pagefile import (
    OriginalLiveFilePlan,live_pagefile_channel_rows,
)


def test_original_live_pagefile_has_10_43_36_source_checkbox_flags():
    plan=OriginalLiveFilePlan()
    receipt=plan.receipt()
    assert receipt["source_channel_flag_count"]==10
    assert receipt["source_spec_flag_count"]==43
    assert receipt["source_value_flag_count"]==36
    assert receipt["go_legacy_frame_mark_value_flag_count"]==73
    assert receipt["non_original_legacy_bits_disabled"]
    assert plan.selected("channels")==tuple(range(8))
    assert plan.selected("spec")==tuple(range(43))
    assert plan.selected("values")==tuple(range(30))
    assert not receipt["selection_controls_native_r6_raw_capture"]
    assert not receipt["original_thread_write_data_flag_modified"]
    assert not receipt["device_commands_sent"]
    assert len(live_pagefile_channel_rows(None))==10


def test_10_channel_spec_and_values_checklists_are_independent():
    original=OriginalLiveFilePlan()
    selected=original.set_checked("channels",0,False)
    selected=selected.set_checked("channels",9,True)
    selected=selected.set_checked("spec",42,False)
    selected=selected.set_checked("values",29,False)
    assert original.channels[0] and not original.channels[9]
    assert not selected.channels[0] and selected.channels[9]
    assert not selected.spec[42] and not selected.values[29]
    assert selected.values[28] and selected.spec[41]
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
    if group=="values":
        with pytest.raises(ValueError):base.set_checked("values",36,True)
        with pytest.raises(ValueError):OriginalLiveFilePlan(values=(True,)*73)


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
    assert accepted.values[0] is True  # Source BAND0 maps to offline RMS0
    assert report["unsupported_original_advanced_result_indices"]==list(range(2,7))
    assert report["unsupported_original_tach_channels"]==[2]
    assert not report["hardware_write_commands_sent"]


def test_sparse_transport_evidence_keeps_unknown_counters_not_fake_zero():
    status={
        "phase":"RECORDING",
        "invalid_frames":0,
        "channels":[
            {"channel":i,"type":"ADC" if i<=8 else "TACH",
             "sequence_discontinuities":0,"nonfinite_samples":0}
            for i in range(1,11)],
    }
    rows=live_pagefile_channel_rows(status)
    assert len(rows)==10
    assert all("— отсчётов" in row for row in rows)
    assert all("0 отсчётов" not in row for row in rows)
    assert all("счётчик ещё не получен" in row for row in rows)


def test_non_numeric_present_native_counts_still_rejected():
    status={
        "phase":"RECORDING",
        "invalid_frames":0,
        "channels":[
            {"channel":i,"type":"ADC" if i<=8 else "TACH",
             "samples":12, "sample_rates_hz":[65536],
             "sequence_discontinuities":0,"nonfinite_samples":0}
            for i in range(1,11)],
    }
    status["channels"][0]["samples"]=True
    with pytest.raises(ValueError):
        live_pagefile_channel_rows(status)


def test_original_file_lock_matrix_and_effective_selected_columns():
    from ..core.original_live_pagefile import (
        source_live_file_edit_policy,source_live_file_field_title)
    for data,values,expected in (
        (False,False,(True,True,True,True)),
        (True,False,(False,True,True,False)),
        (False,True,(False,False,False,True)),
        (True,True,(False,False,False,False)),
    ):
        policy=source_live_file_edit_policy(write_data=data,write_values=values)
        assert tuple(policy[k] for k in ("channels","spec","values","file_options"))==expected
        assert not any(source_live_file_edit_policy(
            write_data=data,write_values=values,stopping=True).values())
    plan=OriginalLiveFilePlan()
    assert plan.effective_values_count()==8*(43+30)
    only_tach=OriginalLiveFilePlan(channels=(False,)*8+(True,False))
    assert only_tach.effective_values_count()==0
    only_tach=only_tach.set_checked("values",30,True)
    assert only_tach.effective_values_count()==1
    assert only_tach.receipt()["selected_source_values_columns"]==1
    assert source_live_file_field_title("spec",0).startswith("Полоса 0.63 Гц")
    assert source_live_file_field_title("values",0)=="Индикатор перегрузки"
    assert source_live_file_field_title("values",6).startswith("Виброускорение, 10..3000 Гц")
    assert source_live_file_field_title("values",30).startswith("Частота вращения")


def test_writer_begin_mask_remains_authoritative_on_end():
    from ..core.original_live_write_stages import OriginalLiveWriteLedger
    from .test_stage111z31cz_source_write_stages_core import source_status
    status=source_status()
    writer=OriginalLiveWriteLedger()
    writer.observe(status)
    start=OriginalLiveFilePlan().bind_status(status)
    writer.toggle("data",start)
    later=start.set_checked("spec",0,False)
    assert writer.plan_for_frame_mark("data",later) is start
    assert writer.plan_for_frame_mark("values",later) is later
    with pytest.raises(ValueError,match="shared channels locked"):
        writer.toggle("values",later.set_checked("channels",0,False))
    writer.toggle("values",later)
    assert writer.plan_for_frame_mark("values",start) is later
    writer.observe(source_status(adc_samples=512,aux=1,frames=30,raw=18000))
    writer.toggle("data",later)
    writer.toggle("values",start)
    assert writer.windows[0].spec==start.spec
    assert writer.windows[1].spec==later.spec
    assert writer.plan_for_frame_mark("data",later) is later
    with pytest.raises(ValueError,match="zero selected result flags"):
        writer.toggle("values",OriginalLiveFilePlan(
            channels=(False,)*8+(True,False)).bind_status(status))
