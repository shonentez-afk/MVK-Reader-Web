"""Stage111X: read-only PRIVATE IDR v3 static FPU control-flow audit.

The original file stays local. Only source-derived addresses, opcode roles,
aggregate counts and unknown-runtime flags are returned. E8 byte scanning
finds *candidates*, not exhaustive disassembled control flow. The known sites
were separately reviewed against source instructions. This audit cannot
verify the live Delphi CW or the channel's actual FRange.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path
from .private_original_cw_idr_audit import (
    audit_original_static_cw, _sections, _read_at_va,
    SET_8087_CW_VA, GET_8087_CW_VA, FPU_INIT_VA,
)

SOURCE = 'PRIVATE_MVKVIEW_IDR_V3_X87_CALLSITE_AUDIT'
PARSER_TEMP_CW_VA = 0x008C45F0
PARSER_TEMP_CW = 0x133F
PARSER_LOAD_VA = 0x0042EBC8
PARSER_SAVE_VA = 0x0042EBC1
PARSER_RESTORE_VA = 0x0042EC68

# Known code-aligned calls reviewed independently in private disassembly.
DIRECT_CALLS = {
    SET_8087_CW_VA: (0x0041BD84, 0x0041BDDA, 0x00448296),
    GET_8087_CW_VA: (0x0041BD4A, 0x0041BDA2, 0x00448261, 0x00448281),
    FPU_INIT_VA: (0x0040AADC, 0x0040AC02, 0x0040B02A,
                  0x0040B61B, 0x008BF072),
}


def _relative_e8(site: int, target: int) -> bytes:
    delta = target - (site + 5)
    if not -(2 ** 31) <= delta < 2 ** 31:
        raise ValueError('Relative call outside i386 range')
    return b'\xE8' + struct.pack('<i', delta)


def _candidate_e8_calls(data: bytes, base: int, target: int) -> set[int]:
    found = set()
    pos = data.find(b'\xE8')
    while pos >= 0:
        if pos + 5 <= len(data):
            dest = (base + pos + 5 + struct.unpack_from('<i', data, pos + 1)[0]) & 0xFFFFFFFF
            if dest == target:
                found.add(base + pos)
        pos = data.find(b'\xE8', pos + 1)
    return found


def audit_private_x87_calls(path: str | Path) -> dict:
    """Fail closed for mismatching source bytes/new unexplained raw E8 hits."""
    verified = audit_original_static_cw(path)
    with Path(path).open('rb') as file:
        sections = _sections(file, Path(path).stat().st_size)
        code = [section for section in sections if section.name in ('.text', '.itext')]
        if {section.name for section in code} != {'.text', '.itext'}:
            raise ValueError('Both original executable sections required')
        raw = {}
        for section in code:
            file.seek(section.raw_offset)
            raw[section.name] = (section.va, file.read(section.size))
            if len(raw[section.name][1]) != section.size:
                raise ValueError('Truncated private executable segment')
        counts = {}
        for target, known_sites in DIRECT_CALLS.items():
            for site in known_sites:
                if _read_at_va(file, sections, site, 5) != _relative_e8(site, target):
                    raise ValueError('Original FPU callsite mismatch')
            candidates = set()
            for base, content in raw.values():
                candidates.update(_candidate_e8_calls(content, base, target))
            if candidates != set(known_sites):
                # Raw E8 candidates can sometimes occur inside immediates;
                # report no inferred control flow until manually reviewed.
                raise ValueError('Unreviewed or missing FPU relative call candidate')
            counts[target] = len(candidates)

        temporary = struct.unpack('<H', _read_at_va(
            file, sections, PARSER_TEMP_CW_VA, 2, '.data'))[0]
        if temporary != PARSER_TEMP_CW:
            raise ValueError('Private numeric parser CW differs from baseline')
        if _read_at_va(file, sections, PARSER_SAVE_VA, 4, '.text') != b'\x9B\xD9\x7D\xF4':
            raise ValueError('Original numeric parser FSTCW save mismatch')
        if _read_at_va(file, sections, PARSER_LOAD_VA, 6, '.text') != (
                b'\xD9\x2D' + struct.pack('<I', PARSER_TEMP_CW_VA)):
            raise ValueError('Original parser FLDCW temporary load mismatch')
        if _read_at_va(file, sections, PARSER_RESTORE_VA, 3, '.text') != b'\xD9\x6D\xF4':
            raise ValueError('Original numeric parser FLDCW restoration mismatch')
        # Check the two callback wrappers restore the pre-callback CW,
        # not a hardcoded global CW. This is a local structural proof only.
        for site in (0x0041BD84, 0x0041BDDA):
            if _read_at_va(file, sections, site - 2, 2, '.text') != b'\x8B\xC3':
                raise ValueError('CW restore wrapper does not reload saved CW')
        # Exception-mask helper deliberately preserves upper ten bits.
        if _read_at_va(file, sections, 0x00448288, 4, '.text') != b'\x66\xB8\xC0\xFF':
            raise ValueError('Exception mask helper source mismatch')
        return {
            'source': SOURCE,
            'original_static_initial_cw_hex': verified['original_static_fpu_cw_hex'],
            'parser_temporary_cw_hex': f'0x{temporary:04X}',
            'parser_temp_prec_mode': '64_bit',
            'parser_temp_exception_mask': f'0x{temporary & 0x3F:02X}',
            'source_direct_set8087cw_callsites': counts[SET_8087_CW_VA],
            'source_direct_get8087cw_callsites': counts[GET_8087_CW_VA],
            'source_direct_fpuinit_callsites': counts[FPU_INIT_VA],
            'source_two_external_callback_wrappers_save_and_restore_cw': True,
            'source_exception_mask_helper_preserves_pc_rc_bits': True,
            'source_numeric_parser_saves_and_restores_cw': True,
            'original_live_process_fpu_cw_at_graph_verified': False,
            'all_indirect_calls_and_arbitrary_fpu_state_writers_excluded': False,
            'original_selected_channel_runtime_frange_verified': False,
            'original_delphi_spectrum_numeric_parity_verified': False,
            'private_original_bytes_or_paths_in_report': False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Private offline FPU callsite audit')
    parser.add_argument('private_idp', help='PRIVATE original MVKView IDR v3 file')
    args = parser.parse_args(argv)
    try:
        result = audit_private_x87_calls(args.private_idp)
    except (OSError, ValueError, struct.error):
        parser.exit(2, 'Original private FPU call graph could not be verified\n')
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
