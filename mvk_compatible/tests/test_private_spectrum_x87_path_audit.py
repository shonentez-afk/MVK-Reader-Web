"""Stage111Z.3 synthetic-only tests for read-only spectrum x87 source audit.

No original EXE/IDP/PAS or user measurements are embedded in CI.
"""
from __future__ import annotations

import hashlib
import struct

import pytest

from mvk_compatible.private_spectrum_x87_path_audit import (
    EXPECTED_HELPER_COUNTS,
    SOURCE_WINDOWS,
    _direct_target_counts,
    _verify_window,
    audit_original_spectrum_x87_path,
)


def test_source_regions_and_helper_count_contract():
    assert set(SOURCE_WINDOWS) == {
        "spectrum", "log10_single", "power_extended", "power_single"
    }
    assert SOURCE_WINDOWS["spectrum"][:2] == (0x0084B5D3, 0x0084B882)
    assert EXPECTED_HELPER_COUNTS == {
        0x00447DB8: 16,
        0x00407C74: 7,
        0x00447DF0: 4,
        0x00447EF8: 2,
    }
    for name, (start, stop, checksum) in SOURCE_WINDOWS.items():
        assert start < stop
        assert len(checksum) == 64
        assert all(ch in "0123456789abcdef" for ch in checksum)


def test_fail_closed_sha_and_length_verification_uses_synthetic_bytes():
    raw = b"synthetic source structure, not original code"
    digest = hashlib.sha256(raw).hexdigest()
    _verify_window(raw, 0x1000, 0x1000 + len(raw), digest)
    with pytest.raises(ValueError):
        _verify_window(raw + b"!", 0x1000, 0x1000 + len(raw), digest)
    with pytest.raises(ValueError):
        _verify_window(raw, 0x1000, 0x1000 + len(raw), "0" * 64)
    with pytest.raises(ValueError):
        _verify_window(raw, 0x1000, 0x0FFF, digest)


def test_direct_call_target_counts_with_synthetic_relative_calls():
    base = 0x2000
    first_target = 0x3100
    second_target = 0x3300
    first_call = b"\xE8" + struct.pack("<i", first_target - (base + 5))
    second_va = base + len(first_call) + 1
    second_call = b"\xE8" + struct.pack("<i", second_target - (second_va + 5))
    raw = first_call + b"\x90" + second_call
    assert _direct_target_counts(raw, base, (first_target, second_target)) == {
        first_target: 1, second_target: 1,
    }
    assert _direct_target_counts(b"\x90\xE8", base, (first_target,)) == {
        first_target: 0,
    }


def test_unavailable_private_idp_fails_without_emitting_code(tmp_path):
    path = tmp_path / "missing.idp"
    with pytest.raises(ValueError):
        audit_original_spectrum_x87_path(path)
