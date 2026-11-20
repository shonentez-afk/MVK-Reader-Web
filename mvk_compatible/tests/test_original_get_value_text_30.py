"""Source 30/30 routing coverage; independent tests of available branches.

All tests intentionally retain original Win32/text/ANSI parity=False.
"""
from __future__ import annotations

import struct
import pytest

from ..core.original_config_idp_tables import SOURCE_BYTES_PER_TYPE
from ..core.original_get_value_text_30 import (
    TYPE_TO_CASE, ADVANCED, SCHEMA, get_value_text_30,
    live_get_units, source_advanced_id, source_advanced_title_candidate,
    source_getvalue_30_provenance,
)


def raw_for_type(n:int, first:int=0) -> bytes:
    return struct.pack("<I",first) + b"\0"*(SOURCE_BYTES_PER_TYPE[n]-4)


def test_all_thirty_original_types_route_and_enforce_source_width():
    assert len(TYPE_TO_CASE)==30
    assert len(set(TYPE_TO_CASE))==13
    for n in range(30):
        raw=raw_for_type(n)
        got=get_value_text_30(n,raw)
        assert got.source_type==n
        assert got.source_case==TYPE_TO_CASE[n]
        assert got.source_branch.startswith("007CE")
        assert got.source_width_bytes==SOURCE_BYTES_PER_TYPE[n]
        assert got.source_route_verified
        assert not got.original_win32_delphi_text_verified
        assert not got.original_tlanguage_verified
        with pytest.raises(ValueError,match="exact original type width"):
            get_value_text_30(n,raw+b"\0")
    assert source_getvalue_30_provenance()["schema"]==SCHEMA
    assert not source_getvalue_30_provenance()["original_delphi_compatibility_verified"]


def test_float32_and_explicit_format_spec_default_four():
    def f(value:float, digits=4)->str:
        return get_value_text_30(0,struct.pack("<f",value),
                                 format_spec=digits).text
    assert f(0)==f(-0.)=="0"
    assert f(1.5)=="1.5"
    assert f(2.5)=="2.5"
    assert f(.1)=="0.1"
    assert f(10000)=="10000"
    assert f(0.000001)=="0.000001"
    assert f(0.000001,2)=="0.000001"
    assert get_value_text_30(0,bytes.fromhex("0000c07f")).text=="NAN"
    assert get_value_text_30(0,bytes.fromhex("0000807f")).text=="UNKNOWN_NONFINITE"


def test_source_signed_unsigned_date_time_and_ip_network_order():
    assert get_value_text_30(1,raw_for_type(1,0xffffffff)).text=="-1"
    assert get_value_text_30(2,raw_for_type(2,0xffffffff)).text=="4294967295"
    assert get_value_text_30(3,raw_for_type(3,0)).text=="UNKNOWN_WIN32_TIMEZONE"
    assert get_value_text_30(3,raw_for_type(3,0),windows_total_timezone_bias_minutes=0).text=="1970-01-01 00:00:00"
    assert get_value_text_30(3,raw_for_type(3,0),windows_total_timezone_bias_minutes=-180).text=="1970-01-01 03:00:00"
    assert get_value_text_30(12,raw_for_type(12,3661)).text=="01:01:01"
    for n in (6,7,15):
        assert get_value_text_30(n,raw_for_type(n,0xC0A80105)).text=="192.168.1.5"


def test_source_hex_bits_ansi_and_empty_string():
    assert get_value_text_30(4,b"\x00\x11\x22\xff"+bytes(12)).text.startswith("001122FF")
    assert get_value_text_30(5,raw_for_type(5,0)).text=="---"
    assert get_value_text_30(5,raw_for_type(5,0x80000005)).text=="0,2,31"
    for n in (8,9,11,13,14):
        raw=(b"AB\x00"+bytes(SOURCE_BYTES_PER_TYPE[n]-3))
        assert get_value_text_30(n,raw).text=="AB"
    n=9
    raw=b"\xcf\xf0\x00"+bytes(SOURCE_BYTES_PER_TYPE[n]-3)
    assert get_value_text_30(n,raw).text=="UNKNOWN_WIN32_ANSI_CODEPAGE"
    assert get_value_text_30(n,raw,windows_ansi_code_page="cp1251").text=="Пр"
    for n in (10,29):
        assert get_value_text_30(n,raw_for_type(n,0xfeed0001)).text=="0xFEED0001"
    assert get_value_text_30(28,raw_for_type(28,0xAABBCCDD)).text=="0xCCDD"
    assert get_value_text_30(16,raw_for_type(16,1)).text=="1000 "
    assert len(get_value_text_30(23,raw_for_type(23,0)).text)==40
    assert get_value_text_30(24,b"\xaa\xbb\xcc\xdd").text=="AA "
    assert get_value_text_30(27,b"\xaa\xbb\xcc\xdd").text=="AA BB CC DD "


