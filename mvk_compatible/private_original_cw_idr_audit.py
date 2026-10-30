"""Stage111W: offline audit of original MVKView's STATIC x87 FPU control word.

Only the user-supplied PRIVATE IDR project is read. The audit returns derived
flags and small numeric parameters, not original code/IDP bytes or file paths.
The initial on-disk CW is not proof of the live process' CW during spectrum.
Never transfer a private .idp, production BIN, PAS/DFM, or source measurements
into GitHub or CI. CI tests use entirely synthetic IDR fixtures.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
from dataclasses import dataclass

SOURCE = 'PRIVATE_MVKVIEW_IDR_V3_STATIC_FPU_CW_AUDIT'
MAGIC = b'IDR proj v.3'
HEADER_COUNT_OFFSET = 0x38
SECTIONS_START = 0x3C
TARGET_FPU_WORD_VA = 0x008C2028
FPU_INIT_VA = 0x00409570
SET_8087_CW_VA = 0x00407664
GET_8087_CW_VA = 0x00407674
CHANNEL_FRANGE_DEFAULT_VA = 0x007D0A61
EXPECTED_INITIAL_CW = 0x1332
FILE_SIZE_LIMIT = 256 * 1024 * 1024
WORD_BYTES = struct.pack('<I', TARGET_FPU_WORD_VA)

# Instruction forms are generic x87/i386 opcodes, not an original code dump.
FPU_INIT_SIGNATURE = b'\xdb\xe3\x9b\xd9\x2d' + WORD_BYTES + b'\xc3'
SET_8087_SIGNATURE = b'\x66\xa3' + WORD_BYTES + b'\xdb\xe2\xd9\x2d' + WORD_BYTES + b'\xc3'
GET_8087_SIGNATURE = bytes.fromhex('6a 00 d9 3c 24 58 c3')
DEFAULT_FRANGE_SIGNATURE = bytes.fromhex('c7 46 04 00 00 80 3f')

PRECISION = {0: '24_bit', 2: '53_bit', 3: '64_bit'}
ROUNDING = {0: 'nearest', 1: 'toward_minus_infinity',
            2: 'toward_plus_infinity', 3: 'toward_zero'}


@dataclass(frozen=True)
class Section:
    name: str
    va: int
    size: int
    flags: int
    raw_offset: int


def _sections(src, size: int) -> tuple[Section, ...]:
    """IDR proj v3 uses 4 dwords and a LENGTH-PREFIXED section name.

    Unlike a null-terminated C string, the byte immediately after the last
    name character begins the next descriptor. The raw image segments then
    appear in the same order directly after the descriptor table.
    """
    src.seek(0)
    header = src.read(4096)
    if not header.startswith(MAGIC) or len(header) < SECTIONS_START:
        raise ValueError('Not the expected IDR v3 project format')
    count = struct.unpack_from('<I', header, HEADER_COUNT_OFFSET)[0]
    if count not in range(1, 33):
        raise ValueError('Invalid IDR section count')
    pos = SECTIONS_START
    descriptors = []
    for _ in range(count):
        if pos + 16 > len(header):
            raise ValueError('Truncated IDR segment descriptor')
        va, length, flags, name_length = struct.unpack_from('<IIII', header, pos)
        if (not 1 <= name_length <= 32 or not 1 <= length <= FILE_SIZE_LIMIT
                or va + length > 2 ** 32 or pos + 16 + name_length > len(header)):
            raise ValueError('Invalid IDR segment descriptor fields')
        name_bytes = header[pos + 16:pos + 16 + name_length]
        try:
            name = name_bytes.decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('Non-ASCII IDR section name') from exc
        descriptors.append((name, va, length, flags))
        pos += 16 + name_length
    if len({name for name, _, _, _ in descriptors}) != len(descriptors):
        raise ValueError('Duplicate IDR section names')
    virtual = sorted(descriptors, key=lambda s: s[1])
    if any(previous[1] + previous[2] > next_[1]
           for previous, next_ in zip(virtual, virtual[1:])):
        raise ValueError('Overlapping IDR virtual ranges')
    offset = pos
    sections = []
    for name, va, length, flags in descriptors:
        if offset + length > size:
            raise ValueError('Truncated IDR raw section')
        sections.append(Section(name, va, length, flags, offset))
        offset += length
    return tuple(sections)


def _read_at_va(src, sections: tuple[Section, ...], va: int,
                length: int, expected_section: str | None = None) -> bytes:
    if length <= 0 or length > 128:
        raise ValueError('Invalid source read length')
    for sec in sections:
        if sec.va <= va and va + length <= sec.va + sec.size:
            if expected_section is not None and sec.name != expected_section:
                raise ValueError('Unexpected original segment for source value')
            src.seek(sec.raw_offset + (va - sec.va))
            data = src.read(length)
            if len(data) != length:
                raise ValueError('Truncated original source read')
            return data
    raise ValueError('Original virtual address not in IDR segment image')


def audit_original_static_cw(path: str | Path) -> dict:
    """Audit original on-disk IDR values; do not claim active process parity."""
    location = Path(path)
    if (location.is_symlink() or not location.is_file()
            or location.suffix.lower() != '.idp'):
        raise ValueError('Expected a real private IDP project file')
    size = location.stat().st_size
    if not 4096 <= size <= FILE_SIZE_LIMIT:
        raise ValueError('Private IDP project length outside safety bounds')
    with location.open('rb') as src:
        sections = _sections(src, size)
        if not ({'.text', '.data'} <= {s.name for s in sections}):
            raise ValueError('Expected source text and data segments')
        if _read_at_va(src, sections, FPU_INIT_VA, len(FPU_INIT_SIGNATURE),
                       expected_section='.text') != FPU_INIT_SIGNATURE:
            raise ValueError('Original FpuInit machine instruction sequence mismatch')
        if _read_at_va(src, sections, SET_8087_CW_VA, len(SET_8087_SIGNATURE),
                       expected_section='.text') != SET_8087_SIGNATURE:
            raise ValueError('Original Set8087CW instruction sequence mismatch')
        if _read_at_va(src, sections, GET_8087_CW_VA, len(GET_8087_SIGNATURE),
                       expected_section='.text') != GET_8087_SIGNATURE:
            raise ValueError('Original Get8087CW instruction sequence mismatch')
        if _read_at_va(src, sections, CHANNEL_FRANGE_DEFAULT_VA,
                       len(DEFAULT_FRANGE_SIGNATURE),
                       expected_section='.text') != DEFAULT_FRANGE_SIGNATURE:
            raise ValueError('Original FRange constructor sequence mismatch')
        source_cw = struct.unpack('<H', _read_at_va(
            src, sections, TARGET_FPU_WORD_VA, 2,
            expected_section='.data'))[0]
    # Fail closed: a modified project cannot be described as source-verified.
    if source_cw != EXPECTED_INITIAL_CW:
        raise ValueError('Initial FPU CW differs from the verified MVKView baseline')
    pc = (source_cw >> 8) & 3
    if pc not in PRECISION:
        raise ValueError('Reserved x87 precision-control mode')
    return {
        'source': SOURCE,
        'original_static_fpu_cw_hex': f'0x{source_cw:04X}',
        'original_static_fpu_cw_address_hex': f'0x{TARGET_FPU_WORD_VA:08X}',
        'original_static_cw_segment': '.data',
        'source_fpu_init_and_get_set_instructions_verified': True,
        'source_constructor_default_channel_frange_single': 1.0,
        'source_constructor_default_frange_verified': True,
        'x87_precision_mode_at_static_init': PRECISION[pc],
        'x87_rounding_mode_at_static_init': ROUNDING[(source_cw >> 10) & 3],
        'x87_exception_mask_bits_hex': f'0x{source_cw & 0x003F:02X}',
        'static_cw_matches_reconstructed_source_bytes': True,
        'same_original_process_runtime_fpu_cw_verified': False,
        'original_selected_channel_runtime_frange_verified': False,
        'original_delphi_graph_default_vscale_numeric_parity_verified': False,
        'original_private_file_bytes_or_path_in_report': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Offline MVKView IDR static FPU audit')
    parser.add_argument('private_idp', help='Local PRIVATE original IDR v3 file; never upload')
    args = parser.parse_args(argv)
    try:
        report = audit_original_static_cw(args.private_idp)
    except (OSError, ValueError, struct.error):
        parser.exit(2, 'Original project cannot be verified; private details withheld\n')
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
