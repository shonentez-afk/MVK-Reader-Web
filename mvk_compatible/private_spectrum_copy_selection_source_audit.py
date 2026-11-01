"""Stage111Z.12: PRIVATE, read-only original MVKView Copy selected-record audit.

The original IDR project stays only on the operator's computer. This script
verifies three code windows by SHA256, then tests original i386 instruction
shapes and rel32 call targets. It emits only derived address/offset facts,
NEVER source code bytes, private filenames, measurements or paths.

This source attestation DOES NOT demonstrate original runtime clipboard
formatting, nor link an earlier GetSpectrum call to the user's Copy click.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from .private_original_cw_idr_audit import (
    _sections, _read_at_va, audit_original_static_cw,
)

SOURCE = "PRIVATE_MVKVIEW_COPY_SELECTED_RECORD_SOURCE_AUDIT_V1"
COPY_HANDLER = 0x0084BC28
COPY_RECORD_BREAKPOINT = 0x0084BC8C
COPY_SELECTION_HELPER = 0x0084EADC

SOURCE_WINDOWS = {
    "copy_preselection": (
        0x0084BC46, 0x0084BC7B,
        "c2956b34d7e10c3f76b570cfcada98ad240cf0116f40b887ae47aadfad8c61b9",
    ),
    "copy_selected_record": (
        0x0084BC7B, 0x0084BCE2,
        "b75c8794de9d67da5918a967ea3863c522534bae7e0192fff647c4d8846824d2",
    ),
    "copy_selection_helper": (
        0x0084EADC, 0x0084EAF4,
        "c070a199b541b9526c737635af20c5fa7aab499a3e32d3860c3b098b6d9eeba3",
    ),
}


def _verify_window(data: bytes, start: int, end: int, digest: str) -> None:
    if (not isinstance(data, bytes) or start >= end or
            len(data) != end-start or
            hashlib.sha256(data).hexdigest() != digest):
        raise ValueError("Original selected Copy source is not authenticated")


def _call_target(data: bytes, base: int, va: int) -> int:
    idx = va-base
    if idx < 0 or idx + 5 > len(data) or data[idx] != 0xE8:
        raise ValueError("Expected original Copy rel32 call not found")
    return (va + 5 + struct.unpack_from("<i", data, idx+1)[0]) & 0xFFFFFFFF


def _verify_structural_facts(windows: dict[str, bytes]) -> dict:
    def require(block: str, va: int, op_hex: str) -> None:
        raw = windows[block]
        start = SOURCE_WINDOWS[block][0]
        opcode = bytes.fromhex(op_hex)
        pos = va-start
        if pos < 0 or raw[pos:pos+len(opcode)] != opcode:
            raise ValueError("Original Copy selected series instructions changed")

    selector = windows["copy_selection_helper"]
    selected = windows["copy_selected_record"]
    a = SOURCE_WINDOWS["copy_selection_helper"][0]
    b = SOURCE_WINDOWS["copy_selected_record"][0]

    # Single-pane mode forces record 0; otherwise helper chooses the current
    # list/graph record by calling the original selection-object getter.
    require("copy_selection_helper", 0x0084EADC, "83 B8 24 06 00 00 01")
    require("copy_selection_helper", 0x0084EAE5, "33 C0 C3")
    require("copy_selection_helper", 0x0084EAE8, "8B 80 30 04 00 00")
    if _call_target(selector, a, 0x0084EAEE) != 0x005B01C8:
        raise ValueError("Selected record getter call changed")

    # Copy uses its own per-selected-record store in a form object:
    # ESI = form_EBX + 0x908 + selected_index * 72.
    require("copy_selected_record", 0x0084BC7B, "8B C3")
    if _call_target(selected, b, 0x0084BC7D) != COPY_SELECTION_HELPER:
        raise ValueError("Original current Copy record selection call changed")
    require("copy_selected_record", 0x0084BC82, "8D 04 C0")
    require("copy_selected_record", 0x0084BC85, "8D B4 C3 08 09 00 00")

    # EXACT original input words: mean ESI+30, x-position ESI+34,
    # amplitude ESI+38; formatting significant digits 3,4,4.
    require("copy_selected_record", 0x0084BC8C, "FF 76 30")
    require("copy_selected_record", 0x0084BC92, "B8 03 00 00 00")
    require("copy_selected_record", 0x0084BCAD, "D9 46 34")
    require("copy_selected_record", 0x0084BCBD, "B8 04 00 00 00")
    require("copy_selected_record", 0x0084BCCF, "FF 76 38")
    require("copy_selected_record", 0x0084BCD5, "B8 04 00 00 00")
    for va in (0x0084BC97,0x0084BCC2,0x0084BCDA):
        if _call_target(selected,b,va) != 0x007B2090:
            raise ValueError("Original Copy formatter call changed")

    # Original uses graph series axis XScale from nested form structures,
    # NOT necessarily Fs/N from the previous GetSpectrum call.
    require("copy_selected_record", 0x0084BCA4, "8B 83 F4 0F 00 00")
    require("copy_selected_record", 0x0084BCAA, "8B 40 40")
    require("copy_selected_record", 0x0084BCB0, "D8 48 14")
    require("copy_selected_record", 0x0084BCB3, "D9 5D E8")
    return {
        "copy_selected_record_base_offset_hex": "0x0908",
        "copy_selected_record_stride_bytes": 72,
        "copy_selected_record_ptr_register": "ESI",
        "copy_form_ptr_register": "EBX",
        "copy_mean_single_offset_hex": "0x30",
        "copy_peak_x_bin_single_offset_hex": "0x34",
        "copy_peak_y_single_offset_hex": "0x38",
        "copy_graph_xscale_expression":
            "dword:[dword:[dword:[ebx+FF4]+40]+14]",
        "copy_selection_helper_single_pane_first_record_verified": True,
        "copy_selection_helper_active_list_record_verified": True,
        "copy_xscale_graph_f32_multiplication_and_store_verified": True,
        "copy_three_formatter_007B2090_calls_verified": True,
        "copy_three_significant_digits_order": [3,4,4],
        "earlier_GetSpectrum_call_same_as_selected_Copy_record_verified": False,
        "original_Copy_runtime_clipboard_character_parity_verified": False,
    }


def audit_original_copy_selected_record(private_idp: str | Path) -> dict:
    original = audit_original_static_cw(private_idp)
    location = Path(private_idp)
    with location.open("rb") as f:
        sections = _sections(f, location.stat().st_size)
        windows = {}
        for name, (start, stop, digest) in SOURCE_WINDOWS.items():
            raw = _read_at_va(f, sections, start, stop-start, ".text")
            _verify_window(raw, start, stop, digest)
            windows[name] = raw
    return {
        "source": SOURCE,
        "private_original_source_windows_sha256_verified": len(SOURCE_WINDOWS),
        "original_static_x87_cw_hex": original["original_static_fpu_cw_hex"],
        "copy_handler_va_hex": f"0x{COPY_HANDLER:08X}",
        "same_click_copy_record_breakpoint_va_hex":
            f"0x{COPY_RECORD_BREAKPOINT:08X}",
        **_verify_structural_facts(windows),
        "private_original_bytes_measurements_or_paths_exposed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only MVKView Copy selected record IDP audit")
    parser.add_argument("private_idp", help="Local original IDR v3 file")
    args = parser.parse_args(argv)
    try:
        result = audit_original_copy_selected_record(args.private_idp)
    except (OSError, ValueError, TypeError, struct.error):
        parser.exit(2, "Original Copy handler cannot be authenticated; details withheld\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
