"""Stage111Z.4: synthetic-only fail-closed tests for original FFT code audit.

The real IDP/EXE is never uploaded to GitHub, CI or these tests.
"""
from __future__ import annotations

import hashlib
import struct

import pytest

from mvk_compatible.private_fft_source_rounding_audit import (
    WINDOWS, _verify_source_window, _verified_fft_semantics,
    audit_original_fft_rounding,
)


def _synthetic_opcode_fixture():
    positive=b"\x68"+struct.pack("<f",6.2831854820251465)+b"\xE8\x00\x00\x00\x00\xC3"
    negative=b"\x53\x56\x8B\xD8\x68"+struct.pack("<f",-6.2831854820251465)+b"\x90"*7
    stages=bytearray(b"\x90"*50)
    stages[0xF:0x12]=bytes.fromhex("D9 5D E8")
    stages[0x24:0x27]=bytes.fromhex("D9 5D D0")
    stages[0x2E:0x31]=bytes.fromhex("D9 5D D4")
    graph=bytearray(b"\x90"*51)
    graph[:5]=b"\xE8"+struct.pack("<i",0x007CC3F8-(0x007D2083+5))
    window=bytes.fromhex("D9 04 83 D8 0C B5 D9 1C C1")
    mean=bytes.fromhex("D9 1C 24 D9 1C 82")
    return {
        "fft_forward_wrapper":positive,
        "fft_reverse_wrapper":negative,
        "twiddle_recurrence":bytes(stages),
        "spectrum_fft_call_and_power":bytes(graph),
        "spectrum_window_multiply":window,
        "dc_center_single":mean,
    }


def test_source_window_metadata_is_only_addresses_and_sha256():
    assert set(WINDOWS)=={
        "fft_forward_wrapper","fft_reverse_wrapper","twiddle_recurrence",
        "butterfly_kernel","spectrum_fft_call_and_power",
        "spectrum_window_multiply","dc_center_single",
    }
    for name,(start,stop,digest) in WINDOWS.items():
        assert start<stop
        assert len(digest)==64 and all(c in "0123456789abcdef" for c in digest)


def test_checksum_requires_identical_synthetic_bytes_and_length():
    test_data=b"operator-independent synthetic opcode test"
    fingerprint=hashlib.sha256(test_data).hexdigest()
    _verify_source_window(test_data,0x1000,0x1000+len(test_data),fingerprint)
    with pytest.raises(ValueError):
        _verify_source_window(test_data+b"!",0x1000,0x1000+len(test_data),fingerprint)
    with pytest.raises(ValueError):
        _verify_source_window(test_data,0x1000,0x1000+len(test_data),"0"*64)


def test_synthetic_fixtures_prove_positive_fft_wrapper_and_single_stores():
    values=_verified_fft_semantics(_synthetic_opcode_fixture())
    assert len(values)==7 and all(values.values())


@pytest.mark.parametrize(("key","corrupt_offset"),[
    ("fft_forward_wrapper",1),
    ("fft_reverse_wrapper",5),
    ("twiddle_recurrence",0xF),
    ("twiddle_recurrence",0x24),
    ("twiddle_recurrence",0x2E),
    ("spectrum_fft_call_and_power",0),
    ("spectrum_window_multiply",0),
    ("dc_center_single",0),
])
def test_synthetic_audit_rejects_modified_critical_instruction(key,corrupt_offset):
    fixture=_synthetic_opcode_fixture()
    damaged=bytearray(fixture[key])
    damaged[corrupt_offset]^=0x10
    fixture[key]=bytes(damaged)
    with pytest.raises(ValueError):
        _verified_fft_semantics(fixture)


def test_no_private_idp_is_successfully_rejected(tmp_path):
    with pytest.raises(ValueError):
        audit_original_fft_rounding(tmp_path/"not_here.idp")
