"""Stage111Z.7: synthetic-only GetSpectrum breakpoint source-audit tests.

No original IDP/EXE/PAS/DFM, real instrument, waveform or saved x32dbg dump
is embedded in the repository or accessed by these tests.
"""
from __future__ import annotations

import hashlib
import struct

import pytest

from mvk_compatible.private_getspectrum_capture_source_audit import (
    CODE_WINDOWS, PRE_BREAKPOINT, POST_BREAKPOINT,
    _validate_window, _call_target, _structural_facts,
    audit_original_getspectrum_capture_sites,
)


def _fake_original_sections():
    blocks = {
        name: bytearray(b"\x90"*(end-start))
        for name, (start,end,_) in CODE_WINDOWS.items()
    }

    def insert(section: str, va: int, body: bytes):
        start=CODE_WINDOWS[section][0]
        assert start <= va and va+len(body) <= CODE_WINDOWS[section][1]
        blocks[section][va-start:va-start+len(body)]=body

    def call(section: str, va: int, target: int):
        insert(section, va, b"\xE8"+struct.pack("<i",target-(va+5)))

    for va, body in (
        (0x007D1483,"89 45 D4"),
        (0x007D149F,"8B 55 D4"),
        (0x007D14B0,"8B 45 FC"),
    ):
        insert("prepared_input_path",va,bytes.fromhex(body))
    call("prepared_input_path",0x007D14A5,0x007D2228)
    call("prepared_input_path",0x007D14B3,0x007D2344)

    for va,body in (
        (0x007D1518,"8B 43 04"),
        (PRE_BREAKPOINT,"8B 4B 04"),
        (0x007D1540,"8B 55 D4"),
        (0x007D1543,"8B 45 FC"),
        (POST_BREAKPOINT,"8B 43 28"),
    ):
        insert("two_breakpoint_bridge",va,bytes.fromhex(body))
    call("two_breakpoint_bridge",0x007D1546,0x007D1FE8)

    insert("spectrum_mode_branch",0x007D15BC,bytes.fromhex("8B 43 18"))
    call("power_loop",0x007D2083,0x007CC3F8)
    for va,body in (
        (0x007D208B,"D1 EA"),
        (0x007D209B,"D9 04 C1 D8 C8"),
        (0x007D20A6,"D9 44 C1 04 D8 C8"),
        (0x007D20AE,"D9 1C 83"),
    ):
        insert("power_loop",va,bytes.fromhex(body))
    return {name:bytes(data) for name,data in blocks.items()}


def test_breakpoint_source_ranges_and_sha_contract():
    assert len(CODE_WINDOWS)==4
    assert (PRE_BREAKPOINT,POST_BREAKPOINT)==(0x007D153D,0x007D154B)
    for _, (first,last,digest) in CODE_WINDOWS.items():
        assert first < last <= first+128
        assert len(digest)==64 and all(ch in "0123456789abcdef" for ch in digest)


def test_synthetic_structure_verifies_capture_stage_and_fft_power():
    result=_structural_facts(_fake_original_sections())
    assert len(result)==7
    assert all(result.values())


@pytest.mark.parametrize(("part","address"),[
    ("prepared_input_path",0x007D1483),
    ("prepared_input_path",0x007D14A5),
    ("prepared_input_path",0x007D14B3),
    ("two_breakpoint_bridge",0x007D153D),
    ("two_breakpoint_bridge",0x007D1540),
    ("two_breakpoint_bridge",0x007D1546),
    ("two_breakpoint_bridge",0x007D154B),
    ("power_loop",0x007D2083),
    ("power_loop",0x007D208B),
    ("power_loop",0x007D20AE),
    ("spectrum_mode_branch",0x007D15BC),
])
def test_synthetic_critical_opcode_tampering_fails_closed(part,address):
    fixture=_fake_original_sections()
    data=bytearray(fixture[part])
    data[address-CODE_WINDOWS[part][0]]^=0x40
    fixture[part]=bytes(data)
    with pytest.raises(ValueError):
        _structural_facts(fixture)


def test_generic_source_digest_and_length_tamper():
    test_data=b"synthetic user-independent code window"
    digest=hashlib.sha256(test_data).hexdigest()
    _validate_window(test_data,0x1000,0x1000+len(test_data),digest)
    with pytest.raises(ValueError):
        _validate_window(test_data+b"!",0x1000,0x1000+len(test_data),digest)
    with pytest.raises(ValueError):
        _validate_window(test_data,0x1000,0x1000+len(test_data),"0"*64)


def test_relative_call_is_validated_and_cannot_be_a_non_call():
    base=0x2000
    code=b"\xE8"+struct.pack("<i",0x3100-(base+5))
    assert _call_target(code,base,base)==0x3100
    with pytest.raises(ValueError):
        _call_target(b"\x90"*5,base,base)
    with pytest.raises(ValueError):
        _call_target(code,base,base+1)


def test_missing_private_original_file_never_passes(tmp_path):
    with pytest.raises(ValueError):
        audit_original_getspectrum_capture_sites(tmp_path/"missing.idp")
