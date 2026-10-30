"""Stage111Z.8: private two-file original GetSpectrum capture preflight.

This diagnostic is local-only and read-only. It accepts before_fft.bin with
N Float32 entries and after_power.bin with N/2 Float32 powers (little-endian),
NO manifest needed. It rejects bad sizes, symlinks, NaNs and negative powers,
and diagnoses degenerate input/output without claiming numerical FFT parity.

No raw samples, per-bin data, hashes, filenames, or source paths are printed.
An all-zero pair is NOT a meaningful golden reference for FFT correctness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np

SOURCE = "PRIVATE_ORIGINAL_GETSPECTRUM_FFT_CAPTURE_PREFLIGHT_V1"
MAX_N = 262144
MIN_N = 1024


def _quality(before: np.ndarray, after: np.ndarray) -> dict:
    """Analyze two validated Float32 arrays, without disclosing values."""
    if (before.ndim != 1 or after.ndim != 1 or
            len(before) < MIN_N or len(before) > MAX_N or
            len(before) & (len(before) - 1) or len(after) * 2 != len(before)):
        raise ValueError("Invalid original FFT pair shape")
    if (not bool(np.isfinite(before).all()) or
            not bool(np.isfinite(after).all()) or
            bool(np.signbit(after).any())):
        raise ValueError("Original FFT pair contains invalid Float32 values")
    n_before = int(np.count_nonzero(before))
    n_after = int(np.count_nonzero(after))
    if not n_before and not n_after:
        status = "EMPTY_INPUT_AND_POWER"
    elif not n_before:
        status = "ZERO_INPUT_WITH_NONZERO_POWER_INCONSISTENT"
    elif not n_after:
        status = "NONZERO_INPUT_WITH_ZERO_POWER_UNINFORMATIVE"
    else:
        status = "NONZERO_INPUT_AND_POWER"
    return {
        "source": SOURCE,
        "fft_n_inferred_from_byte_sizes": int(before.size),
        "input_float32_count": int(before.size),
        "power_float32_count": int(after.size),
        "input_nonzero_count": n_before,
        "power_nonzero_count": n_after,
        "capture_status": status,
        "capture_informative_for_fft_numeric_parity": bool(n_before and n_after),
        "original_capture_same_invocation_authenticated": False,
        "original_delphi_fft_bitwise_parity_verified": False,
        "private_source_bytes_paths_or_values_in_report": False,
    }


def _read_local_file(path: str | Path, expected_bytes: int) -> np.ndarray:
    p = Path(path)
    if (p.is_symlink() or not p.is_file() or
            p.suffix.lower() != ".bin" or p.stat().st_size != expected_bytes):
        raise ValueError("Invalid private FFT dump file or size")
    return np.fromfile(p, dtype="<f4")


def inspect_fft_capture_pair(before_file: str | Path,
                             after_file: str | Path) -> dict:
    """Infer FFT N only from exact binary lengths, not unverified metadata."""
    first, second = Path(before_file), Path(after_file)
    if (first == second or first.is_symlink() or second.is_symlink() or
            not first.is_file() or not second.is_file()):
        raise ValueError("Both private FFT capture files are required")
    before_bytes = first.stat().st_size
    after_bytes = second.stat().st_size
    if (before_bytes < MIN_N * 4 or before_bytes > MAX_N * 4 or
            before_bytes % 4 or after_bytes != before_bytes // 2):
        raise ValueError("Original capture files have invalid FFT lengths")
    before = _read_local_file(first, before_bytes)
    after = _read_local_file(second, after_bytes)
    return _quality(before, after)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Read-only original MVKView FFT memory capture preflight"
    )
    p.add_argument("before_fft_bin", help="Local private pre-FFT Float32 dump")
    p.add_argument("after_power_bin", help="Local private post-FFT powers")
    args = p.parse_args(argv)
    try:
        report = inspect_fft_capture_pair(args.before_fft_bin, args.after_power_bin)
    except (OSError, ValueError, TypeError, OverflowError):
        p.exit(2, "Original FFT capture invalid; private details withheld\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
