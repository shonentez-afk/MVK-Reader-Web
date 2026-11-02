"""Stage111Z30A: synthetic-only capture comparisons, never real original data."""
from __future__ import annotations

import hashlib
import json
import struct

import numpy as np
import pytest

from mvk_compatible.core.envelope_spectrum_idr_candidate import _delphi_integration_power
from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary
from mvk_compatible.private_getspectrum_postmode_compare import (
    SOURCE, SCHEMA, compare_original_postmode_capture, main,
)


def _bits(value):
    return "0x" + struct.pack("<f", float(np.float32(value)))[::-1].hex().upper()


def _manifest(tmp_path, mode=2, n=1024, fs=65536, with_summary=True):
    before = np.full(n//2, np.float32(0.5), dtype="<f4")
    before[0] = 19.
    before[1] = 29.
    before[47] = 150.
    before[48] = 90.
    before[200] = 6.
    after = before.copy()
    low = max(2, round(n/(2.0*fs)))
    after[:low] = 0
    if mode > 1:
        after = _delphi_integration_power(after, n, fs, mode - 1)
    path1, path2 = tmp_path/"original_before_power.bin", tmp_path/"original_after_mode.bin"
    path1.write_bytes(before.tobytes())
    path2.write_bytes(after.tobytes())
    d = {
        "schema": SCHEMA, "fft_n": n,
        "output_sample_rate_hz": fs, "spectrum_mode": mode,
        "channel_index_zero_based": 3, "envelope_code": 0,
        "f_range_bits": "0x40000000",
        "before_stop_va": "0x007D154B",
        "after_stop_va": "0x007D17E7",
        "same_invocation_operator_confirmed": True,
        "before_power_file": path1.name,
        "after_mode_file": path2.name,
        "before_power_sha256": hashlib.sha256(before.tobytes()).hexdigest(),
        "after_mode_sha256": hashlib.sha256(after.tobytes()).hexdigest(),
    }
    if with_summary:
        s = original_spectrum_summary(
            after, n_fft=n, fs_out=float(fs), f_range=2.0, spectrum_mode=mode)
        d.update({
            "summary_stop_va": "0x007D1900",
            "output_mean_bits": _bits(s["output_mean"]),
            "output_peak_x_bits": _bits(s["output_peak_x_bin"]),
            "output_peak_y_bits": _bits(s["output_peak_y"]),
        })
    mp = tmp_path/"original_private_capture.json"
    mp.write_text(json.dumps(d), encoding="utf-8")
    return mp, d, before, after


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_four_modes_exact_local_synthetic_and_summary(tmp_path, mode):
    mp, payload, before, after = _manifest(tmp_path, mode=mode)
    report = compare_original_postmode_capture(mp)
    assert report["source"] == SOURCE and report["mode"] == mode
    assert report["post_mode_power_bitwise_equal"] is True
    assert report["post_mode_power_comparison"]["float32_bitwise_equal_count"] == 512
    assert report["all_summary_words_bitwise_equal_to_original_postmode_candidate"] is True
    assert report["all_summary_words_bitwise_equal_to_reconstructed_candidate"] is True
    assert report["power_integration_passes"] == max(0, mode-1)
    assert report["full_four_mode_parity_certified"] is False
    assert report["same_original_invocation_independently_authenticated"] is False
    assert report["display_log_XScale_TQGrapher_covered"] is False
    public = json.dumps(report)
    assert payload["before_power_file"] not in public
    assert payload["after_mode_file"] not in public
    assert payload["f_range_bits"] not in public
    assert str(tmp_path) not in public
    assert main([str(mp)]) == 0


def test_omitted_summary_is_explicitly_partial(tmp_path):
    mp, _, _, _ = _manifest(tmp_path, with_summary=False)
    r = compare_original_postmode_capture(mp)
    assert r["post_mode_power_bitwise_equal"]
    assert r["original_summary_triplet_captured"] is False
    assert r["all_summary_words_bitwise_equal_to_reconstructed_candidate"] is None


def test_single_bin_mutation_changes_numeric_gate_not_source_bytes(tmp_path):
    mp, d, _, after = _manifest(tmp_path, mode=3)
    after[48] = np.nextafter(after[48], np.float32(np.inf))
    raw = after.tobytes()
    (tmp_path/d["after_mode_file"]).write_bytes(raw)
    d["after_mode_sha256"] = hashlib.sha256(raw).hexdigest()
    mp.write_text(json.dumps(d), encoding="utf-8")
    r = compare_original_postmode_capture(mp)
    assert r["post_mode_power_bitwise_equal"] is False
    assert r["post_mode_power_comparison"]["float32_bitwise_unequal_count"] == 1
    assert r["post_mode_power_comparison"]["within_one_float32_ulp_count"] == 512
    assert main([str(mp)]) == 1


@pytest.mark.parametrize(("field", "value"), [
    ("fft_n", 1000), ("fft_n", True), ("output_sample_rate_hz", 0),
    ("output_sample_rate_hz", True), ("spectrum_mode", 4), ("spectrum_mode", True),
    ("channel_index_zero_based", 8), ("envelope_code", 32),
    ("f_range_bits", "0x00000000"), ("f_range_bits", "0x7F800000"),
    ("before_stop_va", "0x007D154C"), ("after_stop_va", "0x007D17E6"),
    ("same_invocation_operator_confirmed", False),
    ("before_power_file", "../private.bin"), ("after_mode_file", "C:\\original.bin"),
    ("before_power_sha256", "bad"), ("after_mode_sha256", "A"*64),
    ("summary_stop_va", "0x007D1901"), ("output_peak_x_bits", "0x7FC00000"),
])
def test_bad_metadata_fails_closed(tmp_path, field, value):
    mp, d, _, _ = _manifest(tmp_path)
    d[field] = value
    mp.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)


def test_partial_triplet_extra_field_and_bad_sha_are_rejected(tmp_path):
    mp, d, _, _ = _manifest(tmp_path)
    d.pop("output_peak_y_bits")
    mp.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)
    mp, d, _, _ = _manifest(tmp_path)
    d["unexpected"] = "bad"
    mp.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)
    mp, d, _, _ = _manifest(tmp_path)
    p = tmp_path/d["before_power_file"]
    p.write_bytes(p.read_bytes()[:-4])
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)


@pytest.mark.parametrize("corruption", ["nan", "negative", "zero"])
def test_corrupt_original_capture_never_counts_as_parity(tmp_path, corruption):
    mp, d, _, after = _manifest(tmp_path)
    if corruption == "nan":
        after[70] = np.nan
    if corruption == "negative":
        after[70] = -1.0
    if corruption == "zero":
        after.fill(0)
    raw = after.tobytes()
    (tmp_path/d["after_mode_file"]).write_bytes(raw)
    d["after_mode_sha256"] = hashlib.sha256(raw).hexdigest()
    mp.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)


def test_capture_symlink_is_refused(tmp_path):
    mp, d, _, _ = _manifest(tmp_path)
    path = tmp_path/d["before_power_file"]
    real = tmp_path/"capture_real.bin"
    path.rename(real)
    try:
        path.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported")
    with pytest.raises(ValueError):
        compare_original_postmode_capture(mp)
