"""41 vendor-original RU Advanced labels, ten selectors, no guessed IDs.

These test labels are derived from the user's already-extracted
EXTLOCALIZATION source, NOT from any live instrument file.
"""
from __future__ import annotations

import struct
import pytest

from ..core.original_config_idp_tables import (
    SOURCE_SELECTOR_IDS,SOURCE_SELECTOR_PREFIXES,
)
from ..core.original_get_value_text_30 import (
    get_value_text_30,source_getvalue_30_provenance,
)
from ..core.original_ru_advanced_catalog import (
    SCHEMA,RU_ADVANCED_CATALOG,original_ru_advanced_translations,
    original_ru_advanced_provenance,
)


def _u32(n):
    return struct.pack("<I",n)


def _metadata(kind,id_value,**kwargs):
    if kind in ("result_overload","result_buffers","result_sensor_state"):
        return dict(advanced_kind=kind,source_locale="ru-ru")
    return dict(advanced_kind=kind,source_locale="ru-ru",
                advanced_source_bits=8,advanced_source_bit_start=0,**kwargs)


def test_all_41_original_dynamic_ru_keys_are_present_exactly_once():
    assert set(RU_ADVANCED_CATALOG)==set(SOURCE_SELECTOR_IDS)
    assert sum(len(x) for x in RU_ADVANCED_CATALOG.values())==41
    for kind, ids in SOURCE_SELECTOR_IDS.items():
        translations=original_ru_advanced_translations(kind)
        prefix=SOURCE_SELECTOR_PREFIXES[kind]
        assert set(translations)=={f"{prefix}Cell{x}" for x in ids}
        assert all(translations[f"{prefix}Cell{x}"] for x in ids)
        for id_value in ids:
            translated=get_value_text_30(
                10,_u32(id_value),**_metadata(kind,id_value))
            assert translated.text==translations[f"{prefix}Cell{id_value}"]
            assert translated.source_route_verified
            assert not translated.original_tlanguage_verified
            assert not translated.original_win32_delphi_text_verified
    assert SCHEMA=="MVK_EXTLOCALIZATION_1033_RU_SOURCE_ADVANCED_41_V1"
    assert original_ru_advanced_provenance()["source_localized_advanced_id_count"]==41
    assert not original_ru_advanced_provenance()["original_pe_rcdata_byte_parity_verified"]


def test_three_live_result_advanced_bits_correct_with_source_resource():
    # Source raw DWORD 0x51 means Overload=1; Buffers=5 (not
    # in source list, hence hexadecimal fallback); SensorState=0.
    raw=_u32(0x51)
    assert get_value_text_30(
        10,raw,advanced_kind="result_overload",source_locale="ru-ru"
    ).text=="Перегрузка"
    assert get_value_text_30(
        10,raw,advanced_kind="result_buffers",source_locale="ru-ru"
    ).text=="(0x00000005)"
    assert get_value_text_30(
        10,raw,advanced_kind="result_sensor_state",source_locale="ru-ru"
    ).text=="ОК"
    assert get_value_text_30(
        10,_u32(0x70),advanced_kind="result_buffers",source_locale="ru-ru"
    ).text=="Идет заполнение (1, 4, 32 с)"
    assert get_value_text_30(
        10,_u32(0x800),advanced_kind="result_sensor_state",source_locale="ru-ru"
    ).text=="КЗ линии"


def test_composite_alarm_alert_matches_delphi_bit_subset_order():
    # User's original _Unit115:007D0808 says each list ID whose bits
    # are included in selected flags is concatenated with '; '.
    result=get_value_text_30(
        10,_u32(0b0101),advanced_kind="alarm_alert",
        advanced_source_bits=4,advanced_source_composite=True,
        source_locale="ru-ru")
    assert result.text=="Ошибка датчика (Устар. ПО); Переход в желтую зону"
    assert get_value_text_30(
        10,_u32(0),advanced_kind="alarm_alert",
        advanced_source_bits=4,advanced_source_composite=True,
        source_locale="ru-ru").text=="---"
    assert get_value_text_30(
        10,_u32(0b1000),advanced_kind="alarm_alert",
        advanced_source_bits=4,advanced_source_composite=True,
        source_locale="ru-ru").text=="Переход в красную зону"


def test_unmapped_source_id_does_not_invent_missing_translation():
    assert get_value_text_30(
        10,_u32(254),advanced_kind="alarm_state",
        advanced_source_bits=8,source_locale="ru-ru"
    ).text=="(0x000000FE)"
    assert get_value_text_30(
        10,_u32(254),advanced_kind="alarm_state",
        advanced_source_bits=8
    ).text=="(0x000000FE)"


@pytest.mark.parametrize("opts",[
    {"advanced_kind":"alarm_state","advanced_source_bits":8,"source_locale":"en-us"},
    {"advanced_kind":"alarm_state","advanced_source_bits":8,"source_locale":"ru-RU"},
    {"advanced_kind":"alarm_state","source_locale":"ru-ru"},
    {"advanced_kind":"invalid","advanced_source_bits":8,"source_locale":"ru-ru"},
    {"advanced_kind":"alarm_state","advanced_source_bits":8,"source_locale":"ru-ru",
     "local_advanced_translations":{"AlarmStateCell17":"untrusted"}},
])
def test_reject_wrong_locale_missing_bit_metadata_and_conflicting_sources(opts):
    with pytest.raises(ValueError):
        get_value_text_30(10,_u32(17),**opts)


def test_catalog_immutable_and_source_provenance_false():
    with pytest.raises(TypeError):
        RU_ADVANCED_CATALOG["alarm_state"][17]="FAKE"
    with pytest.raises(TypeError):
        original_ru_advanced_translations("alarm_state")["AlarmStateCell17"]="FAKE"
    assert source_getvalue_30_provenance()[
        "original_ru_advanced_labels_from_extracted_resource"]==41
    assert source_getvalue_30_provenance()["original_delphi_compatibility_verified"] is False



def test_advanced_metadata_rejected_even_before_register_word_arrives():
    # An incomplete device DWORD must not mask an invalid selection.
    with pytest.raises(ValueError,match="only render an Advanced"):
        get_value_text_30(0,None,source_locale="ru-ru")
    with pytest.raises(ValueError,match="not composite"):
        get_value_text_30(10,None,advanced_kind="result_overload",
                          source_locale="ru-ru",advanced_source_composite=True)
    with pytest.raises(ValueError,match="Bits/Start"):
        get_value_text_30(10,None,advanced_kind="result_buffers",
                          source_locale="ru-ru",advanced_source_bit_start=2)
    with pytest.raises(ValueError,match="Non-Advanced"):
        get_value_text_30(2,None,advanced_source_bits=4)
    assert get_value_text_30(10,None,advanced_kind="result_overload",
                             source_locale="ru-ru").text=="UNKNOWN"
