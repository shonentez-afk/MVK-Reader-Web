"""Stage111Z.9: offline original GetSpectrum OutputMean / PeakX / PeakY oracle.

Private operator input is ONE post-mode, pre-summary Float32 power buffer
captured at original x32dbg 007D17E7, plus the 3 output Single HEX words
read at 007D1900 from the SAME GetSpectrum invocation. Mode 2/3 modifies
powers BEFORE the summary; a raw 007D154B power dump is NOT interchangeable.

This tool NEVER launches Delphi, accesses a device/network or stores private
samples in GitHub. It emits only aggregate ULP / relative differences and
cannot independently verify that files/metadata came from the same process.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .core.spectrum_metrics_idr_candidate import original_spectrum_summary

SOURCE = "OPERATOR_SUPPLIED_GETSPECTRUM_SUMMARY_3SINGLE_COMPARISON"
SCHEMA = "MVKVIEW_ORIGINAL_GETSPECTRUM_SUMMARY_V1"
_FIELDS = frozenset({
    "schema", "summary_power_stop_va", "summary_fields_stop_va",
    "fft_n", "sample_rate_hz", "spectrum_mode", "f_range_bits",
    "summary_power_file", "output_mean_bits", "output_peak_x_bits",
    "output_peak_y_bits",
})
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.bin\Z")
_BITS = re.compile(r"0x[0-9A-Fa-f]{8}\Z")
_OUTPUTS = {
    "output_mean": "output_mean_bits",
    "output_peak_x_bin": "output_peak_x_bits",
    "output_peak_y": "output_peak_y_bits",
}


def _parse_bits(value: object, name: str) -> tuple[int, float]:
    if not isinstance(value, str) or _BITS.fullmatch(value) is None:
        raise ValueError("Invalid original Float32 bit field: " + name)
    bits = int(value, 16)
    number = struct.unpack("<f", struct.pack("<I", bits))[0]
    if not math.isfinite(number) or number < 0:
        raise ValueError("Original field must be finite nonnegative Single: " + name)
    return bits, number


def _float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def _compare_single(original_bits: int, candidate: float) -> dict:
    candidate_bits = _float32_bits(candidate)
    if (original_bits & 0x80000000) or (candidate_bits & 0x80000000):
        raise ValueError("Expected nonnegative summary field for comparison")
    original_float = struct.unpack(
        "<f", struct.pack("<I", original_bits))[0]
    delta = abs(float(np.float32(candidate)) - original_float)
    denom = max(
        abs(original_float), abs(float(candidate)),
        float(np.finfo(np.float32).tiny),
    )
    return {
        "float32_bitwise_equal": bool(candidate_bits == original_bits),
        "float32_ulp_distance": abs(candidate_bits - original_bits),
        "absolute_difference": delta,
        "relative_difference": delta / denom,
    }


def compare_original_summary_triplet(manifest_file: str | Path) -> dict:
    path = Path(manifest_file)
    if (path.is_symlink() or not path.is_file() or
            path.suffix.lower() != ".json" or
            not 2 <= path.stat().st_size <= 8192):
        raise ValueError("Original summary manifest is invalid")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or set(payload) != _FIELDS or
            payload["schema"] != SCHEMA):
        raise ValueError("Original summary manifest schema differs")
    if (payload["summary_power_stop_va"] != "0x007D17E7" or
            payload["summary_fields_stop_va"] != "0x007D1900"):
        raise ValueError("Original summary breakpoint pair mismatch")
    n = payload["fft_n"]
    fs = payload["sample_rate_hz"]
    mode = payload["spectrum_mode"]
    if (type(n) is not int or n < 1024 or n > 262144 or
            n & (n-1) or type(fs) is not int or
            not 1 <= fs <= 100000000 or
            type(mode) is not int or mode not in (0,1,2,3)):
        raise ValueError("Original summary N, Fs or mode invalid")
    _, f_range = _parse_bits(payload["f_range_bits"], "f_range_bits")
    if f_range <= 0.0:
        raise ValueError("Original FRange must be positive")
    original_values = {}
    for output, field in _OUTPUTS.items():
        original_values[output] = _parse_bits(payload[field], field)[0]

    filename = payload["summary_power_file"]
    if (not isinstance(filename, str) or
            _SAFE_NAME.fullmatch(filename) is None or ".." in filename):
        raise ValueError("Original power capture filename unsafe")
    src = path.parent / filename
    if (src.is_symlink() or not src.is_file() or
            src.stat().st_size != (n // 2) * 4):
        raise ValueError("Original summary power capture dimensions invalid")
    power = np.fromfile(src, dtype="<f4")
    if (power.size != n // 2 or
            not bool(np.isfinite(power).all()) or
            bool(np.signbit(power).any()) or
            not bool(np.any(power > 0.0))):
        raise ValueError("Original summary power not finite or informative")
    # This is already post mode-specific integration and low-bin clipping.
    # NEVER apply another FFT, mode integration, or FRange to the raw powers.
    candidate = original_spectrum_summary(
        power, n_fft=n, fs_out=float(fs), f_range=float(f_range),
        spectrum_mode=mode,
    )
    comparisons = {
        name: _compare_single(original_values[name], candidate[name])
        for name in _OUTPUTS
    }
    return {
        "source": SOURCE,
        "schema": SCHEMA,
        "fft_n": n,
        "mode_operator_supplied": mode,
        "power_capture_is_after_mode_processing_by_requested_breakpoint": True,
        "same_original_GetSpectrum_invocation_authenticated": False,
        "operator_capture_source_authenticated": False,
        "original_delphi_summary_bitwise_parity_accepted": False,
        "original_summary_fields_and_metadata_in_report": False,
        "all_three_float32_bits_equal": all(
            field["float32_bitwise_equal"] for field in comparisons.values()
        ),
        "field_differences": comparisons,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Private original 3-field GetSpectrum runtime compare")
    p.add_argument("manifest", help="Local JSON and post-mode summary power .bin")
    args = p.parse_args(argv)
    try:
        report = compare_original_summary_triplet(args.manifest)
    except (OSError, ValueError, OverflowError, TypeError, struct.error):
        p.exit(2, "Original spectrum triplet capture invalid; private details withheld\n")
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
