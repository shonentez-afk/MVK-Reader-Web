"""Stage111Z.7: OFFLINE original GetSpectrum FFT power pair comparator.

Read-only input: two operator-saved Float32 little-endian memory dumps taken
from ONE call in original 32-bit MVKView, immediately before (007D153D)
and immediately after (007D154B) internal FFT processing.

The first dump is ALREADY mean-centered and envelope-adjusted if requested.
Re-centering it would be a reconstruction error. The second dump is N/2
nonnegative Single spectral powers BEFORE mode integration or amplitude
conversion. No device connections, network, original EXE or IDP are used.

Only aggregate error metrics are emitted. Never print original values,
samples, bins, raw binary, private local filenames or complete paths.
This tool CANNOT authenticate that supplied dumps came from original Delphi.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .core.fft_idr_candidate import (
    idr_power_spectrum, idr_hann_rms, fft_idr_float32_real,
)

SOURCE = "OPERATOR_SUPPLIED_ORIGINAL_GETSPECTRUM_FFT_POWER_PAIR_COMPARISON"
SCHEMA = "MVKVIEW_ORIGINAL_FFT_POWER_PAIR_V1"
_BEFORE_VA = "0x007D153D"
_AFTER_VA = "0x007D154B"
_FIELDS = frozenset({
    "schema", "before_stop_va", "after_stop_va", "fft_n",
    "spectrum_mode", "envelope_code", "channel_index",
    "sample_rate_hz", "f_range_bits", "before_fft_file", "after_power_file",
})
_OPTIONAL_FIELDS = frozenset({"complex_fft_file"})
_SAFE_BIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.bin\Z")
_HEX32 = re.compile(r"0x[0-9A-Fa-f]{8}\Z")


def _integer(value: object, low: int, high: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError("Invalid private capture " + field)
    return value


def _local_dump(folder: Path, filename: object, expected_bytes: int) -> np.ndarray:
    if (not isinstance(filename, str) or
            _SAFE_BIN.fullmatch(filename) is None or "/" in filename or
            "\\" in filename or ".." in filename):
        raise ValueError("Invalid private dump filename")
    p = folder / filename
    if p.is_symlink() or not p.is_file() or p.stat().st_size != expected_bytes:
        raise ValueError("Invalid private dump size/type")
    data = np.fromfile(p, dtype="<f4")
    if data.size * 4 != expected_bytes or not bool(np.isfinite(data).all()):
        raise ValueError("Private dump must contain finite Float32 values")
    return data


def _ordered_signed_float32_bits(bits: np.ndarray) -> np.ndarray:
    """Order negative and positive finite Float32 bit patterns monotonically."""
    raw = bits.astype(np.uint32, copy=False)
    negative = (raw & np.uint32(0x80000000)) != 0
    ordered = np.where(negative, np.bitwise_not(raw),
                       np.bitwise_or(raw, np.uint32(0x80000000)))
    return ordered.astype(np.int64)


def _comparison(reference: np.ndarray, predicted: np.ndarray,
                *, signed: bool = False) -> dict:
    """Float32 bitwise distance, supporting signed FFT Re/Im when requested."""
    p = np.asarray(predicted, dtype="<f4")
    if (p.shape != reference.shape or not bool(np.isfinite(p).all()) or
            (not signed and bool((p < 0).any()))):
        raise ValueError("Reconstructed FFT values are invalid")
    original_bits = reference.view("<u4")
    predicted_bits = p.view("<u4")
    if signed:
        left_i = _ordered_signed_float32_bits(original_bits)
        right_i = _ordered_signed_float32_bits(predicted_bits)
    else:
        left_i = original_bits.astype(np.int64)
        right_i = predicted_bits.astype(np.int64)
    distance = np.abs(left_i - right_i)
    exact = int(np.count_nonzero(original_bits == predicted_bits))
    left = reference.astype(np.float64)
    right = p.astype(np.float64)
    rel = np.abs(left - right) / np.maximum(
        np.maximum(np.abs(left), np.abs(right)), np.finfo(np.float32).tiny
    )
    return {
        "bins": int(reference.size),
        "float32_bitwise_equal_count": exact,
        "float32_bitwise_unequal_count": int(reference.size - exact),
        "within_one_float32_ulp_count": int(np.count_nonzero(distance <= 1)),
        "max_float32_ulp_distance": int(np.max(distance)),
        "mean_float32_ulp_distance": float(np.mean(distance, dtype=np.float64)),
        "max_relative_bin_error": float(np.max(rel)),
    }


def compare_original_fft_power_pair(manifest_file: str | Path) -> dict:
    """Compare one operator-supplied pair, without returning source samples."""
    path = Path(manifest_file)
    if (path.is_symlink() or not path.is_file() or
            path.suffix.lower() != ".json" or
            not 2 <= path.stat().st_size <= 8192):
        raise ValueError("Invalid private capture manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or
            set(payload) not in (_FIELDS, _FIELDS | _OPTIONAL_FIELDS) or
            payload["schema"] != SCHEMA):
        raise ValueError("Unexpected private FFT capture manifest schema")
    if payload["before_stop_va"] != _BEFORE_VA or payload["after_stop_va"] != _AFTER_VA:
        raise ValueError("Original source breakpoint pair mismatch")
    n = _integer(payload["fft_n"], 1024, 262144, "fft_n")
    if n & (n - 1):
        raise ValueError("FFT size must be a power of two")
    _integer(payload["spectrum_mode"], 0, 3, "spectrum_mode")
    _integer(payload["envelope_code"], 0, 255, "envelope_code")
    _integer(payload["channel_index"], 0, 7, "channel_index")
    _integer(payload["sample_rate_hz"], 1, 100000000, "sample_rate_hz")
    bits = payload["f_range_bits"]
    if not isinstance(bits, str) or _HEX32.fullmatch(bits) is None:
        raise ValueError("Invalid original FRange Float32 bits")
    f_range = struct.unpack("<f", struct.pack("<I", int(bits, 16)))[0]
    if not math.isfinite(f_range) or f_range <= 0:
        raise ValueError("Original FRange must be finite positive Single")
    if payload["before_fft_file"] == payload["after_power_file"]:
        raise ValueError("Before and after dumps must be distinct files")

    before = _local_dump(path.parent, payload["before_fft_file"], n * 4)
    after = _local_dump(path.parent, payload["after_power_file"], (n // 2) * 4)
    if bool(np.signbit(after).any()):
        raise ValueError("Original squared spectrum must not have negative signs")
    evaluations = {}
    for backend, name in (("idr_float32", "source_derived_float32_fft"),
                          ("numpy", "numpy_float64_fft_cast_to_single")):
        # NEVER remove DC again: this is PREPARED original runtime input.
        candidate, removed = idr_power_spectrum(before, backend=backend, remove_dc=False)
        if removed != 0.0:
            raise ValueError("Unexpected secondary DC subtraction")
        evaluations[name] = _comparison(after, candidate)
    if "complex_fft_file" in payload:
        if payload["complex_fft_file"] in (
            payload["before_fft_file"], payload["after_power_file"]
        ):
            raise ValueError("Complex FFT dump must be a distinct file")
        # Optional inner checkpoint: GetSpectrum's call to FFT has returned,
        # but the Re/Im -> power loop has not yet executed (007D2088).
        original_complex = _local_dump(
            path.parent, payload["complex_fft_file"], n * 8
        )
        windowed = np.asarray(
            before.astype(np.float64) * idr_hann_rms(n).astype(np.float64),
            dtype=np.float32,
        )
        predicted_real, predicted_imag = fft_idr_float32_real(windowed)
        native = np.fft.fft(windowed.astype(np.float64)).conjugate()
        evaluations["optional_original_complex_fft"] = {
            "source_derived_real": _comparison(
                original_complex[0::2], predicted_real, signed=True),
            "source_derived_imag": _comparison(
                original_complex[1::2], predicted_imag, signed=True),
            "numpy_real_cast_to_single": _comparison(
                original_complex[0::2], native.real, signed=True),
            "numpy_imag_cast_to_single": _comparison(
                original_complex[1::2], native.imag, signed=True),
        }
    return {
        "source": SOURCE,
        "schema": SCHEMA,
        "operator_supplied_fft_n": n,
        "operator_supplied_before_after_same_original_invocation_authenticated": False,
        "operator_supplied_original_channel_frange_authenticated": False,
        "original_delphi_fft_bitwise_parity_accepted": False,
        "pre_fft_original_buffer_recentered_or_mutated": False,
        "source_original_fft_power_is_before_mode_integration": True,
        "optional_complex_fft_reference_compared": "complex_fft_file" in payload,
        "private_original_values_or_paths_in_report": False,
        "comparisons": evaluations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Private read-only original MVKView FFT pre/post power comparison"
    )
    parser.add_argument("manifest", help="Local JSON next to two original .bin dumps")
    args = parser.parse_args(argv)
    try:
        result = compare_original_fft_power_pair(args.manifest)
    except (OSError, ValueError, TypeError, OverflowError, struct.error):
        parser.exit(2, "Original private FFT capture invalid; raw details withheld\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
