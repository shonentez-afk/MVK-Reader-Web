"""Stage111Z.11: PRIVATE original spectrum Copy-text comparison from raw Single.

This avoids rereading/recalculating the private archive. It uses ONLY three
operator-reported original summary DWORDs, N and Fs from Stage111Z.10,
compared with a separate one-line TAB clipboard capture from the ORIGINAL
running Windows MVKView. The 007B2090 formatting remains a CANDIDATE until
the operator supplies a real clipboard text reference.

Never uploads source text, measurement arrays or filenames to GitHub/CI.
Output has SHA256 of private clipboard and boolean per-field text matches,
NOT the original clipboard or predicted values. This is local-only and
read-only; no device or network.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .core.spectrum_summary_export_candidate import spectrum_triplet_text
from .private_getspectrum_summary_triplet_compare import (
    SCHEMA, _FIELDS, _parse_bits,
)
from .triplet_reference_compare import read_operator_triplet_file

SOURCE = "OPERATOR_ORIGINAL_SPECTRUM_COPY_TEXT_CHECK_V1"


def compare_original_copy_text(
    summary_manifest: str | Path, original_clipboard_txt: str | Path,
    *, decimal_separator: str = ",", encoding: str = "utf-8-sig",
) -> dict:
    """Compare 007B2090 candidate formatting with original 3-column TAB."""
    manifest = Path(summary_manifest)
    if (manifest.is_symlink() or not manifest.is_file() or
            manifest.suffix.lower() != ".json" or
            not 2 <= manifest.stat().st_size <= 8192):
        raise ValueError("Invalid original summary manifest")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or set(payload) != _FIELDS or
            payload.get("schema") != SCHEMA or
            payload.get("summary_power_stop_va") != "0x007D17E7" or
            payload.get("summary_fields_stop_va") != "0x007D1900"):
        raise ValueError("Unexpected summary checkpoint manifest schema")
    n, fs, mode = (
        payload.get("fft_n"), payload.get("sample_rate_hz"),
        payload.get("spectrum_mode")
    )
    if (type(n) is not int or not 1024 <= n <= 262144 or n & (n - 1) or
            type(fs) is not int or not 1 <= fs <= 100000000 or
            type(mode) is not int or mode not in (0, 1, 2, 3)):
        raise ValueError("Invalid original copy parameters")
    _range_bits, f_range = _parse_bits(payload.get("f_range_bits"), "f_range_bits")
    if f_range <= 0:
        raise ValueError("Invalid original FRange")
    _, mean = _parse_bits(payload.get("output_mean_bits"), "output_mean_bits")
    _, peak_x = _parse_bits(payload.get("output_peak_x_bits"), "output_peak_x_bits")
    _, peak_y = _parse_bits(payload.get("output_peak_y_bits"), "output_peak_y_bits")
    # Original graph XScale=Fs/N Single. The candidate explicitly rounds
    # the product to Single; RTL FormatFloat parity is NOT yet established.
    df = np.float32(float(fs) / float(n))
    frequency = float(np.float32(float(peak_x) * float(df)))
    if not math.isfinite(frequency):
        raise ValueError("Invalid original peak frequency")
    summary = {
        "source": "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
        "output_mean": mean,
        "output_peak_frequency_hz": frequency,
        "output_peak_y": peak_y,
    }
    candidate = spectrum_triplet_text(
        summary, separator="\t", decimal_separator=decimal_separator
    )
    original = read_operator_triplet_file(
        Path(original_clipboard_txt), separator="\t",
        decimal_separator=decimal_separator, encoding=encoding,
    )
    candidate_fields = candidate.split("\t")
    observed_fields = original["original_text_local_only"].split("\t")
    if len(candidate_fields) != 3 or len(observed_fields) != 3:
        raise ValueError("Invalid candidate/original clipboard field count")
    per_field = {
        name: candidate_fields[i] == observed_fields[i]
        for i, name in enumerate(("mean_text", "peak_frequency_text", "peak_y_text"))
    }
    return {
        "source": SOURCE,
        "operator_reference_sha256": original["sha256"],
        "operator_original_triplet_uses_tab": True,
        "operator_original_decimal_separator_explicit": decimal_separator,
        "candidate_built_only_from_original_single_words": True,
        "candidate_x_scale_is_source_derived_not_runtime_attested": True,
        "candidate_delphi_formatfloat_rtl_verified": False,
        "same_original_window_clipboard_and_summary_authenticated": False,
        "all_three_fields_text_equal": all(per_field.values()),
        "field_text_equal": per_field,
        "private_original_text_or_numeric_values_exposed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Private original MVKView three-field Copy text regression")
    parser.add_argument("--summary-manifest", required=True)
    parser.add_argument("--reference", required=True, help="Local original Copy text")
    parser.add_argument("--decimal", choices=(".", ","), default=",")
    parser.add_argument("--encoding", choices=("utf-8-sig", "cp1251"), default="utf-8-sig")
    args = parser.parse_args(argv)
    try:
        result = compare_original_copy_text(
            args.summary_manifest, args.reference,
            decimal_separator=args.decimal, encoding=args.encoding,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        parser.exit(2, "Private original Copy-text reference invalid; content withheld\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result["all_three_fields_text_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
