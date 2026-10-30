"""Stage111Z.8: local original MVKView raw FFT binary pair comparison.

Run with ONLY two operator-saved Float32 files; no manifest, sample rate,
mode, channel or FRange are guessed or invented. All numerical comparisons
use the ACTUAL prepared pre-FFT array without a second mean subtraction.
Original Windows process capture provenance is operator-reported, not
authenticated by this program.

Input files are read-only and NEVER sent to GitHub/CI or the network.
Output contains only aggregate error statistics, never individual bins,
sample values, filenames, filesystem paths or original raw bytes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .core.fft_idr_candidate import idr_power_spectrum
from .private_getspectrum_capture_preflight import (
    inspect_fft_capture_pair, _read_local_file,
)
from .private_getspectrum_power_compare import _comparison

SOURCE = "OPERATOR_SUPPLIED_ORIGINAL_GETSPECTRUM_RAW_PAIR_COMPARE_V1"


def compare_original_fft_raw_pair(
    before_file: str | Path, after_file: str | Path
) -> dict:
    """Compare source-derived float32 FFT and independent NumPy FFT.

    A nonzero result allows a numeric comparison. It does NOT certify that
    two user-supplied files came from the same original Delphi invocation.
    """
    quality = inspect_fft_capture_pair(before_file, after_file)
    n = quality["fft_n_inferred_from_byte_sizes"]
    result = {
        "source": SOURCE,
        "fft_n": n,
        "capture_quality": quality,
        "input_original_provenance_authenticated": False,
        "same_original_GetSpectrum_invocation_authenticated": False,
        "original_Delphi_FFT_complete_parity_accepted": False,
        "original_hann_table_fully_authenticated": False,
        "input_recentered_or_calibrated_by_comparator": False,
        "capture_sample_rate_hz_or_mode_inferred": False,
        "private_source_bytes_paths_or_values_in_report": False,
        "fft_numeric_comparison_performed": quality[
            "capture_informative_for_fft_numeric_parity"
        ],
        "comparisons": {},
    }
    if not quality["capture_informative_for_fft_numeric_parity"]:
        return result
    before = _read_local_file(before_file, n * 4)
    after = _read_local_file(after_file, (n // 2) * 4)
    # _read_local_file checks names/length; preflight checks finite/positive.
    if (before.size != n or after.size != n // 2 or
            not bool(np.isfinite(before).all()) or
            not bool(np.isfinite(after).all()) or
            bool(np.signbit(after).any())):
        raise ValueError("Private original FFT capture changed during comparison")
    for backend, name in (
        ("idr_float32", "source_derived_float32_fft"),
        ("numpy", "numpy_float64_fft_cast_to_single"),
    ):
        candidate, mean_removed = idr_power_spectrum(
            before, backend=backend, remove_dc=False
        )
        if mean_removed != 0.0:
            raise ValueError("Original FFT input was unexpectedly mean-centered twice")
        result["comparisons"][name] = _comparison(after, candidate)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline two-file original GetSpectrum Float32 FFT comparison"
    )
    parser.add_argument("before_fft_bin", help="Operator's private pre-FFT dump")
    parser.add_argument("after_power_bin", help="Operator's private post-FFT power dump")
    args = parser.parse_args(argv)
    try:
        report = compare_original_fft_raw_pair(
            args.before_fft_bin, args.after_power_bin
        )
    except (OSError, ValueError, TypeError, OverflowError, FloatingPointError):
        parser.exit(2, "Private original FFT capture cannot be compared; details withheld\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
