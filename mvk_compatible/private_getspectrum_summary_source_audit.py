"""Stage111Z.9: read-only PRIVATE original GetSpectrum summary source attestation.

The operator's original IDR remains only on their own computer. Public
content comprises SHA256 hashes of short code windows and structural i386
instruction tests. Neither source bytes nor actual measurement arrays are
printed/exported. Static source verification IS NOT original runtime parity.
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

SOURCE = "PRIVATE_MVKVIEW_ORIGINAL_GETSPECTRUM_SUMMARY_SOURCE_AUDIT_V1"
PRE_SUMMARY_BREAKPOINT = 0x007D17E7
POST_SUMMARY_BREAKPOINT = 0x007D1900
SOURCE_WINDOWS = {
    "summary_band_boundaries": (
        0x007D154B, 0x007D15BC,
        "7c9932682f7797b8d7a645cf155815e4a5f7e007f2d2e7f6522fcd99ff00f267"),
    "summary_power_loop": (
        0x007D17E7, 0x007D1832,
        "0fceff3096d0b0af7b0a380fba4fd33580bcebc0832d13cbd0f9f99f825ff6a1"),
    "summary_mean_and_condition": (
        0x007D1832, 0x007D1876,
        "1be603c033c65d8418ed02f3df20547b1758fbfe1c763f80a21b225130d55b8c"),
    "summary_peak_neighborhood": (
        0x007D1876, 0x007D18D1,
        "64d775dccedf1c33059a190eda43fda9ebbd3b17c6f29efdc95984932896ab15"),
    "summary_peak_y_finalize": (
        0x007D18D1, 0x007D191D,
        "118e262bfce6be39415bca86dfa4cf3a777f10604a9e289af53dc55890d6aa7c"),
    "summary_weighted_bin_helper": (
        0x007D21A8, 0x007D2223,
        "01dfee1801fdb15ebde2b992b03274643c524569ce5d748981cb30ea2cf8c0b7"),
}


def _verify_hash(data: bytes, first: int, last: int, digest: str) -> None:
    if (not isinstance(data, bytes) or first >= last or
            len(data) != last-first or hashlib.sha256(data).hexdigest() != digest):
        raise ValueError("Original GetSpectrum summary source identity mismatch")


def _source_call_target(window: bytes, start: int, site: int) -> int:
    off = site-start
    if off < 0 or off+5 > len(window) or window[off] != 0xE8:
        raise ValueError("Original summary helper is not a direct E8 call")
    return (site+5+struct.unpack_from("<i", window, off+1)[0]) & 0xFFFFFFFF


def _source_summary_structure(windows: dict[str, bytes]) -> dict:
    def require(block: str, site: int, op: str) -> None:
        first = SOURCE_WINDOWS[block][0]
        wanted = bytes.fromhex(op)
        if windows[block][site-first:site-first+len(wanted)] != wanted:
            raise ValueError("Original summary source structure differs")

    bounds = windows["summary_band_boundaries"]
    require("summary_band_boundaries", 0x007D154B, "8B 43 28")
    require("summary_band_boundaries", 0x007D158B, "D8 0D 8C 19 7D 00")
    # Original lower-band cutoff uses nearest-even ROUND and max(2, value).
    if (_source_call_target(bounds, 0x007D154B, 0x007D1563) != 0x00407C74 or
            _source_call_target(bounds, 0x007D154B, 0x007D1591) != 0x00407C68 or
            _source_call_target(bounds, 0x007D154B, 0x007D159D) != 0x007B1CF0):
        raise ValueError("Original low/high band helpers changed")
    require("summary_power_loop", PRE_SUMMARY_BREAKPOINT, "33 C0")
    require("summary_power_loop", 0x007D1807, "DD 45 D8")
    require("summary_power_loop", 0x007D180A, "D8 04 B0")
    require("summary_power_loop", 0x007D180D, "DD 5D D8")
    require("summary_mean_and_condition", 0x007D185A, "D8 48 04")
    require("summary_mean_and_condition", 0x007D185D, "D9 5B 30")
    require("summary_mean_and_condition", 0x007D1869, "89 43 38")
    require("summary_mean_and_condition", 0x007D186E, "89 43 34")
    if _source_call_target(
        windows["summary_mean_and_condition"],
        0x007D1832, 0x007D1842
    ) != 0x00407C58:
        raise ValueError("Original OutputMean sqrt source changed")
    require("summary_peak_neighborhood", 0x007D18B8, "8D 43 34")
    require("summary_peak_neighborhood", 0x007D18BC, "8D 43 38")
    if _source_call_target(
        windows["summary_peak_neighborhood"],
        0x007D1876, 0x007D18CC
    ) != 0x007D21A8:
        raise ValueError("Original 5-bin centroid helper changed")
    require("summary_peak_y_finalize", 0x007D18FC, "D9 5B 38")
    require("summary_peak_y_finalize", POST_SUMMARY_BREAKPOINT, "33 C0")
    if _source_call_target(
        windows["summary_peak_y_finalize"],
        0x007D18D1, 0x007D18E1
    ) != 0x00407C58:
        raise ValueError("Original OutputPeakY sqrt source changed")
    require("summary_weighted_bin_helper", 0x007D21DE, "D9 5D FC")
    require("summary_weighted_bin_helper", 0x007D21E7, "D9 5D F8")
    require("summary_weighted_bin_helper", 0x007D220C, "D9 1E")
    return {
        "source_summary_upper_bound_trunc_n_div_2_56_verified": True,
        "source_summary_lower_bound_round_n_div_2fs_max_2_verified": True,
        "source_band_sum_qword_store_every_add_verified": True,
        "source_strict_peak_first_tie_verified": True,
        "source_weighted_five_bin_peak_and_single_intermediates_verified": True,
        "source_output_mean_single_field_offset": 0x30,
        "source_output_peak_x_single_field_offset": 0x34,
        "source_output_peak_y_single_field_offset": 0x38,
        "source_summary_both_original_sqrt_calls_verified": True,
    }


def audit_private_getspectrum_summary_source(private_idp: str | Path) -> dict:
    base = audit_original_static_cw(private_idp)
    p = Path(private_idp)
    with p.open("rb") as f:
        sections = _sections(f, p.stat().st_size)
        windows = {}
        for key, (start, stop, digest) in SOURCE_WINDOWS.items():
            data = _read_at_va(f, sections, start, stop-start, ".text")
            _verify_hash(data, start, stop, digest)
            windows[key] = data
    return {
        "source": SOURCE,
        "original_source_code_windows_sha256_verified": len(SOURCE_WINDOWS),
        "original_static_fpu_cw_hex": base["original_static_fpu_cw_hex"],
        "source_pre_summary_breakpoint_hex": f"0x{PRE_SUMMARY_BREAKPOINT:08X}",
        "source_post_summary_breakpoint_hex": f"0x{POST_SUMMARY_BREAKPOINT:08X}",
        **_source_summary_structure(windows),
        "original_runtime_triplet_observed": False,
        "original_Delphi_x87_triplet_bitwise_parity_verified": False,
        "private_original_bytes_or_paths_in_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Read-only private original MVKView summary x87 source audit")
    p.add_argument("private_idp", help="Local original IDR v3 (never upload)")
    args = p.parse_args(argv)
    try:
        report = audit_private_getspectrum_summary_source(args.private_idp)
    except (OSError, ValueError, TypeError, struct.error):
        p.exit(2, "Original GetSpectrum source cannot be authenticated; details withheld\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
