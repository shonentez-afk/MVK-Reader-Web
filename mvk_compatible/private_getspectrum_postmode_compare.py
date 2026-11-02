"""Stage111Z30A: PRIVATE, read-only original GetSpectrum post-mode verification.

Compare an operator-captured FFT power array at 007D154B (before low-bin
zeroing / mode integration) to an array from the SAME original GetSpectrum
invocation at 007D17E7 (after integration, before summary). This isolates
mode 0/1/2/3 power processing from already-validated FFT stage Z8.

All captures remain local. No device access, network, file modification,
parameter fitting, automatic gain, or synthetic replacement of real goldens.
Operator provenance statements are never independently authenticated here.
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

from .core.envelope_spectrum_idr_candidate import _delphi_integration_power
from .core.spectrum_metrics_idr_candidate import original_spectrum_summary
from .private_getspectrum_power_compare import _comparison
from .private_getspectrum_summary_triplet_compare import _compare_single

SOURCE = "PRIVATE_ORIGINAL_GETSPECTRUM_POSTMODE_V1"
SCHEMA = "MVKVIEW_ORIGINAL_POSTMODE_CAPTURE_V1"
BEFORE_STOP_VA = "0x007D154B"
AFTER_STOP_VA = "0x007D17E7"
SUMMARY_STOP_VA = "0x007D1900"
_BASE_FIELDS = frozenset({
    "schema", "fft_n", "output_sample_rate_hz", "spectrum_mode",
    "channel_index_zero_based", "envelope_code", "f_range_bits",
    "before_stop_va", "after_stop_va", "same_invocation_operator_confirmed",
    "before_power_file", "after_mode_file",
    "before_power_sha256", "after_mode_sha256",
})
_SUMMARY_FIELDS = frozenset({
    "summary_stop_va", "output_mean_bits", "output_peak_x_bits",
    "output_peak_y_bits",
})
_SAFE_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.bin\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_BITS = re.compile(r"0x[0-9A-Fa-f]{8}\Z")
_OUTPUTS = {
    "output_mean": "output_mean_bits",
    "output_peak_x_bin": "output_peak_x_bits",
    "output_peak_y": "output_peak_y_bits",
}


def _int_field(value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("Invalid operator capture integer metadata")
    return value


def _float32_bits(value: object) -> int:
    if not isinstance(value, str) or _BITS.fullmatch(value) is None:
        raise ValueError("Invalid captured Float32 hexadecimal word")
    bits = int(value, 16)
    number = struct.unpack("<f", struct.pack("<I", bits))[0]
    if not math.isfinite(number) or number < 0 or bits & 0x80000000:
        raise ValueError("Captured Float32 must be finite and nonnegative")
    return bits


def _read_float32(folder: Path, filename: object, expected_hash: object,
                  count: int) -> tuple[np.ndarray, str]:
    if (not isinstance(filename, str) or _SAFE_FILE.fullmatch(filename) is None
        or ".." in filename or "/" in filename or "\\" in filename
        or not isinstance(expected_hash, str)
        or _SHA256.fullmatch(expected_hash) is None):
        raise ValueError("Unsafe original capture filename or SHA256")
    p = folder / filename
    if p.is_symlink() or not p.is_file() or p.stat().st_size != count * 4:
        raise ValueError("Original Float32 capture dimensions/type differ")
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != count * 4 or digest != expected_hash:
        raise ValueError("Original Float32 capture SHA256 differs")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if not bool(np.isfinite(values).all()) or bool(np.signbit(values).any()):
        raise ValueError("Original spectrum powers must be finite nonnegative Float32")
    return values, digest


def compare_original_postmode_capture(manifest: str | Path) -> dict:
    """Never return an original sample, file path, screenshot or captured word."""
    path = Path(manifest)
    if (path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json"
        or not 2 <= path.stat().st_size <= 8192):
        raise ValueError("Invalid private original post-mode manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid private original capture structure")
    fields = set(payload)
    if fields not in (_BASE_FIELDS, _BASE_FIELDS | _SUMMARY_FIELDS):
        raise ValueError("Incomplete or unexpected original capture fields")
    has_summary = fields == _BASE_FIELDS | _SUMMARY_FIELDS
    if (payload["schema"] != SCHEMA
        or payload["before_stop_va"] != BEFORE_STOP_VA
        or payload["after_stop_va"] != AFTER_STOP_VA
        or payload["same_invocation_operator_confirmed"] is not True
        or (has_summary and payload["summary_stop_va"] != SUMMARY_STOP_VA)):
        raise ValueError("Original breakpoint/provenance claim mismatch")
    n = _int_field(payload["fft_n"], 1024, 262144)
    if n & (n - 1):
        raise ValueError("Original FFT N must be a power of two")
    fs = _int_field(payload["output_sample_rate_hz"], 1, 100000000)
    mode = _int_field(payload["spectrum_mode"], 0, 3)
    _int_field(payload["channel_index_zero_based"], 0, 7)
    _int_field(payload["envelope_code"], 0, 31)
    f_range_bits = _float32_bits(payload["f_range_bits"])
    f_range = struct.unpack("<f", struct.pack("<I", f_range_bits))[0]
    if f_range <= 0:
        raise ValueError("Original FRange must be positive")
    if payload["before_power_file"] == payload["after_mode_file"]:
        raise ValueError("Pre-mode and post-mode checkpoints need distinct files")
    low = max(2, round(n / (2.0 * fs)))
    if low >= n // 2:
        raise ValueError("Source lower cutoff exceeds original FFT power range")

    before, before_sha = _read_float32(
        path.parent, payload["before_power_file"],
        payload["before_power_sha256"], n // 2)
    actual, after_sha = _read_float32(
        path.parent, payload["after_mode_file"],
        payload["after_mode_sha256"], n // 2)
    if not bool(np.any(before[low:] > 0)) or not bool(np.any(actual[low:] > 0)):
        raise ValueError("Uninformative zero original capture; parity cannot be tested")
    predicted = before.copy()
    predicted[:low] = np.float32(0.0)
    if mode in (2, 3):
        predicted = _delphi_integration_power(predicted, n, fs, mode - 1)
    comparison = _comparison(actual, predicted)
    reference_summary = None
    predicted_summary = None
    if has_summary:
        reference_summary = original_spectrum_summary(
            actual, n_fft=n, fs_out=float(fs), f_range=float(f_range),
            spectrum_mode=mode)
        predicted_summary = original_spectrum_summary(
            predicted, n_fft=n, fs_out=float(fs), f_range=float(f_range),
            spectrum_mode=mode)
        reference_summary = {
            key: _compare_single(
                _float32_bits(payload[word]), reference_summary[key])
            for key, word in _OUTPUTS.items()
        }
        predicted_summary = {
            key: _compare_single(
                _float32_bits(payload[word]), predicted_summary[key])
            for key, word in _OUTPUTS.items()
        }
    return {
        "source": SOURCE,
        "schema": SCHEMA,
        "mode": mode,
        "fft_n": n,
        "low_bins_zeroed": low,
        "power_integration_passes": max(0, mode - 1),
        "original_pre_mode_sha256": before_sha,
        "original_post_mode_sha256": after_sha,
        "post_mode_power_comparison": comparison,
        "post_mode_power_bitwise_equal": (
            comparison["float32_bitwise_unequal_count"] == 0),
        "original_summary_triplet_captured": has_summary,
        "original_summary_from_original_postmode_differences": reference_summary,
        "original_summary_from_reconstructed_postmode_differences": predicted_summary,
        "all_summary_words_bitwise_equal_to_original_postmode_candidate": (
            None if reference_summary is None else all(
                d["float32_bitwise_equal"] for d in reference_summary.values())),
        "all_summary_words_bitwise_equal_to_reconstructed_candidate": (
            None if predicted_summary is None else all(
                d["float32_bitwise_equal"] for d in predicted_summary.values())),
        "operator_same_original_invocation_claimed": True,
        "same_original_invocation_independently_authenticated": False,
        "original_ADC_FRange_window_independently_authenticated": False,
        "full_four_mode_parity_certified": False,
        "display_log_XScale_TQGrapher_covered": False,
        "private_sample_bytes_paths_or_capture_bits_in_report": False,
        "warning": (
            "Read-only source-derived mode-power/summary diagnostics only; "
            "cannot authenticate original Win32 invocation, FFT input, UI or "
            "all four mode paths without independent same-run evidence."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Private original GetSpectrum post-mode power and 3-float comparison")
    parser.add_argument("manifest", help="Local JSON next to original Float32 dumps")
    args = parser.parse_args(argv)
    try:
        report = compare_original_postmode_capture(args.manifest)
    except (OSError, ValueError, TypeError, OverflowError, struct.error):
        parser.exit(2, "Original private post-mode capture invalid; details withheld\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    summary_ok = report["all_summary_words_bitwise_equal_to_reconstructed_candidate"]
    return 0 if (report["post_mode_power_bitwise_equal"]
                 and summary_ok is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
