"""Stage111Z.9 tests — only fabricated instruction snippets, no private IDP."""
from __future__ import annotations

import hashlib
import struct
import pytest

from mvk_compatible.private_getspectrum_summary_source_audit import (
    SOURCE_WINDOWS, PRE_SUMMARY_BREAKPOINT, POST_SUMMARY_BREAKPOINT,
    _verify_hash, _source_call_target, _source_summary_structure,
    audit_private_getspectrum_summary_source,
)


def _fake_windows() -> dict[str, bytes]:
    synthetic = {
        key: bytearray(b"\x90" * (end-start))
        for key, (start, end, _) in SOURCE_WINDOWS.items()
    }
    def put(name: str, addr: int, hex_text: str) -> None:
        offset = addr - SOURCE_WINDOWS[name][0]
        raw = bytes.fromhex(hex_text)
        assert 0 <= offset and offset + len(raw) <= len(synthetic[name])
        synthetic[name][offset:offset+len(raw)] = raw
    def call(name: str, addr: int, target: int) -> None:
        raw = b"\xE8" + struct.pack("<i", target - addr - 5)
        put(name, addr, raw.hex())
    for name,site,op in [
        ("summary_band_boundaries",0x007D154B,"8B 43 28"),
        ("summary_band_boundaries",0x007D158B,"D8 0D 8C 19 7D 00"),
        ("summary_power_loop",PRE_SUMMARY_BREAKPOINT,"33 C0"),
        ("summary_power_loop",0x007D1807,"DD 45 D8"),
        ("summary_power_loop",0x007D180A,"D8 04 B0"),
        ("summary_power_loop",0x007D180D,"DD 5D D8"),
        ("summary_mean_and_condition",0x007D185A,"D8 48 04"),
        ("summary_mean_and_condition",0x007D185D,"D9 5B 30"),
        ("summary_mean_and_condition",0x007D1869,"89 43 38"),
        ("summary_mean_and_condition",0x007D186E,"89 43 34"),
        ("summary_peak_neighborhood",0x007D18B8,"8D 43 34"),
        ("summary_peak_neighborhood",0x007D18BC,"8D 43 38"),
        ("summary_peak_y_finalize",0x007D18FC,"D9 5B 38"),
        ("summary_peak_y_finalize",POST_SUMMARY_BREAKPOINT,"33 C0"),
        ("summary_weighted_bin_helper",0x007D21DE,"D9 5D FC"),
        ("summary_weighted_bin_helper",0x007D21E7,"D9 5D F8"),
        ("summary_weighted_bin_helper",0x007D220C,"D9 1E"),
    ]:
        put(name,site,op)
    for name,site,target in [
        ("summary_band_boundaries",0x007D1563,0x00407C74),
        ("summary_band_boundaries",0x007D1591,0x00407C68),
        ("summary_band_boundaries",0x007D159D,0x007B1CF0),
        ("summary_mean_and_condition",0x007D1842,0x00407C58),
        ("summary_peak_neighborhood",0x007D18CC,0x007D21A8),
        ("summary_peak_y_finalize",0x007D18E1,0x00407C58),
    ]:
        call(name,site,target)
    return {k: bytes(v) for k,v in synthetic.items()}


def test_six_source_windows_have_only_addresses_and_sha_metadata():
    assert len(SOURCE_WINDOWS) == 6
    assert PRE_SUMMARY_BREAKPOINT == 0x007D17E7
    assert POST_SUMMARY_BREAKPOINT == 0x007D1900
    for first,last,sha in SOURCE_WINDOWS.values():
        assert first < last <= first + 128
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)


def test_private_summary_structure_with_fabricated_opcodes_only():
    facts = _source_summary_structure(_fake_windows())
    assert facts["source_output_mean_single_field_offset"] == 0x30
    assert facts["source_output_peak_x_single_field_offset"] == 0x34
    assert facts["source_output_peak_y_single_field_offset"] == 0x38
    assert all(v is True for k,v in facts.items() if k.endswith("_verified"))


@pytest.mark.parametrize(("name","address"), [
    ("summary_band_boundaries",0x007D1563),
    ("summary_band_boundaries",0x007D1591),
    ("summary_power_loop",0x007D180D),
    ("summary_mean_and_condition",0x007D185D),
    ("summary_mean_and_condition",0x007D1869),
    ("summary_peak_neighborhood",0x007D18CC),
    ("summary_peak_y_finalize",0x007D18FC),
    ("summary_weighted_bin_helper",0x007D21DE),
    ("summary_weighted_bin_helper",0x007D220C),
])
def test_tampered_synthetic_instruction_rejected(name,address):
    fixture = _fake_windows()
    raw = bytearray(fixture[name])
    raw[address - SOURCE_WINDOWS[name][0]] ^= 0x40
    fixture[name] = bytes(raw)
    with pytest.raises(ValueError):
        _source_summary_structure(fixture)


def test_digest_refuses_synthetic_corruption_and_truncation():
    data = b"synthetic not original Delphi code"
    digest = hashlib.sha256(data).hexdigest()
    _verify_hash(data,0x1000,0x1000+len(data),digest)
    with pytest.raises(ValueError):
        _verify_hash(data+b"!",0x1000,0x1000+len(data),digest)
    with pytest.raises(ValueError):
        _verify_hash(data,0x1000,0x1000+len(data),"0"*64)


def test_invalid_unsafe_call_target_rejected():
    with pytest.raises(ValueError):
        _source_call_target(b"\x90"*5, 0x1000, 0x1000)
    with pytest.raises(ValueError):
        _source_call_target(b"\xE8" + b"\0"*4,0x1000,0x0FFF)


def test_missing_private_original_idp_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        audit_private_getspectrum_summary_source(tmp_path/"missing.idp")
