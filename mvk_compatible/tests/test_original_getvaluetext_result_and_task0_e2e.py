"""Triple-source original GetValueText on verified-mode result/Task0 bytes.

Uses only synthetic register/frame values; not original private artifacts,
not hardware and not a claim of locale/binary 1:1 compatibility.
"""
from __future__ import annotations

import struct

import pytest

from mvk_compatible.core.original_config_semantics import (
    SOURCE_ADVANCED_OPTIONS, AdvancedCell, AdvancedValue,
)
from mvk_compatible.core.original_config_register_image import (
    LocalRegisterImage, extract_source_advanced_bits,
)
from mvk_compatible.core.original_cell_source_renderer import render_source_cell
from mvk_compatible.core.original_result_status_source import (
    FIELDS, decode_source_result_status, source_result_sensor_display,
)
from mvk_compatible.core.original_pagestatus_source import source_pagestatus_table
from mvk_compatible.core.original_task0_config_live import (
    _replay_original_param, original_task0_field_text,
)


def test_original_gettitlebyid_exact_and_composite_source_order():
    original=AdvancedCell((
        AdvancedValue(1,"A"),AdvancedValue(3,"AB"),AdvancedValue(2,"B"),
        AdvancedValue(0,"ZERO"),
    ),composite=True)
    # _Unit115:007D08AE bitwise subset, preserves list order with ", ".
    assert original.get_title_by_id(3)=="A, AB, B, ZERO"
    assert original.get_title_by_id(4)=="ZERO"
    assert original.get_title_by_id(0)=="ZERO"
    assert original.get_title_by_id(0xFFFFFFFF)=="A, AB, B, ZERO"
    none=AdvancedCell((AdvancedValue(1,"One"),AdvancedValue(2,"Two")),composite=True)
    assert none.get_title_by_id(0)=="---"
    exact=AdvancedCell((AdvancedValue(1,"first"),AdvancedValue(1,"second")))
    assert exact.get_title_by_id(1)=="first"
    assert exact.get_title_by_id(0xFFFFFFFF)=="(0xFFFFFFFF)"
    assert len(SOURCE_ADVANCED_OPTIONS["alarm_alert"].values)==4
    assert SOURCE_ADVANCED_OPTIONS["alarm_alert"].composite
    assert SOURCE_ADVANCED_OPTIONS["alarm_alert"].get_title_by_id(5)==(
        "AlarmAlertCell1, AlarmAlertCell4"
    )
    assert SOURCE_ADVANCED_OPTIONS["alarm_alert"].get_title_by_id(0)=="---"
    for family,ids in {
        "alarm_band":(0,1,48,47),
        "alarm_state":(0,1,2,3,4,5,17,18,19,20,21,255),
        "tacho_function":(0,1),
        "result_overload":(0,1),
        "result_buffers":(0,1,3,7),
        "result_sensor_state":(0,1,2,3),
    }.items():
        assert tuple(x.id for x in SOURCE_ADVANCED_OPTIONS[family].values)==ids
    with pytest.raises(ValueError):original.get_title_by_id(True)


def test_original_result_status_three_fields_read_one_register_without_false_ok():
    # _Unit125:00804A82: Bits 1/0, 00804ABE: Bits 3/4,
    # 00804AFA: Bits 2/10. All FROM the same ResultStatus +0x120.
    word=0x00000831  # Overload=1, Buffers=3, SensorState=2
    record=decode_source_result_status(word,1)
    assert record.source_register_word==0x2120
    assert tuple((x.key,x.bits,x.bit_start,x.numeric_id) for x in record.fields)==(
        ("ResultOverload",1,0,1),
        ("ResultBuffers",3,4,3),
        ("ResultSensorState",2,10,2),
    )
    assert [x.title_key for x in record.fields]==[
        "OverloadCell1","BuffersCell3","SensorStateCell2"
    ]
    assert source_result_sensor_display("0x00000831",1)==(
        "0x00000831 · SensorStateCell2"
    )
    end=decode_source_result_status("0x00000831",8)
    assert end.source_register_word==0x2F20
    assert end.receipt()["original_delphi_localized_title_verified"] is False
    assert end.receipt()["source_live_device_parity_verified"] is False
    assert not end.receipt()["device_commands_sent"]
    zero=decode_source_result_status("0x00000000",1)
    assert zero.field("ResultSensorState").numeric_id==0
    assert zero.field("ResultOverload").title_key=="OverloadCell0"
    # Real buffers ID 2 not in 0/1/3/7 -> exact original unknown fallback.
    unknown=decode_source_result_status(0x20,2)
    assert unknown.field("ResultBuffers").title_key=="(0x00000002)"
    for raw in (-1,2**32,True,0.25,"0x01234","0xZZZZZZZZ"):
        with pytest.raises(ValueError):decode_source_result_status(raw,1)
    for adc in (0,9,True,"2"):
        with pytest.raises(ValueError):decode_source_result_status(0,adc)


