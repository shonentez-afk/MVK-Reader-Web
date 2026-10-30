"""Stage111Z.5: synthetic-only checks of original Hann source fingerprinting.

No original bytes, private IDP, raw spectrum, EXE or field measurements are
available to CI. The artificial snippets below are invented for testing.
"""
from __future__ import annotations
import hashlib
import struct

import pytest

from mvk_compatible.private_hann_source_audit import (
    SOURCE_WINDOWS, HANN_COUNT, TABLE_VA,
    _verify_digest, _verified_call_target, _structural_facts,
    audit_private_hann_source,
)


def test_hann_private_source_fingerprint_metadata():
    assert len(SOURCE_WINDOWS) == 5
    assert HANN_COUNT == 262144 and TABLE_VA == 0x0096DA48
    assert {row[0] for row in SOURCE_WINDOWS.values()} == {'.text', '.itext'}
    for section, first, last, sha256 in SOURCE_WINDOWS.values():
        assert first < last and last-first <= 128
        assert len(sha256) == 64
        assert all(c in '0123456789abcdef' for c in sha256)


def test_fingerprint_accepts_only_valid_length_and_checksum():
    data = b'independent synthetic Hann source, not original'
    digest = hashlib.sha256(data).hexdigest()
    _verify_digest(data, 0x1000, 0x1000+len(data), digest)
    with pytest.raises(ValueError):
        _verify_digest(data+b'!', 0x1000, 0x1000+len(data), digest)
    with pytest.raises(ValueError):
        _verify_digest(data, 0x1000, 0x1000+len(data), '0'*64)
    with pytest.raises(ValueError):
        _verify_digest(data, 0x1000, 0x0FFF, digest)


def _synthetic_hann_structural_blocks():
    """Minimal fabricated opcodes, not original code image."""
    blocks = {
        name: bytearray(b'\x90'*(stop-start))
        for name, (_, start, stop, _) in SOURCE_WINDOWS.items()
    }
    init = blocks['hann_initializer']
    init_base = SOURCE_WINDOWS['hann_initializer'][1]
    f = blocks['fft_consumer']
    f_base = SOURCE_WINDOWS['fft_consumer'][1]

    def put(buf, base, va, hex_data):
        b=bytes.fromhex(hex_data)
        buf[va-base:va-base+len(b)] = b

    instructions = {
        0x008C106C:'83 2D 44 DA 96 00 01',
        0x008C1077:'BB 48 DA 96 00',
        0x008C107F:'DB 45 FC',
        0x008C1082:'DB 2D D0 10 8C 00',
        0x008C1088:'DE C9',
        0x008C108A:'D8 35 DC 10 8C 00',
        0x008C109C:'D9 E8',
        0x008C109E:'DE E1',
        0x008C10A0:'DB 7D F0',
        0x008C10A4:'68 FF 3F 00 00 68 00 00 00 C0 6A 00',
        0x008C10B5:'DB 6D F0',
        0x008C10B8:'DE F1',
        0x008C10BA:'D9 1B',
        0x008C10C1:'81 FE 00 00 04 00',
    }
    for va, signature in instructions.items():
        put(init, init_base, va, signature)
    for address, target in ((0x008C1097,0x00407C00),
                            (0x008C10B0,0x00407C58)):
        put(init, init_base, address,
            (b'\xE8'+struct.pack('<i',target-address-5)).hex())

    fft_instr = {
        0x007D2044:'B8 00 00 04 00',
        0x007D204B:'F7 75 FC',
        0x007D205E:'0F AF 75 F4',
        0x007D2065:'D8 0C B5 48 DA 96 00',
        0x007D2072:'D9 1C C1',
    }
    for va, signature in fft_instr.items():
        put(f, f_base, va, signature)
    va=0x007D2083
    put(f, f_base, va, (b'\xE8'+struct.pack('<i',0x007CC3F8-va-5)).hex())
    vals = blocks['hann_math_constants']
    vals[:10] = bytes.fromhex('35 C2 68 21 A2 DA 0F C9 01 40')
    vals[12:16] = struct.pack('<f', 262144.)
    blocks['cos_helper'][6:8] = b'\xD9\xFF'
    blocks['sqrt_helper'][6:8] = b'\xD9\xFA'
    return {key: bytes(value) for key, value in blocks.items()}


def test_synthetic_source_structure_and_corrupt_callsite():
    snippets = _synthetic_hann_structural_blocks()
    facts = _structural_facts(snippets)
    assert len(facts) == 6 and all(facts.values())
    init=bytearray(snippets['hann_initializer'])
    init[0x008C1097-SOURCE_WINDOWS['hann_initializer'][1]] ^= 0x10
    with pytest.raises(ValueError):
        _structural_facts({**snippets, 'hann_initializer': bytes(init)})


def test_synthetic_changed_stride_and_table_address_are_rejected():
    snippets = _synthetic_hann_structural_blocks()
    for section, va in [('fft_consumer',0x007D204B),
                        ('fft_consumer',0x007D2065),
                        ('hann_initializer',0x008C10C1)]:
        changed=bytearray(snippets[section])
        changed[va-SOURCE_WINDOWS[section][1]] ^= 0x40
        with pytest.raises(ValueError):
            _structural_facts({**snippets,section:bytes(changed)})


def test_relative_call_decoder_is_fail_closed():
    start=0x1000
    raw=b'\xE8'+struct.pack('<i',0x2030-(start+5))
    assert _verified_call_target(raw,start,start)==0x2030
    with pytest.raises(ValueError):
        _verified_call_target(b'\x90'*5,start,start)
    with pytest.raises(ValueError):
        _verified_call_target(raw,start,start+1)


def test_original_private_file_absent_is_not_fake_success(tmp_path):
    with pytest.raises(ValueError):
        audit_private_hann_source(tmp_path/'nonexistent.idp')
