"""Stage111Z.7: private read-only GetSpectrum FFT capture breakpoint source audit.

Uses PRIVATE original IDR v3 only on operator's offline computer. The source
is never exported; the public module contains only SHA256 fingerprints,
machine-code address roles, generic short instruction shapes, and summary
facts. This is static control-flow evidence, NOT a runtime FFT signal.
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

SOURCE = "PRIVATE_MVKVIEW_GETSPECTRUM_FFT_CAPTURE_SOURCE_AUDIT_V1"
CODE_WINDOWS = {
    "prepared_input_path": (0x007D1472, 0x007D14B8,
        "c0c0f5c88ac625d7a32555e5a27d5b6415218480caf08965344ca4595203967d"),
    "two_breakpoint_bridge": (0x007D1518, 0x007D1558,
        "fcacf538ee49b7a548498a04f4e0ed0446d1fa978242c8501f55ff10ca4ade66"),
    "power_loop": (0x007D2080, 0x007D20B6,
        "2eb7a8a5fc04215384684252290dc8dfc1fbe513a9a8e7382512ef19134b1c3b"),
    "spectrum_mode_branch": (0x007D15A5, 0x007D15E1,
        "0fed410a3864591c6e2e8052813fcb57b09f9364df4290b6b76ff758e11fd95f"),
}

PRE_BREAKPOINT = 0x007D153D
POST_BREAKPOINT = 0x007D154B


def _validate_window(data: bytes, start: int, end: int, digest: str) -> None:
    if (not isinstance(data, bytes) or end <= start or
            len(data) != end-start or hashlib.sha256(data).hexdigest() != digest):
        raise ValueError("Original GetSpectrum source differs from expected IDR")


def _call_target(data: bytes, base: int, site: int) -> int:
    offset = site-base
    if offset < 0 or offset+5 > len(data) or data[offset] != 0xE8:
        raise ValueError("Expected original relative-call instruction missing")
    return (site+5+struct.unpack_from("<i", data, offset+1)[0]) & 0xFFFFFFFF


def _structural_facts(blocks: dict[str, bytes]) -> dict:
    """Only structural properties backed by verified machine-instruction sites."""
    def require(window: str, va: int, instruction_hex: str) -> None:
        data = blocks[window]
        start = CODE_WINDOWS[window][0]
        expected = bytes.fromhex(instruction_hex)
        off = va-start
        if off < 0 or data[off:off+len(expected)] != expected:
            raise ValueError("Original GetSpectrum breakpoint structure changed")

    require("prepared_input_path", 0x007D1483, "89 45 D4")  # [ebp-2c] <- EAX
    require("prepared_input_path", 0x007D149F, "8B 55 D4")  # buffer as EDX
    require("prepared_input_path", 0x007D14B0, "8B 45 FC")  # channel storage

    input_code = blocks["prepared_input_path"]
    input_base = CODE_WINDOWS["prepared_input_path"][0]
    if (_call_target(input_code, input_base, 0x007D14A5) != 0x007D2228 or
            _call_target(input_code, input_base, 0x007D14B3) != 0x007D2344):
        raise ValueError("GetSignal or mean-centering source call differs")

    require("two_breakpoint_bridge", 0x007D1518, "8B 43 04")  # N
    require("two_breakpoint_bridge", PRE_BREAKPOINT, "8B 4B 04")
    require("two_breakpoint_bridge", 0x007D1540, "8B 55 D4")
    require("two_breakpoint_bridge", 0x007D1543, "8B 45 FC")
    bridge = blocks["two_breakpoint_bridge"]
    bridge_base = CODE_WINDOWS["two_breakpoint_bridge"][0]
    if _call_target(bridge, bridge_base, 0x007D1546) != 0x007D1FE8:
        raise ValueError("Original FFT calculation call differs")
    require("two_breakpoint_bridge", POST_BREAKPOINT, "8B 43 28")

    require("spectrum_mode_branch", 0x007D15BC, "8B 43 18")
    require("power_loop", 0x007D208B, "D1 EA")  # N/2
    require("power_loop", 0x007D209B, "D9 04 C1 D8 C8")
    require("power_loop", 0x007D20A6, "D9 44 C1 04 D8 C8")
    require("power_loop", 0x007D20AE, "D9 1C 83")  # FSTP power[k] as Single
    power = blocks["power_loop"]
    if _call_target(power, CODE_WINDOWS["power_loop"][0], 0x007D2083) != 0x007CC3F8:
        raise ValueError("Original spectrum no longer calls positive-angle FFT")
    return {
        "source_prepared_input_and_mean_centering_verified": True,
        "source_pre_breakpoint_buffer_is_EBP_minus_0x2C": True,
        "source_pre_breakpoint_length_is_params_FFT_N": True,
        "source_post_breakpoint_same_buffer_contains_first_N_over_2_powers": True,
        "source_power_is_before_mode_integration": True,
        "source_fft_calculation_uses_positive_angle_wrapper": True,
        "source_spectrum_mode_is_params_offset_0x18": True,
    }


def audit_original_getspectrum_capture_sites(private_idp: str | Path) -> dict:
    original = audit_original_static_cw(private_idp)
    p = Path(private_idp)
    with p.open("rb") as src:
        sections = _sections(src, p.stat().st_size)
        blocks = {}
        for name, (start, end, expected_sha) in CODE_WINDOWS.items():
            data = _read_at_va(src, sections, start, end-start, ".text")
            _validate_window(data, start, end, expected_sha)
            blocks[name] = data
    return {
        "source": SOURCE,
        "original_static_fpu_initial_cw_hex": original["original_static_fpu_cw_hex"],
        "original_source_code_windows_SHA256_verified": len(CODE_WINDOWS),
        "pre_breakpoint_address_hex": f"0x{PRE_BREAKPOINT:08X}",
        "post_breakpoint_address_hex": f"0x{POST_BREAKPOINT:08X}",
        **_structural_facts(blocks),
        "operator_original_runtime_powers_already_captured": False,
        "original_Delphi_FFT_numeric_parity_certified": False,
        "private_original_code_bytes_or_paths_in_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local MVKView FFT capture source audit")
    parser.add_argument("private_idp", help="Local PRIVATE original IDR v3 file")
    args = parser.parse_args(argv)
    try:
        result = audit_original_getspectrum_capture_sites(args.private_idp)
    except (OSError, ValueError, TypeError, struct.error):
        parser.exit(2, "Private GetSpectrum source cannot be authenticated; details withheld\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