def test_source_result_getvaluetext_same_32bit_word_and_bit_extraction():
    image=bytearray(0x6000)
    addr=0x2120
    image[addr*2:addr*2+4]=struct.pack("<I",0x00000831)
    local=LocalRegisterImage.from_bytes(bytes(image))
    for key,kind,width,start in FIELDS:
        r=render_source_cell(local,addr,10,advanced=kind,
                             bits=width,bit_start=start)
        raw=local.read_u32(addr)
        expected=SOURCE_ADVANCED_OPTIONS[kind].get_title_by_id(
            extract_source_advanced_bits(raw,width,start))
        assert r.display==expected
        assert not r.original_runtime_text_verified
        assert not r.original_live_device_verified
    # Nothing about a source selector authorizes writing a register.
    assert not render_source_cell(
        local,addr,10,advanced="result_overload",bits=1).mutable


def test_pagestatus_preserves_real_raw_and_recovered_sensor_code():
    raw="0x00000831"
    payload={"channels":[{"sensor_status":raw} for _ in range(8)],
             "dsp_tach":{"available":False}}
    page=source_pagestatus_table(0,payload)
    assert len(page.rows)==10
    assert page.rows[0][1]=="—"  # unknown system DSP is not 'healthy'
    assert page.rows[1]==(
        "АЦП1 · состояние датчика","0x00000831 · SensorStateCell2"
    )
    assert page.rows[8]==(
        "АЦП8 · состояние датчика","0x00000831 · SensorStateCell2"
    )
    assert page.provenance!="ORIGINAL_DELPHI_VERIFIED"
    payload["channels"][0]["sensor_status"]=None
    assert source_pagestatus_table(0,payload).rows[1][1]=="—"


def test_task0_28byte_empty_param_and_verifiable_advanced_source_ids():
    typ=0xFF800C0D
    empty=struct.pack("<7I",typ,28,0,0,0,0,0)
    block=struct.pack("<II", (2<<16)|0x0c,0x66666666)
    valid=struct.pack("<7I",typ,36,0,0,0,0,1)+block
    mem,observed,param_count,tail=_replay_original_param(empty+valid)
    assert param_count==1 and tail==0
    assert mem[0x0c*2:0x0c*2+4]==struct.pack("<I",0x66666666)
    assert observed[0x0c] and observed[0x0d]
    assert original_task0_field_text("ConfigModbusEndian",{
        "valid":True, "raw_hex_le":"66666666",
    })=="0x66666666 · EndianCell6"
    assert original_task0_field_text("ConfigNumGroups",{
        "valid":True, "raw_hex_le":"01000000",
    })=="0x00000001 · ConfigNumGroupsCell1"
    assert original_task0_field_text("ConfigWifiMode",{
        "valid":True, "raw_hex_le":"01000000",
    })=="0x00000001 · WifiModeCell1"
    assert original_task0_field_text("ConfigWifiPassword",{
        "valid":True,"raw_hex_le":"41424344",
    })=="•••••••• (скрыто)"
    assert original_task0_field_text("ConfigNumGroups",{
        "valid":False,"raw_hex_le":None,
    })=="—"
    with pytest.raises(ValueError,match="PARAM too short"):
        _replay_original_param(struct.pack("<II",typ,24)+b"\x00"*16)


def test_legacy_status_quality_never_claims_zero_means_sensor_ok():
    from mvk_compatible.core.native_r6_live_status import _channel_quality
    channel={"sequence_discontinuities":0,"nonfinite_samples":0,
             "sample_rates_hz":[65536],"samples":256,"type":"ADC",
             "dsp_sensor_status_hex":"0x00000000"}
    assert _channel_quality(channel)=="DSP: статус 0x00000000"
    channel["dsp_sensor_status_hex"]="0x00000831"
    assert _channel_quality(channel)=="DSP: статус 0x00000831"
    channel["dsp_sensor_status_hex"]=None
    assert _channel_quality(channel)=="DSP НЕ ПОЛУЧЕН"
