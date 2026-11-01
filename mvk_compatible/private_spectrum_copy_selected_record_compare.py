"""Stage111Z.12: locally compare ONE original MVKView Copy click and its record.

At x32dbg 0084BC8C original EBX is the form; ESI points to the CURRENT
selected spectrum record, which is not necessarily the same buffer as a
previous GetSpectrum breakpoint. Copy reads [ESI+30/34/38] as Single and
multiplies the peak-bin by graph series XScale (nested from EBX+FF4).

Pass only these four original Single words and one original TAB clipboard
line from the SAME click. No archive, FFT rerun, guessed Fs/N or FRange.
Never print private words, paths or clipboard text; local read-only tool.
This compares a formatter candidate, NOT independently authenticated Delphi.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .core.spectrum_summary_export_candidate import spectrum_triplet_text
from .triplet_reference_compare import read_operator_triplet_file

SOURCE = "OPERATOR_ORIGINAL_MVKVIEW_COPY_SELECTED_RECORD_COMPARE_V1"
SCHEMA = "MVKVIEW_ORIGINAL_COPY_SAME_CLICK_V1"
_REQUIRED_FIELDS = frozenset({
    "schema", "copy_breakpoint_va", "output_mean_bits",
    "output_peak_x_bin_bits", "output_peak_y_bits",
    "graph_xscale_bits", "original_clipboard_file", "decimal_separator",
})
_HEX = re.compile(r"0x[0-9A-Fa-f]{8}\Z")
_SAFE_TXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.txt\Z")


def _load_float32_word(value: object, field: str, *, must_positive: bool = False) -> float:
    if not isinstance(value,str) or _HEX.fullmatch(value) is None:
        raise ValueError("Invalid original Copy Float32 word: " + field)
    number = struct.unpack("<f",struct.pack("<I",int(value,16)))[0]
    if not math.isfinite(number) or number < 0 or (must_positive and number <= 0):
        raise ValueError("Invalid original Copy nonnegative word: " + field)
    return number


def compare_original_copy_selected_record(manifest_path: str | Path) -> dict:
    p = Path(manifest_path)
    if (p.is_symlink() or not p.is_file() or p.suffix.lower() != ".json" or
            not 2 <= p.stat().st_size <= 4096):
        raise ValueError("Invalid local original Copy manifest")
    payload = json.loads(p.read_text(encoding="utf-8"))
    if (not isinstance(payload,dict) or set(payload) != _REQUIRED_FIELDS or
            payload.get("schema") != SCHEMA or
            payload.get("copy_breakpoint_va") != "0x0084BC8C"):
        raise ValueError("Original Copy selected-record schema invalid")
    decimal = payload["decimal_separator"]
    if decimal not in (".",","):
        raise ValueError("Invalid original Copy decimal separator")
    clipboard_name = payload["original_clipboard_file"]
    if (not isinstance(clipboard_name,str) or
            _SAFE_TXT.fullmatch(clipboard_name) is None or
            ".." in clipboard_name or "/" in clipboard_name or
            "\\" in clipboard_name):
        raise ValueError("Invalid original Copy local clipboard filename")
    mean = _load_float32_word(payload["output_mean_bits"],"output_mean_bits")
    peak_x = _load_float32_word(
        payload["output_peak_x_bin_bits"],"output_peak_x_bin_bits")
    peak_y = _load_float32_word(payload["output_peak_y_bits"],"output_peak_y_bits")
    scale = _load_float32_word(
        payload["graph_xscale_bits"],"graph_xscale_bits",must_positive=True)
    # Original FPU uses FLD f32 PeakX; FMUL f32 XScale; FSTP f32.
    # Product of two float32 values is exactly representable in float64 before
    # the source's final Single rounding, for these ordinary finite numbers.
    frequency = float(np.float32(float(peak_x) * float(scale)))
    if not math.isfinite(frequency) or frequency < 0.0:
        raise ValueError("Original Copy peak scale overflow")
    summary = {
        "source": "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE",
        "output_mean":mean,
        "output_peak_frequency_hz":frequency,
        "output_peak_y":peak_y,
    }
    candidate = spectrum_triplet_text(
        summary,separator="\t",decimal_separator=decimal)
    original = read_operator_triplet_file(
        p.parent / clipboard_name,
        separator="\t",decimal_separator=decimal,encoding="utf-8-sig",
    )
    predicted_cols = candidate.split("\t")
    observed_cols = original["original_text_local_only"].split("\t")
    if len(predicted_cols) != 3 or len(observed_cols) != 3:
        raise ValueError("Expected exactly 3 original Copy columns")
    names = ("mean","peak_frequency_hz","peak_amplitude")
    equal = {
        name: predicted_cols[index] == observed_cols[index]
        for index,name in enumerate(names)
    }
    return {
        "source": SOURCE,
        "schema": SCHEMA,
        "operator_original_copy_line_sha256": original["sha256"],
        "formatting_digits_source": [3,4,4],
        "copy_record_snapshot_source_va": "0x0084BC8C",
        "selected_record_same_as_previous_GetSpectrum_authenticated": False,
        "all_three_text_fields_equal": all(equal.values()),
        "text_fields_equal": equal,
        "original_Delphi_RTL_general_formatting_parity_verified": False,
        "original_selected_record_snapshot_and_clipboard_same_click_authenticated": False,
        "no_archive_derived_or_inferred_fs_f_range": True,
        "private_original_values_or_paths_in_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline selected MVKView Copy record to TAB clipboard comparison")
    parser.add_argument("local_manifest",help="Private one-click record words + local Copy TXT")
    args = parser.parse_args(argv)
    try:
        report = compare_original_copy_selected_record(args.local_manifest)
    except (OSError, ValueError, TypeError, OverflowError, UnicodeError, struct.error):
        parser.exit(2,"Private original Copy click invalid; content withheld\n")
    print(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2))
    return 0 if report["all_three_text_fields_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
