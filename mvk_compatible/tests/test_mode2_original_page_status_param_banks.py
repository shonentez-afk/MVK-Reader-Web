"""One source register image -> all 15 original PageStatus Qt/Core modes.

All bytes are synthetic, no MVK01 TCP and no private original data. We
compare concrete original _Unit125 register bases/offsets, not invented
FFT-derived RMS or fake vendor GetValueText strings.
"""
from __future__ import annotations

import copy
import struct

import pytest

from ..core.original_live_result_registers import (
    SCHEMA,parse_live_result_registers,source_live_status_projection,
)
from ..core.native_r6_live_status import validate_live_status
from .test_stage111z26_native_live_status import fixture_state,now


def synthetic_register_banks():
    adc=[]
    for ch in range(8):
        adc.append({
            "adc":ch+1,"base_word":0x2000+ch*0x200,
            "bands_43_raw_f32_le":[None]*43,
            "rms_24_raw_f32_le":[None]*24,
            "peak_24_raw_f32_le":[None]*24,
            "peak_peak_24_raw_f32_le":[None]*24,
            "sensor_status_raw_u32_le":None,
            "control_8_values_raw_f32_le":[None]*8,
            "control_8_status_raw_u32_le":[None]*8,
        })
    tach=[{
        "tach":i+1,"base_word":0x3000+0x100*i,
        "source_field_0_2_4_6_8_fe_raw_le":[None]*6,
    } for i in range(2)]
    return {
        "schema":SCHEMA,"accepted_param_frames":3,
        "tcp_connection_count":1,
        "original_get_value_text_parity_verified":False,
        "original_delphi_runtime_parity_verified":False,
        "adc":adc,"tach":tach,
    }


def w(value:float)->str:
    return struct.pack("<f",value).hex()


def d(value:int)->str:
    return struct.pack("<I",value).hex()


def live_state(*,partial=False):
    status=fixture_state()
    for ch in status["channels"][:8]:
        ch["dsp_sensor_status_hex"]="0x00000000"
    status.update(
        source_rx_nonempty_parameter_frames=5,
        source_rx_ack_observed_no_command_issued=0,
        source_rx_denied_responses=0,
        source_tcp_connection_count=1,
        source_tcp_multi_socket=False,
        source_tcp_reconnects_after_raw=0,
    )
    banks=synthetic_register_banks()
    banks["adc"][0]["bands_43_raw_f32_le"]=[
        w((i+1)*0.25) for i in range(43)] if not partial else [w(0.25)]+[None]*42
    banks["adc"][0]["rms_24_raw_f32_le"][0]=w(1.5)
    banks["adc"][0]["peak_24_raw_f32_le"][0]=w(2.5)
    banks["adc"][0]["peak_peak_24_raw_f32_le"][0]=w(3.5)
    banks["adc"][0]["control_8_values_raw_f32_le"][0]=w(4.5)
    banks["adc"][0]["control_8_status_raw_u32_le"][0]=d(0x00000003)
    banks["adc"][0]["sensor_status_raw_u32_le"]=d(0x51)
    banks["tach"][0]["source_field_0_2_4_6_8_fe_raw_le"]=[
        w(50.5),w(0.25),d(0),d(123),d(456),d(99999)]
    # Deliberately absent second TACH remains UNKNOWN, even when
    # first tach is valid. +FE from full initial image is stale by rule.
    status["source_live_page_status_banks"]=banks
    return status


def test_native_validated_live_status_delivers_8_adc_2_tach_raw_words():
    status=live_state()
    parsed=validate_live_status(status,
        expected_run=status["session_id"],now=now())
    assert parsed["source_live_page_status_banks_verified"]
    banks=parsed["source_live_page_status_banks"]
    assert banks["accepted_param_frames"]==3
    assert banks["known_complete_dwords"]==43+3+2+1+5
    assert banks["adc"][0]["bands_43_raw_f32_le"][0]==w(0.25)
    assert banks["adc"][1]["bands_43_raw_f32_le"][0] is None
    assert banks["tach"][0]["source_field_0_2_4_6_8_fe_raw_le"][5] is None
    assert not banks["get_value_text_parity_verified"]
    assert not banks["original_delphi_runtime_parity_verified"]


