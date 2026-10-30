"""Only SYNTHETIC IDR image: no original private bytes in GitHub or CircleCI."""
from __future__ import annotations
import json
import struct
import pytest

from mvk_compatible.private_original_cw_idr_audit import (
    MAGIC, SOURCE, FPU_INIT_VA, SET_8087_CW_VA, GET_8087_CW_VA,
    CHANNEL_FRANGE_DEFAULT_VA, TARGET_FPU_WORD_VA, EXPECTED_INITIAL_CW,
    FPU_INIT_SIGNATURE, SET_8087_SIGNATURE, GET_8087_SIGNATURE,
    DEFAULT_FRANGE_SIGNATURE, audit_original_static_cw, main,
)


def synthetic_project(path, *, static_cw=EXPECTED_INITIAL_CW,
                      corrupt_address=None, bad_magic=False):
    """Test segments are synthetic, compact and padded only with zeros."""
    regions = [
        ('.text', 0x401000, 0x3D0000, 0x60000020),
        ('.data', 0x8C2000, 0x100, 0xC0000040),
    ]
    sections = [bytearray(size) for _, _, size, _ in regions]
    for addr, content in (
        (FPU_INIT_VA, FPU_INIT_SIGNATURE),
        (SET_8087_CW_VA, SET_8087_SIGNATURE),
        (GET_8087_CW_VA, GET_8087_SIGNATURE),
        (CHANNEL_FRANGE_DEFAULT_VA, DEFAULT_FRANGE_SIGNATURE),
        (TARGET_FPU_WORD_VA, struct.pack('<H', static_cw)),
    ):
        for i, (_, va, size, _) in enumerate(regions):
            if va <= addr and addr + len(content) <= va + size:
                sections[i][addr - va:addr - va + len(content)] = content
                break
        else:
            raise AssertionError('Missing synthetic segment for fixture')
    if corrupt_address is not None:
        for i, (_, va, size, _) in enumerate(regions):
            if va <= corrupt_address < va + size:
                sections[i][corrupt_address - va] ^= 1
    header = bytearray(0x3C)
    header[:len(MAGIC)] = b'BROKENMAGIC!' if bad_magic else MAGIC
    struct.pack_into('<I', header, 0x38, len(regions))
    for name, va, size, flags in regions:
        header += struct.pack('<IIII', va, size, flags, len(name)) + name.encode('ascii')
    path.write_bytes(bytes(header) + b''.join(sections) + b'SYNTHETIC-ONLY')
    return path


def test_idr_length_prefixed_section_map_extracts_original_static_cw(tmp_path, capsys):
    file = synthetic_project(tmp_path / 'synthetic.idp')
    report = audit_original_static_cw(file)
    assert report['source'] == SOURCE
    assert report['original_static_fpu_cw_hex'] == '0x1332'
    assert report['original_static_cw_segment'] == '.data'
    assert report['x87_precision_mode_at_static_init'] == '64_bit'
    assert report['x87_rounding_mode_at_static_init'] == 'nearest'
    assert report['x87_exception_mask_bits_hex'] == '0x32'
    assert report['source_constructor_default_channel_frange_single'] == 1.0
    assert report['source_fpu_init_and_get_set_instructions_verified']
    assert not report['same_original_process_runtime_fpu_cw_verified']
    assert not report['original_selected_channel_runtime_frange_verified']
    assert not report['original_delphi_graph_default_vscale_numeric_parity_verified']
    assert report['original_private_file_bytes_or_path_in_report'] is False
    assert main([str(file)]) == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == report
    assert str(file) not in stdout
    assert 'SYNTHETIC-ONLY' not in stdout


@pytest.mark.parametrize('altered', [0x037F, 0x133F, 0x1032, 0x1232])
def test_modified_idr_cw_does_not_get_false_original_attestation(tmp_path, altered):
    file = synthetic_project(tmp_path / 'altered.idp', static_cw=altered)
    with pytest.raises(ValueError, match='verified MVKView baseline'):
        audit_original_static_cw(file)


@pytest.mark.parametrize('at', [
    FPU_INIT_VA, SET_8087_CW_VA, GET_8087_CW_VA,
    CHANNEL_FRANGE_DEFAULT_VA,
])
def test_corrupt_original_instruction_signature_is_rejected(tmp_path, at):
    file = synthetic_project(tmp_path / 'corrupt.idp', corrupt_address=at)
    with pytest.raises(ValueError, match='sequence mismatch'):
        audit_original_static_cw(file)


def test_wrong_magic_and_symlink_fail_closed_without_path_leak(tmp_path, capsys):
    file = synthetic_project(tmp_path / 'incorrect.idp', bad_magic=True)
    with pytest.raises(ValueError, match='IDR'):
        audit_original_static_cw(file)
    with pytest.raises(SystemExit) as exc:
        main([str(file)])
    assert exc.value.code == 2
    assert str(file) not in capsys.readouterr().err
    good = synthetic_project(tmp_path / 'good.idp')
    shortcut = tmp_path / 'symbolic.idp'
    try:
        shortcut.symlink_to(good)
    except OSError:
        pytest.skip('No symlink capability')
    with pytest.raises(ValueError, match='real private'):
        audit_original_static_cw(shortcut)


def test_truncated_source_section_fails_before_invalid_read(tmp_path):
    file = synthetic_project(tmp_path / 'short.idp')
    data = file.read_bytes()
    file.write_bytes(data[:300])
    with pytest.raises(ValueError):
        audit_original_static_cw(file)


def test_idr_script_cannot_authenticate_unrelated_file(tmp_path):
    file = tmp_path / 'wrong.txt'
    file.write_text('CW=0x1332')
    with pytest.raises(ValueError):
        audit_original_static_cw(file)