def test_advanced_from_source_list_and_unknown_ids_not_fabricated():
    assert set(ADVANCED)=={"result_overload","result_buffers","result_sensor_state"}
    raw=0x51
    assert source_advanced_id(raw,"result_overload")==1
    assert source_advanced_id(raw,"result_buffers")==5
    assert source_advanced_id(raw,"result_sensor_state")==0
    assert source_advanced_title_candidate(raw,"result_overload")=="UNRESOLVED_ADVANCED_ID_1"
    # GetTitleByID source 007D0845 returns the hexadecimal ID in parentheses.
    assert source_advanced_title_candidate(raw,"result_buffers")=="(0x00000005)"
    assert source_advanced_title_candidate(raw,"result_overload",{
        "OverloadCell1":"Locally supplied title"
    })=="Locally supplied title"
    assert get_value_text_30(10,raw_for_type(10,raw),
        advanced_kind="result_overload").text=="UNRESOLVED_ADVANCED_ID_1"
    assert get_value_text_30(10,raw_for_type(10,raw),
        advanced_kind="result_buffers").text=="(0x00000005)"
    assert get_value_text_30(10,raw_for_type(10,raw)).text=="0x00000051"


def test_source_getunits_return_constructor_strings_and_guards():
    assert live_get_units("SPEC",0)=="м/с2"
    assert live_get_units("SPEC",42)=="м/с2"
    assert [live_get_units("RESULT",i) for i in range(6)]==[
        "","","","В","м/с2",""]
    assert [live_get_units("BAND",i) for i in range(6)]==[
        "м/с2","мм/с","мкм","м/с2","мм/с","мкм"]
    assert [live_get_units("TACH",i) for i in range(6)]==[
        "Гц","Гц","","","",""]
    for group,index in [("SPEC",43),("RESULT",6),("BAND",24),
                        ("TACH",6),("unknown",0),("SPEC",-1)]:
        with pytest.raises(ValueError):
            live_get_units(group,index)


def test_missing_network_word_is_not_nil_source_pointer_and_invalid_inputs():
    assert get_value_text_30(0,None).text=="UNKNOWN"
    assert get_value_text_30(0,None,data_pointer_known_absent=True).text=="####"
    with pytest.raises(ValueError):
        get_value_text_30(0,b"\x00"*4,data_pointer_known_absent=True)
    for wrong in (-1,30,True,1.2,"0"):
        with pytest.raises(ValueError):
            get_value_text_30(wrong,None)
    for wrong in ("4",0,17,True):
        with pytest.raises(ValueError):
            get_value_text_30(0,None,format_spec=wrong)
    with pytest.raises(ValueError):
        get_value_text_30(2,raw_for_type(2),advanced_kind="result_overload")

def test_actual_source_advanced_selector_can_use_local_tlanguage_resource():
    import json
    from ..core.original_language_resource import inspect_local_language_bytes
    language=inspect_local_language_bytes(json.dumps([
        {"ru-ru":[{"OverloadCell1":"Перегрузка подтверждена локально"}]}
    ],ensure_ascii=False).encode("utf-8"),"ru-ru")
    got=get_value_text_30(
        10,raw_for_type(10,0x51),advanced_kind="result_overload",
        local_advanced_translations=dict(language.translations))
    assert got.text=="Перегрузка подтверждена локально"
    assert not got.original_tlanguage_verified
    assert not language.imported_local_resource_verified_as_original
