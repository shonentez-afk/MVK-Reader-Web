"""Stage111Z30B: private same-call original GetSpectrum displayed Y array.

Original GetSpectrum has TWO distinct Float32 buffers at 007D17E7:
  [EBP-2C] full N/2 post-mode FFT powers, [EBP-30] full N/2 display Y.
Do not confuse graphical Y with power or use plotted/decimated points.
Captures and SHA are read only; no device/network access or raw data output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .core.spectrum_display_source import (
    source_derived_mode_display, display_source_provenance)
from .private_getspectrum_power_compare import _comparison

SOURCE = "PRIVATE_ORIGINAL_GETSPECTRUM_DISPLAY_Y_V1"
SCHEMA = "MVKVIEW_ORIGINAL_DISPLAY_Y_PAIR_V1"
_STOP = "0x007D17E7"
_FIELDS = frozenset({
    "schema", "fft_n", "output_sample_rate_hz", "spectrum_mode",
    "channel_index_zero_based", "envelope_code", "f_range_bits",
    "power_stop_va", "display_stop_va",
    "power_buffer_role", "display_buffer_role",
    "same_invocation_operator_confirmed",
    "post_mode_power_file", "display_y_file",
    "post_mode_power_sha256", "display_y_sha256",
})
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.bin\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_BITS = re.compile(r"0x[0-9A-Fa-f]{8}\Z")


def _integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid original GetSpectrum metadata integer")
    return value


def _read(path: Path, name: object, sha: object, count: int, *,
          nonnegative: bool) -> tuple[np.ndarray, str]:
    if (not isinstance(name, str) or _NAME.fullmatch(name) is None
        or ".." in name or "/" in name or "\\" in name
        or not isinstance(sha, str) or _SHA.fullmatch(sha) is None):
        raise ValueError("Private Float32 name or SHA is invalid")
    file = path / name
    if file.is_symlink() or not file.is_file() or file.stat().st_size != count*4:
        raise ValueError("Private Float32 file type/length invalid")
    raw = file.read_bytes()
    hash_value = hashlib.sha256(raw).hexdigest()
    if len(raw) != count*4 or hash_value != sha:
        raise ValueError("Private Float32 SHA changed")
    arr = np.frombuffer(raw, dtype="<f4").copy()
    if (not bool(np.isfinite(arr).all()) or
        (nonnegative and bool((arr < 0).any()))):
        raise ValueError("Original Float32 buffer has unsupported values")
    return arr, hash_value


def _old_display_float32(power: np.ndarray, mode: int,
                         n_fft: int, f_range: float) -> np.ndarray:
    """PRIOR archive display calculation, for diagnostic comparison ONLY."""
    p = np.asarray(power, dtype=np.float64)
    half = n_fft // 2
    if mode == 0:
        result = np.full(half, -180., dtype=np.float64)
        valid = p > 0
        result[valid] = 10.*(np.log10(p[valid]) - 2.*np.log10(half))
    else:
        result = np.sqrt(p/2.)*(f_range/half)
    return np.asarray(result, dtype="<f4")


def compare_original_display_y_pair(manifest_file: str | Path) -> dict:
    path = Path(manifest_file)
    if (path.is_symlink() or not path.is_file() or
        path.suffix.lower() != ".json" or
        not 2 <= path.stat().st_size <= 8192):
        raise ValueError("Invalid original GetSpectrum display manifest")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != _FIELDS or data["schema"] != SCHEMA:
        raise ValueError("Unexpected original GetSpectrum display manifest")
    if (data["power_stop_va"] != _STOP or data["display_stop_va"] != _STOP
        or data["power_buffer_role"] != "EBP-2C"
        or data["display_buffer_role"] != "EBP-30"
        or data["same_invocation_operator_confirmed"] is not True):
        raise ValueError("The original source checkpoint/buffer roles are inconsistent")
    n = _integer(data["fft_n"], 1024, 262144)
    if n & (n-1):
        raise ValueError("FFT N must be a power of two")
    fs = _integer(data["output_sample_rate_hz"], 1, 100000000)
    mode = _integer(data["spectrum_mode"], 0, 3)
    _integer(data["channel_index_zero_based"], 0, 7)
    _integer(data["envelope_code"], 0, 31)
    if not isinstance(data["f_range_bits"], str) or _BITS.fullmatch(data["f_range_bits"]) is None:
        raise ValueError("Original FRange bits invalid")
    fr = struct.unpack("<f", struct.pack("<I", int(data["f_range_bits"], 16)))[0]
    if not math.isfinite(fr) or fr <= 0:
        raise ValueError("Original FRange Single invalid")
    if data["post_mode_power_file"] == data["display_y_file"]:
        raise ValueError("Original power and display capture files must differ")
    powers, psha = _read(path.parent, data["post_mode_power_file"],
                          data["post_mode_power_sha256"], n//2, nonnegative=True)
    display, ysha = _read(path.parent, data["display_y_file"],
                          data["display_y_sha256"], n//2, nonnegative=mode!=0)
    if not bool(np.any(powers>0)) or not bool(np.any(display != 0)):
        raise ValueError("Uninformative original display capture")
    candidate = source_derived_mode_display(powers,n_fft=n,mode=mode,f_range=fr)
    prior_candidate = _old_display_float32(powers,mode,n,fr)
    current = _comparison(display,candidate,signed=True)
    prior = _comparison(display,prior_candidate,signed=True)
    return {
        "source": SOURCE, "schema": SCHEMA, "fft_n": n,
        "operator_mode": mode, "operator_sample_rate_hz": fs,
        "post_mode_power_sha256": psha, "display_y_sha256": ysha,
        "original_post_mode_power_and_display_same_checkpoint_claimed": True,
        "same_original_invocation_independently_authenticated": False,
        "source_derived_single_staging": current,
        "prior_double_staging_cast_single": prior,
        "source_derived_bitwise_equal_to_operator_capture": (
            current["float32_bitwise_unequal_count"] == 0),
        "source_derived_improves_bitwise_count": (
            current["float32_bitwise_equal_count"] >
            prior["float32_bitwise_equal_count"]),
        "candidate_auto_selected_or_gain_fitted": False,
        "full_original_window_FRange_provenance_authenticated": False,
        "original_full_four_mode_runtime_parity_certified": False,
        "source_evidence": display_source_provenance(),
        "original_private_filenames_data_paths_FRange_bits_in_report": False,
        "warning": ("Static source confirms log10 and Float32 intermediate stores, "
                    "but NumPy is not x87; genuine same-run Win32/plot parity remains open."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PRIVATE original GetSpectrum full Y display vs source model")
    parser.add_argument("manifest", help="Local manifest and Float32 buffers only")
    args = parser.parse_args(argv)
    try:
        report = compare_original_display_y_pair(args.manifest)
    except (OSError, ValueError, TypeError, OverflowError, struct.error):
        parser.exit(2,"Original display capture rejected; private details withheld\n")
    print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if report["source_derived_bitwise_equal_to_operator_capture"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
