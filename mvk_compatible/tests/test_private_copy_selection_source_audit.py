"""Stage111Z.12 — independent synthetic opcode tests for original Copy selection.

Only invented i386 instruction windows are stored. No original EXE, IDP,
window memory, archived measurements, or actual clipboard strings in CI.
"""
from __future__ import annotations

import hashlib
import struct

import pytest

from mvk_compatible.private_spectrum_copy_selection_source_audit import (
    SOURCE_WINDOWS, COPY_HANDLER, COPY_RECORD_BREAKPOINT,
    COPY_SELECTION_HELPER, _verify_window, _call_target,
    _verify_structural_facts, audit_original_copy_selected_record,
)


def _synthetic_copy_windows() -> dict[str, bytes]:
    data = {
        name: bytearray(b"\x90" * (end-start))
        for name, (start,end,_) in SOURCE_WINDOWS.items()
    }

    def put(name: str, va: int, encoded_hex: str) -> None:
        start,end,_ = SOURCE_WINDOWS[name]
        encoded = bytes.fromhex(encoded_hex)
        assert start <= va and va + len(encoded) <= end
        data[name][va-start:va-start+len(encoded)] = encoded

    def call(name: str, va: int, target: int) -> None:
        put(name, va, (b"\xE8" + struct.pack("<i",target-va-5)).hex())

    select = "copy_selection_helper"
    for va, opcode in (
        (0x0084EADC,"83 B8 24 06 00 00 01"),
        (0x0084EAE5,"33 C0 C3"),
        (0x0084EAE8,"8B 80 30 04 00 00"),
    ):
        put(select, va, opcode)
    call(select,0x0084EAEE,0x005B01C8)

    copy = "copy_selected_record"
    for va, opcode in (
        (0x0084BC7B,"8B C3"),
        (0x0084BC82,"8D 04 C0"),
        (0x0084BC85,"8D B4 C3 08 09 00 00"),
        (0x0084BC8C,"FF 76 30"),
        (0x0084BC92,"B8 03 00 00 00"),
        (0x0084BCA4,"8B 83 F4 0F 00 00"),
        (0x0084BCAA,"8B 40 40"),
        (0x0084BCAD,"D9 46 34"),
        (0x0084BCB0,"D8 48 14"),
        (0x0084BCB3,"D9 5D E8"),
        (0x0084BCBD,"B8 04 00 00 00"),
        (0x0084BCCF,"FF 76 38"),
        (0x0084BCD5,"B8 04 00 00 00"),
    ):
        put(copy,va,opcode)
    for va,target in (
        (0x0084BC7D,COPY_SELECTION_HELPER),
        (0x0084BC97,0x007B2090),
        (0x0084BCC2,0x007B2090),
        (0x0084BCDA,0x007B2090),
    ):
        call(copy,va,target)
    return {name:bytes(raw) for name,raw in data.items()}


def test_copy_original_metadata_and_sha_only():
    assert COPY_HANDLER == 0x0084BC28
    assert COPY_RECORD_BREAKPOINT == 0x0084BC8C
    assert COPY_SELECTION_HELPER == 0x0084EADC
    assert len(SOURCE_WINDOWS) == 3
    for first,stop,digest in SOURCE_WINDOWS.values():
        assert 0 < stop-first <= 128
        assert len(digest) == 64
        assert all(ch in "0123456789abcdef" for ch in digest)


def test_selected_form_record_and_three_formatter_structures():
    facts = _verify_structural_facts(_synthetic_copy_windows())
    assert facts["copy_selected_record_stride_bytes"] == 72
    assert facts["copy_selected_record_base_offset_hex"] == "0x0908"
    assert facts["copy_selected_record_ptr_register"] == "ESI"
    assert facts["copy_three_significant_digits_order"] == [3,4,4]
    assert facts["copy_three_formatter_007B2090_calls_verified"] is True
    assert facts["copy_selection_helper_active_list_record_verified"] is True
    assert facts["copy_graph_xscale_expression"].endswith("+14]")
    assert facts["earlier_GetSpectrum_call_same_as_selected_Copy_record_verified"] is False


@pytest.mark.parametrize(("block","va"), [
    ("copy_selection_helper",0x0084EADC),
    ("copy_selection_helper",0x0084EAE8),
    ("copy_selection_helper",0x0084EAEE),
    ("copy_selected_record",0x0084BC7D),
    ("copy_selected_record",0x0084BC85),
    ("copy_selected_record",0x0084BC8C),
    ("copy_selected_record",0x0084BC97),
    ("copy_selected_record",0x0084BCA4),
    ("copy_selected_record",0x0084BCB0),
    ("copy_selected_record",0x0084BCC2),
    ("copy_selected_record",0x0084BCCF),
    ("copy_selected_record",0x0084BCDA),
])
def test_copy_opcode_changed_fails_closed(block,va):
    windows = _synthetic_copy_windows()
    damaged = bytearray(windows[block])
    damaged[va-SOURCE_WINDOWS[block][0]] ^= 0x40
    windows[block] = bytes(damaged)
    with pytest.raises(ValueError):
        _verify_structural_facts(windows)


def test_source_window_digest_must_match_length_and_content():
    raw = b"independent synthetic copy source"
    digest = hashlib.sha256(raw).hexdigest()
    _verify_window(raw,0x1000,0x1000+len(raw),digest)
    with pytest.raises(ValueError):
        _verify_window(raw,0x1000,0x1000+len(raw),"f"*64)
    with pytest.raises(ValueError):
        _verify_window(raw+b"x",0x1000,0x1000+len(raw),digest)


def test_missing_original_idp_never_claims_source_proof(tmp_path):
    with pytest.raises(ValueError):
        audit_original_copy_selected_record(tmp_path/"missing.idp")


def test_relative_call_rejects_non_call_and_wrong_site():
    raw = b"\xE8" + struct.pack("<i", 0x3100-0x2005)
    assert _call_target(raw,0x2000,0x2000) == 0x3100
    with pytest.raises(ValueError):
        _call_target(b"\x90"*5,0x2000,0x2000)
    with pytest.raises(ValueError):
        _call_target(raw,0x2000,0x2001)
