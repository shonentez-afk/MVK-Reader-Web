"""Source IDP + DFM 96/144 DPI Mode2: real passive 8+2 quality, no TCP."""
from __future__ import annotations

import pytest
from ..core.original_mode2_live_health import (
    SOURCE_CHANNEL_KINDS,original_dpi_geometry,live_transport_health,
)
from ..core.original_connected_status import connected_system_status,UNKNOWN
from ..core.original_measurement_mode import source_connection_display
from .test_stage111z31cr_connected_core import source_test_transport


def _snapshot(*,silent=None,invalid=0,gaps=0,nonfinite=0,
              phase="RECORDING",frames=120):
    status=source_test_transport(phase=phase,frames=frames)
    status["invalid_frames"]=invalid
    status["seconds_since_last_packet"]=silent
    status["channels"]=[
        {"channel":i,"type":type_,
         "sequence_discontinuities":gaps if i==1 else 0,
         "nonfinite_samples":nonfinite if i==1 else 0}
        for i,type_ in enumerate(SOURCE_CHANNEL_KINDS,1)]
    return status


def test_original_dpi96_and_dpi150_one_scale_from_dfm():
    original=original_dpi_geometry(1.)
    scaled=original_dpi_geometry(1.5)
    assert original["dfm_pixels_per_inch"]==96
    assert original["qt_physical_client_reference"]==[1008,929]
    assert original["panel_physical_height"]==53
    assert scaled["physical_dpi_candidate"]==144
    assert scaled["qt_physical_client_reference"]==[1512,1394]
    assert scaled["panel_physical_height"]==80
    assert scaled["tab_physical_height"]==66
    assert [x["rect"] for x in scaled["button_logical_rects"]]==[
        [6,0,160,41],[172,0,160,41],[338,0,160,41],
        [504,0,160,41],[670,0,160,41]]
    assert scaled["qt_layout_must_not_apply_second_scale"]
    for bad in (0.,-1,False,float("nan"),float("inf"),4.5,"1.5"):
        with pytest.raises(ValueError):
            original_dpi_geometry(bad)


def test_fresh_json_not_green_when_last_instrument_packet_is_silent():
    status=_snapshot(silent=5.2)
    health=live_transport_health(status)
    assert health.channels_observed==10
    assert health.stream_silent
    assert not health.data_integrity_alert
    proof=connected_system_status(status)
    assert not proof.connection_verified
    assert proof.stream_silent
    assert len(proof.rows)==15 and all(value==UNKNOWN for _,value in proof.rows)
    lamp=source_connection_display(
        selected=True,capture_started=True,status=status)
    assert lamp.indicator=="bad"
    assert lamp.phase=="SILENT"
    assert "Нет новых данных" in lamp.text


def test_ten_channels_invalid_frames_and_gaps_warn_without_fake_dsp():
    status=_snapshot(silent=.5,invalid=2,gaps=3,nonfinite=1)
    health=live_transport_health(status)
    assert health.channels_observed==10
    assert health.invalid_frames==2
    assert health.sequence_gaps==3
    assert health.nonfinite_samples==1
    assert health.data_integrity_alert
    proof=connected_system_status(status)
    assert proof.connection_verified
    assert proof.data_integrity_alert
    assert proof.receipt()["native_channels_observed"]==10
    assert proof.receipt()["native_sequence_gaps"]==3
    assert proof.receipt()["original_device_system_fields_proven"]==0
    lamp=source_connection_display(
        selected=True,capture_started=True,status=status)
    assert lamp.phase=="STREAM_ERRORS" and lamp.indicator=="bad"
    assert lamp.transport_verified # TCP read-only still proven
    assert "Ошибки входного потока" in lamp.text


def test_clean_ten_channel_run_green_until_timeout_and_export():
    status=_snapshot(silent=0.2)
    model=connected_system_status(status)
    assert model.connection_verified
    assert not model.data_integrity_alert
    assert model.receipt()["native_channels_observed"]==10
    lamp=source_connection_display(
        selected=True,capture_started=True,status=status)
    assert lamp.phase=="RECORDING" and lamp.indicator=="good"
    for phase,expected in (
        ("VERIFYING","Проверка записи"),
        ("COMPLETED","Запись завершена"),
    ):
        completed=source_connection_display(
            selected=True,capture_started=True,
            status=_snapshot(phase=phase,silent=500))
        assert completed.phase==phase
        assert completed.indicator=="waiting"
        assert expected in completed.text


def test_sparse_legacy_source_receipt_does_not_fabricate_ten_channels():
    health=live_transport_health(source_test_transport())
    assert health.channels_observed==0
    model=connected_system_status(source_test_transport())
    assert model.connection_verified
    assert model.receipt()["native_channels_observed"]==0
    assert not model.receipt()["native_data_integrity_alert"]


@pytest.mark.parametrize("mutation",(
    {"channels":[{"channel":1,"type":"ADC"}]},
    {"channels":[{"channel":i,"type":"ADC",
                  "sequence_discontinuities":0,"nonfinite_samples":0}
                 for i in range(1,11)]},
    {"seconds_since_last_packet":float("nan")},
    {"seconds_since_last_packet":-1},
    {"invalid_frames":True},
))
def test_rejects_untrusted_run_quality_metadata(mutation):
    status=_snapshot()
    status.update(mutation)
    with pytest.raises(ValueError):
        connected_system_status(status)
