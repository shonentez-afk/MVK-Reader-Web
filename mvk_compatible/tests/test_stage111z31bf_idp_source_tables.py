"""Stage111Z31BF: recovered IDP DWORD selector, FmtChar and Float32 tables.

Numeric fixtures below are the operator-owned original's derived values.
No original IDP/PAS/DFM/BIN is included in CI.
"""
import struct
import pytest

from mvk_compatible.core.original_config_idp_tables import (
    SOURCE_FMT_CHARS, SOURCE_BYTES_PER_TYPE, SOURCE_SELECTOR_IDS,
    SOURCE_OCTAVE_HZ_FLOAT32_BITS, source_octave_frequencies_float32,
    source_type_description, source_selector_key, verify_embedded_table_digests,
)
from mvk_compatible.core.original_config_semantics import (
    SOURCE_ADVANCED_OPTIONS, source_section_rows,
)


def test_source_type_30_entries_and_exact_field_storage():
    verify_embedded_table_digests()
    assert len(SOURCE_FMT_CHARS)==len(SOURCE_BYTES_PER_TYPE)==30
    assert "".join(SOURCE_FMT_CHARS)=="fiw!!!vacshz!qpmbbbbbbbb!!!!hh"
    assert source_type_description(0)=={
        "type_id":0,"format_char":"f","source_storage_bytes":4,
        "source_register_words":2,
        "character_has_original_placeholder":False}
    assert source_type_description(7)["format_char"]=="a"
    assert source_type_description(9)["source_storage_bytes"]==32
    assert source_type_description(13)["source_storage_bytes"]==32
    assert source_type_description(14)["source_storage_bytes"]==64
    assert source_type_description(14)["source_register_words"]==32
    assert source_type_description(4)["character_has_original_placeholder"]
    for invalid in (-1,30,True,"0"):
        with pytest.raises(ValueError):source_type_description(invalid)


def test_exact_original_nonconsecutive_selector_values():
    assert SOURCE_SELECTOR_IDS["alarm_band"]==(0,1,48,47)
    assert SOURCE_SELECTOR_IDS["alarm_state"]==(
        0,1,2,3,4,5,17,18,19,20,21,255)
    assert SOURCE_SELECTOR_IDS["alarm_alert"]==(1,2,4,8)
    assert SOURCE_SELECTOR_IDS["result_buffers"]==(0,1,3,7)
    assert SOURCE_SELECTOR_IDS["num_groups"]==(0,1)
    assert SOURCE_SELECTOR_IDS["option"]==(0,1,2,3)
    assert SOURCE_SELECTOR_IDS["wifi_mode"]==(0,1,2)
    assert source_selector_key("alarm_band",48)=="AlarmBandCell48"
    assert source_selector_key("alarm_band",46) is None
    assert source_selector_key("wifi_mode",1)=="WifiModeCell1"
    assert source_selector_key("unknown",1) is None


def test_exact_43_original_octave_float32_bits_and_ids():
    assert len(SOURCE_OCTAVE_HZ_FLOAT32_BITS)==43
    frequencies=source_octave_frequencies_float32()
    assert len(frequencies)==43
    assert struct.unpack("<I",struct.pack("<f",frequencies[0]))[0]==0x3F2147AE
    assert struct.unpack("<I",struct.pack("<f",frequencies[7]))[0]==0x4049999A
    assert struct.unpack("<I",struct.pack("<f",frequencies[-1]))[0]==0x461C4000
    assert frequencies[2]==1.0 and frequencies[15]==20.0
    assert frequencies[42]==10000.0
    assert all(a<b for a,b in zip(frequencies,frequencies[1:]))
    octave=SOURCE_ADVANCED_OPTIONS["octave_band"]
    assert len(octave.values)==44
    assert octave.get_title_by_id(0)=="Off"
    assert octave.get_title_by_id(1)=="0.63 Гц"
    assert octave.get_title_by_id(43)=="10000 Гц"
    assert octave.get_index_by_id(43)==43


def test_original_dynamic_advanced_ids_in_source_order():
    assert [x.id for x in SOURCE_ADVANCED_OPTIONS["num_groups"].values]==[0,1]
    assert [x.id for x in SOURCE_ADVANCED_OPTIONS["option"].values]==[0,1,2,3]
    assert [x.id for x in SOURCE_ADVANCED_OPTIONS["wifi_mode"].values]==[0,1,2]
    assert SOURCE_ADVANCED_OPTIONS["wifi_mode"].get_title_by_id(2)==(
        "WifiModeCell2")
    assert SOURCE_ADVANCED_OPTIONS["wifi_mode"].get_title_by_id(100)==(
        "(0x00000064)")


def test_local_fmt_char_conformance_is_diagnostic_not_authority():
    class Cell:
        def __init__(self,fmt):self.format_char=fmt;self.formatted=fmt+":0"
    class Doc:
        def value(self,addr):
            return {4:Cell("a"),10:Cell("D"),0x60:Cell("p")}.get(addr)
    rows=source_section_rows(Doc(),"ip")
    assert rows[0]["source_format_char"]=="a"
    assert rows[0]["source_storage_bytes"]==4
    assert rows[0]["local_fmtchar_matches_source"] is True
    assert rows[3]["local_fmtchar_matches_source"] is False
    assert rows[14]["source_storage_bytes"]==64
    assert rows[14]["local_fmtchar_matches_source"] is True
    assert rows[14]["sensitive_value_masked"]