def test_all_fourteen_non_system_modes_use_only_real_param_registers():
    v=validate_live_status(live_state(),
        expected_run=fixture_state()["session_id"],now=now())
    banks=v["source_live_page_status_banks"]
    for mode in range(1,15):
        projection=source_live_status_projection(mode,banks)
        assert projection.model.index==mode
        assert projection.table_name in (
            "tabAlarmResult","tabAllResult","tabResult")
        assert "НЕ исходный TMvkCellList.GetValueText" in projection.model.note
        assert projection.provenance.startswith("SOURCE_LIVE_")
        assert not projection.receipt()["original_delphi_pixel_parity_verified"]
        assert projection.source_digest is None
    alarm=source_live_status_projection(1,banks)
    assert len(alarm.model.rows)==24
    assert alarm.model.rows[0][1]=="4.5 (RAW)"
    assert alarm.model.rows[1][1]=="0x00000003 (RAW)"
    assert alarm.model.rows[2][1]==alarm.model.rows[1][1]
    for index,val in ((2,"1.5 (RAW)"),(3,"2.5 (RAW)"),(4,"3.5 (RAW)")):
        model=source_live_status_projection(index,banks).model
        assert len(model.rows)==24
        assert model.rows[0][1]==val
        assert model.rows[0][2]=="—"
    first=source_live_status_projection(5,banks)
    assert first.chart_visible
    assert len(first.model.rows)==43
    assert len(first.model.bands_for_plot)==43
    assert first.model.bands_for_plot[0]==0.25
    assert first.model.bands_for_plot[-1]==10.75
    for mode in range(6,13):
        other=source_live_status_projection(mode,banks)
        assert not other.chart_visible
        assert len(other.model.rows)==43
        assert other.model.rows[0][1]=="—"
    tach=source_live_status_projection(13,banks)
    assert tach.model.rows[0][2]=="50.5 (RAW)"
    assert tach.model.rows[1][2]=="0.25 (RAW)"
    assert tach.model.rows[4][2]=="0x000001C8 (RAW)"
    assert tach.model.rows[5][2]=="—"
    assert all(row[2]=="—" for row in
        source_live_status_projection(14,banks).model.rows)
    assert not source_live_status_projection(13,banks).chart_visible


def test_missing_band_prevents_live_third_octave_plot_but_other_bands_visible():
    raw=live_state(partial=True)
    parsed=parse_live_result_registers(raw)
    assert parsed is not None
    first=source_live_status_projection(5,parsed)
    assert not first.chart_visible
    assert first.model.rows[0][1]=="0.25 (RAW)"
    assert first.model.rows[1][1]=="—"


@pytest.mark.parametrize("corrupt",[
    lambda st: st["source_live_page_status_banks"]["adc"].pop(),
    lambda st: st["source_live_page_status_banks"]["tach"][1].update(tach=1),
    lambda st: st["source_live_page_status_banks"]["adc"][0].update(base_word=0x2200),
    lambda st: st["source_live_page_status_banks"]["adc"][0][
        "bands_43_raw_f32_le"].__setitem__(0,"FFFFFFFE"),
    lambda st: st["source_live_page_status_banks"]["adc"][0][
        "bands_43_raw_f32_le"].__setitem__(0,"abcde"),
    lambda st: st["source_live_page_status_banks"].update(
        accepted_param_frames=90000),
    lambda st: st["source_live_page_status_banks"].update(
        tcp_connection_count=2),
    lambda st: st["source_live_page_status_banks"].update(
        original_get_value_text_parity_verified=True),
    lambda st: st["source_live_page_status_banks"].update(
        accepted_param_frames=0),
])
def test_corrupt_or_foreign_live_page_status_is_rejected_before_qt(corrupt):
    st=live_state()
    corrupt(st)
    with pytest.raises(ValueError,match="Source PageStatus"):
        validate_live_status(st,expected_run=st["session_id"],now=now())


def test_old_go_status_has_no_fabricated_new_page_results():
    st=fixture_state()
    assert parse_live_result_registers(st) is None
    v=validate_live_status(st,expected_run=st["session_id"],now=now())
    assert v["source_live_page_status_banks_verified"] is False


def test_nonfinite_raw_result_refuses_chart_not_fabricated_rms():
    st=live_state()
    st["source_live_page_status_banks"]["adc"][0][
        "bands_43_raw_f32_le"][8]=d(0x7fc00000)  # wire NaN is a REAL raw word
    banks=parse_live_result_registers(st)
    projection=source_live_status_projection(5,banks)
    assert not projection.chart_visible
    assert projection.model.rows[8][1]=="—"
    assert banks["adc"][0]["bands_43_raw_f32_le"][8]==d(0x7fc00000)
