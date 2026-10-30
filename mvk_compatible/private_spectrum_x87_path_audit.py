"""Stage111Z.3: read-only audit of original PRIVATE spectrum x87 control flow.

The private IDP never leaves the operator's computer. Only verified structural
facts and aggregate callsite counts are emitted, never code bytes, measurements,
filenames or source paths. This is a static-code attestation; it cannot certify
Delphi runtime FPU status, border outcomes, FFT, Qt Canvas or calibration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from .private_original_cw_idr_audit import (
    _sections, _read_at_va, audit_original_static_cw,
)

SOURCE = "PRIVATE_MVKVIEW_IDR_SPECTRUM_X87_PATH_AUDIT_V1"

# SHA256 of code image windows in the already privately verified original IDP.
# The code/IDP itself and all original Delphi sources are NOT included.
SOURCE_WINDOWS = {
    "spectrum": (0x0084B5D3, 0x0084B882,
                 "06cd6b198b0c4213937f4c228cc35c536adfc6b3d0d39ece713bce6a474cf58d"),
    "log10_single": (0x00447DB8, 0x00447DC7,
                     "66cdc62b6f8a18e3cde573684f60252e6cad21762398f54f962ae6795251cebd"),
    "power_extended": (0x00447DF0, 0x00447E72,
                       "0875357af1363946f15a0fa352da9c97425b4331295a7a3c5a0398f0736f2713"),
    "power_single": (0x00447EF8, 0x00447F7A,
                     "df942d2359da176de596055a48dc5edeb01f8f0c4d21e3003398cc6477f62854"),
}

EXPECTED_HELPER_COUNTS = {
    0x00447DB8: 16,  # single-argument x87 FLDLG2/FYL2X log10
    0x00407C74: 7,   # integer TRUNC
    0x00447DF0: 4,  # extended-precision power helper
    0x00447EF8: 2,  # single-precision power helper
}

def _verify_window(window: bytes, start: int, stop: int, expected_sha256: str) -> None:
    """Generic digest check; synthetic tests can provide their own digest."""
    if (stop <= start or len(window) != stop - start or
            hashlib.sha256(window).hexdigest() != expected_sha256):
        raise ValueError("Original code image segment is not the verified baseline")


def _direct_target_counts(raw: bytes, start_va: int, targets: tuple[int, ...]) -> dict[int, int]:
    """E8 rel32 candidates in already verified code; not a general disassembler."""
    count: Counter[int] = Counter()
    allowed = set(targets)
    for i in range(max(0, len(raw) - 4)):
        if raw[i] == 0xE8:
            displacement = struct.unpack_from("<i", raw, i + 1)[0]
            destination = (start_va + i + 5 + displacement) & 0xFFFFFFFF
            if destination in allowed:
                count[destination] += 1
    return {target: count[target] for target in targets}


def audit_original_spectrum_x87_path(path: str | Path) -> dict:
    """Source-verified structure only; no live original execution or file export."""
    baseline = audit_original_static_cw(path)
    location = Path(path)
    with location.open("rb") as src:
        sections = _sections(src, location.stat().st_size)
        blocks = {}
        for name, (start, stop, expected_digest) in SOURCE_WINDOWS.items():
            data = _read_at_va(src, sections, start, stop - start, ".text") if stop - start <= 128 else None
            if data is None:
                # _read_at_va intentionally limits reads to 128 B. Read longer
                # chunks with explicit section ownership and bounds checks.
                sec = next((s for s in sections if s.name == ".text" and
                            s.va <= start and stop <= s.va + s.size), None)
                if sec is None:
                    raise ValueError("Original source range outside verified text segment")
                src.seek(sec.raw_offset + start - sec.va)
                data = src.read(stop - start)
            _verify_window(data, start, stop, expected_digest)
            blocks[name] = data
        raw = blocks["spectrum"]
        counts = _direct_target_counts(
            raw, SOURCE_WINDOWS["spectrum"][0],
            tuple(EXPECTED_HELPER_COUNTS),
        )
        if counts != EXPECTED_HELPER_COUNTS:
            raise ValueError("Unexpected spectrum x87/TRUNC helper callsites")
        # Original uses FSTP Single for two source mode multipliers and
        # six final branches. Do not infer the actual live numeric result.
        store_opcode = bytes.fromhex("D99E2C060000")
        if raw.count(store_opcode) != 8 or bytes.fromhex("D95DF8") not in raw:
            raise ValueError("Required original Single stores not present")
        factor10 = struct.unpack("<f", _read_at_va(
            src, sections, 0x0084BBCC, 4, ".text"))[0]
        factor100 = struct.unpack("<f", _read_at_va(
            src, sections, 0x0084BBD0, 4, ".text"))[0]
        if (factor10, factor100) != (10.0, 100.0):
            raise ValueError("Original source spectrum mode factors differ")
    return {
        "source": SOURCE,
        "source_handler_and_three_helpers_sha256_verified": True,
        "source_selected_channel_frange_read_verified": True,
        "source_tag_0_1_2_3_multipliers": [1, 1, 10, 100],
        "source_single_log10_callsite_count": counts[0x00447DB8],
        "source_trunc_callsite_count": counts[0x00407C74],
        "source_power_extended_callsite_count": counts[0x00447DF0],
        "source_power_single_callsite_count": counts[0x00447EF8],
        "source_single_intermediate_fraction_and_final_stores_verified": True,
        "original_static_initial_cw_hex": baseline["original_static_fpu_cw_hex"],
        "original_runtime_x87_cw_for_all_modes_verified": False,
        "original_delphi_x87_border_outputs_verified": False,
        "original_fft_cursor_canvas_numerical_parity_verified": False,
        "private_source_bytes_or_paths_in_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local source spectrum x87 branch audit"
    )
    parser.add_argument("private_idp", help="Private original MVKView IDP (local only)")
    args = parser.parse_args(argv)
    try:
        result = audit_original_spectrum_x87_path(args.private_idp)
    except (OSError, ValueError, struct.error):
        parser.exit(2, "Private spectrum source cannot be authenticated; source withheld\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
