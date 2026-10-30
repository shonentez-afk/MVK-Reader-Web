"""Stage111Z.5: read-only/private IDR Hann-generator audit (no original bytes exported).

This verifies the source instructions/constant windows, NOT runtime Delphi
window bits, channel samples, process FPU state or complete FFT parity.
Never commit/upload private EXE, IDP, PAS, DFM, BIN, PCAPNG or archives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from .private_original_cw_idr_audit import (
    _read_at_va, _sections, audit_original_static_cw,
)

SOURCE = 'PRIVATE_MVKVIEW_HANN_X87_SOURCE_AUDIT_V1'
HANN_COUNT = 262144
TABLE_VA = 0x0096DA48  # original BSS table, populated at runtime only
SOURCE_WINDOWS = {
    'hann_initializer': ('.itext', 0x008C1064, 0x008C10CF,
         'c79e0efde295eb23b32bc0cb50ad7b9a586f5ef214a374611ff20775ab268c4c'),
    'hann_math_constants': ('.itext', 0x008C10D0, 0x008C10E0,
         '6898c1941321092844404b9c30fc10f0b6b76e3fd2d95e778a61b52e95dcd1ed'),
    'cos_helper': ('.text', 0x00407C00, 0x00407C0D,
         'b19ec2f0b6c9d0173d60a01855ac7bbc3370bb0d1f627a6329ffc716c1d7244b'),
    'sqrt_helper': ('.text', 0x00407C58, 0x00407C65,
         '32acf2ea0996c5e1059ecd00e14f3c4f645ed521cd5b5f63c0e5e2f4b1e70e8c'),
    'fft_consumer': ('.text', 0x007D2044, 0x007D2088,
         '13108e3f370fd6e2bf6b4415d88b17ea7ec53db9e527b38eb559b64a7b2d9088'),
}


def _verify_digest(data: bytes, start: int, end: int, digest: str) -> None:
    if (not isinstance(data, bytes) or start >= end or len(data) != end - start
            or hashlib.sha256(data).hexdigest() != digest):
        raise ValueError('Private original Hann source fingerprint mismatch')


def _verified_call_target(src: bytes, base_va: int, call_va: int) -> int:
    offset = call_va - base_va
    if offset < 0 or offset + 5 > len(src) or src[offset] != 0xE8:
        raise ValueError('Original Hann math callsite missing')
    return (call_va + 5 + struct.unpack_from('<i', src, offset + 1)[0]) & 0xFFFFFFFF


def _structural_facts(blocks: dict[str, bytes]) -> dict:
    """Inspect previously SHA-verified structural instructions; no code output."""
    init = blocks['hann_initializer']
    vals = blocks['hann_math_constants']
    fft = blocks['fft_consumer']
    cos = blocks['cos_helper']
    sqrt = blocks['sqrt_helper']

    def require(data: bytes, start: int, va: int, opcode: str) -> None:
        sig = bytes.fromhex(opcode)
        offset = va - start
        if offset < 0 or data[offset:offset + len(sig)] != sig:
            raise ValueError('Original Hann instruction or constant changed')

    base = SOURCE_WINDOWS['hann_initializer'][1]
    require(init, base, 0x008C106C, '83 2D 44 DA 96 00 01')  # one-time init guard
    require(init, base, 0x008C1077, 'BB 48 DA 96 00')      # table address
    require(init, base, 0x008C107F, 'DB 45 FC')            # FILD index
    require(init, base, 0x008C1082, 'DB 2D D0 10 8C 00')  # FLD 2*pi 80-bit
    require(init, base, 0x008C1088, 'DE C9')               # x87 multiply
    require(init, base, 0x008C108A, 'D8 35 DC 10 8C 00')  # divide by f32 N
    require(init, base, 0x008C109C, 'D9 E8')               # FLD1
    require(init, base, 0x008C109E, 'DE E1')               # 1-cos, reverse sub
    require(init, base, 0x008C10A0, 'DB 7D F0')            # FSTP Extended
    require(init, base, 0x008C10A4,
            '68 FF 3F 00 00 68 00 00 00 C0 6A 00')         # 1.5 Extended
    require(init, base, 0x008C10B5, 'DB 6D F0')            # FLD Extended
    require(init, base, 0x008C10B8, 'DE F1')               # result/sqrt
    require(init, base, 0x008C10BA, 'D9 1B')               # FSTP table Single
    require(init, base, 0x008C10C1, '81 FE 00 00 04 00')   # N=262144
    if _verified_call_target(init, base, 0x008C1097) != 0x00407C00:
        raise ValueError('Original Hann FCOS call target differs')
    if _verified_call_target(init, base, 0x008C10B0) != 0x00407C58:
        raise ValueError('Original Hann FSQRT call target differs')
    # 80-bit extended representation of exact rounded 2*pi (scientific const).
    if vals[:10] != bytes.fromhex('35 C2 68 21 A2 DA 0F C9 01 40'):
        raise ValueError('Source Hann two-pi Extended constant differs')
    if struct.unpack_from('<f', vals, 12)[0] != float(HANN_COUNT):
        raise ValueError('Original Hann table length constant differs')
    if b'\xD9\xFF' not in cos or b'\xD9\xFA' not in sqrt:
        raise ValueError('Source helpers are not FCOS and FSQRT')
    fft_base = SOURCE_WINDOWS['fft_consumer'][1]
    require(fft, fft_base, 0x007D2044, 'B8 00 00 04 00')
    require(fft, fft_base, 0x007D204B, 'F7 75 FC')          # stride = 262144/N
    require(fft, fft_base, 0x007D205E, '0F AF 75 F4')      # i*stride
    require(fft, fft_base, 0x007D2065, 'D8 0C B5 48 DA 96 00')
    require(fft, fft_base, 0x007D2072, 'D9 1C C1')         # FSTP windowed Single
    if _verified_call_target(fft, fft_base, 0x007D2083) != 0x007CC3F8:
        raise ValueError('Original spectrum forward FFT target differs')
    return {
        'original_hann_constructor_once_verified': True,
        'original_hann_extended_two_pi_and_float32_size_verified': True,
        'original_hann_x87_fcos_and_fsqrt_verified': True,
        'original_hann_extended_intermediate_and_single_final_store_verified': True,
        'original_fft_stride_and_hann_multiplication_verified': True,
        'original_spectrum_calls_positive_angle_fft_verified': True,
    }


def audit_private_hann_source(path: str | Path) -> dict:
    original = audit_original_static_cw(path)
    p = Path(path)
    with p.open('rb') as f:
        sections = _sections(f, p.stat().st_size)
        blocks = {}
        for name, (section_name, start, end, digest) in SOURCE_WINDOWS.items():
            data = _read_at_va(f, sections, start, end-start, section_name)
            _verify_digest(data, start, end, digest)
            blocks[name] = data
    structure = _structural_facts(blocks)
    return {
        'source': SOURCE,
        'original_static_cw_hex': original['original_static_fpu_cw_hex'],
        'source_code_windows_sha256_verified': len(SOURCE_WINDOWS),
        'source_hann_table_elements': HANN_COUNT,
        'source_hann_table_bss_base_hex': f'0x{TABLE_VA:08X}',
        **structure,
        'original_hann_initializer_runtime_cw_observed': False,
        'original_runtime_hann_table_bitwise_observed': False,
        'original_fft_numeric_parity_verified': False,
        'private_code_or_measurements_in_report': False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Local read-only private MVKView Hann audit')
    p.add_argument('private_idp', help='Local PRIVATE original IDR v3 file')
    args = p.parse_args(argv)
    try:
        result = audit_private_hann_source(args.private_idp)
    except (OSError, ValueError, TypeError, struct.error):
        p.exit(2, 'Private original Hann source cannot be verified; details withheld\n')
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
