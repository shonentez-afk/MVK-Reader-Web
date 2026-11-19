"""30-case source GetValueText dispatcher and explicit private parity gate."""
from __future__ import annotations
import struct

import pytest

from ..core.original_get_value_text_source import (
    source_getvalue_dispatch_case,source_getvalue_text_candidate,
    source_getvalue_router_provenance,
)


def test_all_original_thirty_types_have_deterministic_nonblank_branch():
    mapped=[source_getvalue_dispatch_case(i) for i in range(30)]
    assert len(mapped)==30
    assert len({case for case,_ in mapped})==13
    assert mapped[0]==(1,"007CE77C")
    assert mapped[1]==(2,"007CE799")
    assert mapped[16]==(12,"007CE93F")
    assert mapped[24]==(13,"007CE95B")
    assert mapped[-1]==(10,"007CE91F")
    assert source_getvalue_router_provenance()["original_type_count"]==30
    for wrong in (-1,30,1.5,"0",True,None):
        with pytest.raises(ValueError):
            source_getvalue_dispatch_case(wrong)


def test_source_numeric_preview_preserves_raw_bits_and_never_claims_win32():
    word=struct.pack("<f",1.5).hex()
    got=source_getvalue_text_candidate(0,word)
    assert got.candidate_text=="1.5 (RAW)"
    assert got.raw_source_f32==1.5
    assert got.original_branch_address=="007CE77C"
    assert not got.original_delphi_text_parity_verified
    assert not got.original_tlanguage_parity_verified
    # Every unsupported original type is *raw*, never an invented
    # decimal/time/enum that could look like a genuine measurement.
    for kind in range(1,30):
        result=source_getvalue_text_candidate(kind,"0000803f")
        assert result.candidate_text==f"0x3F800000 (RAW type {kind})"
        assert result.original_branch_address.startswith("007CE")
        assert not result.original_delphi_text_parity_verified


def test_missing_register_is_not_original_missing_data_pointer():
    unknown=source_getvalue_text_candidate(0,None)
    missing_pointer=source_getvalue_text_candidate(
        0,None,data_pointer_known_absent=True)
    assert unknown.candidate_text=="—"
    assert missing_pointer.candidate_text=="####"
    assert not missing_pointer.source_values_available
    with pytest.raises(ValueError):
        source_getvalue_text_candidate(0,"0000803f",
            data_pointer_known_absent=True)
    for wrong in ("ABCDEF01","not hex","abc",42):
        with pytest.raises(ValueError):
            source_getvalue_text_candidate(0,wrong)


def test_nonfinite_float32_source_raw_is_unknown_but_not_zero():
    got=source_getvalue_text_candidate(0,"0000c07f")
    assert got.candidate_text=="—"
    assert got.raw_source_f32 is None
    assert not got.source_values_available
