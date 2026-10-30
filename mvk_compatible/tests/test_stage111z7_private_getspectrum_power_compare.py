"""Stage111Z.7 synthetic private GetSpectrum pair comparator tests.

All signals/FFT powers are fabricated in pytest tmp_path. No real MVK
instrument, source executable, original IDP, raw archive, or network is used.
"""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import (
    idr_power_spectrum, idr_hann_rms, fft_idr_float32_real,
)
from mvk_compatible.private_getspectrum_power_compare import (
    SCHEMA, SOURCE, compare_original_fft_power_pair,
)


def _synthetic_capture(tmp_path, n: int = 1024):
    t = np.arange(n, dtype=np.float64)
    # Add a deliberate DC term to detect an accidental SECOND removal.
    # This is a synthetic before-FFT buffer, never an original capture.
    signal = np.asarray(2.5 + np.sin(2*np.pi*17*t/n)
                        + 0.08*np.cos(2*np.pi*63*t/n), dtype="<f4")
    power, _ = idr_power_spectrum(signal, backend="idr_float32", remove_dc=False)
    signal.tofile(tmp_path / "before_fft.bin")
    power.tofile(tmp_path / "after_power.bin")
    manifest = {
        "schema": SCHEMA,
        "before_stop_va": "0x007D153D",
        "after_stop_va": "0x007D154B",
        "fft_n": n,
        "spectrum_mode": 1,
        "envelope_code": 0,
        "channel_index": 0,
        "sample_rate_hz": 65536,
        "f_range_bits": "0x3F800000",
        "before_fft_file": "before_fft.bin",
        "after_power_file": "after_power.bin",
    }
    p = tmp_path / "capture.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p, manifest, signal, power


def test_exact_synthetic_prepared_pair_is_bitwise_equal_and_never_recentered(tmp_path):
    path, payload, signal, power = _synthetic_capture(tmp_path)
    report = compare_original_fft_power_pair(path)
    assert report["source"] == SOURCE
    assert report["schema"] == SCHEMA
    assert report["operator_supplied_fft_n"] == len(signal)
    assert report["pre_fft_original_buffer_recentered_or_mutated"] is False
    assert report["operator_supplied_before_after_same_original_invocation_authenticated"] is False
    assert report["original_delphi_fft_bitwise_parity_accepted"] is False
    stats = report["comparisons"]["source_derived_float32_fft"]
    assert stats["bins"] == len(power)
    assert stats["float32_bitwise_equal_count"] == len(power)
    assert stats["float32_bitwise_unequal_count"] == 0
    assert stats["within_one_float32_ulp_count"] == len(power)
    assert stats["max_float32_ulp_distance"] == 0
    assert stats["max_relative_bin_error"] == 0.0
    # Even though the input has a synthetic DC offset, no re-centering happens.
    assert abs(float(np.mean(signal))) > 2.
    report_text = json.dumps(report)
    assert "before_fft.bin" not in report_text
    assert "after_power.bin" not in report_text
    assert str(tmp_path) not in report_text
    assert "3F800000" not in report_text


def test_single_float32_ulp_mismatch_is_counted_not_suppressed(tmp_path):
    path, manifest, signal, power = _synthetic_capture(tmp_path)
    arr = np.fromfile(tmp_path / "after_power.bin", dtype="<f4")
    idx = 17
    assert arr[idx] > 0
    words = arr.view("<u4")
    words[idx] = np.uint32(int(words[idx]) + 1)
    arr.tofile(tmp_path / "after_power.bin")
    report = compare_original_fft_power_pair(path)
    x = report["comparisons"]["source_derived_float32_fft"]
    assert x["float32_bitwise_unequal_count"] == 1
    assert x["float32_bitwise_equal_count"] == len(arr) - 1
    assert x["max_float32_ulp_distance"] == 1
    assert x["within_one_float32_ulp_count"] == len(arr)


@pytest.mark.parametrize("field,value", [
    ("schema", "UNKNOWN_SCHEMA"),
    ("before_stop_va", "0x007D153C"),
    ("after_stop_va", "0x007D154A"),
    ("fft_n", 1025),
    ("fft_n", 65537),
    ("fft_n", True),
    ("spectrum_mode", 4),
    ("spectrum_mode", True),
    ("envelope_code", -1),
    ("channel_index", 8),
    ("sample_rate_hz", 0),
    ("f_range_bits", "0x00000000"),
    ("f_range_bits", "0x7F800000"),
    ("f_range_bits", "0xZZZZZZZZ"),
    ("before_fft_file", "../secret.bin"),
    ("before_fft_file", "C:\\private\\before_fft.bin"),
    ("after_power_file", "before_fft.bin"),
])
def test_invalid_or_unsafe_manifest_fails_closed(tmp_path, field, value):
    path, manifest, _, _ = _synthetic_capture(tmp_path)
    payload = copy.deepcopy(manifest)
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)


def test_missing_or_extra_manifest_field_is_rejected(tmp_path):
    path, manifest, _, _ = _synthetic_capture(tmp_path)
    payload = copy.deepcopy(manifest)
    del payload["fft_n"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)
    payload = copy.deepcopy(manifest)
    payload["unexpected"] = "extra"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)


def test_mismatched_sizes_or_nonfinite_original_values_fail_closed(tmp_path):
    path, manifest, _, power = _synthetic_capture(tmp_path)
    target = tmp_path / "after_power.bin"
    target.write_bytes(target.read_bytes()[:-4])
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)
    power = power.copy()
    power[4] = np.float32(np.nan)
    power.tofile(target)
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)
    power[4] = np.float32(-1.0)
    power.tofile(target)
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)


def test_source_files_cannot_be_symlinks(tmp_path):
    path, manifest, _, power = _synthetic_capture(tmp_path)
    target = tmp_path / "after_power.bin"
    target.unlink()
    link_to = tmp_path / "other.bin"
    power.tofile(link_to)
    try:
        target.symlink_to(link_to)
    except (OSError, NotImplementedError):
        pytest.skip("Filesystem disallows test symlinks")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)


def test_two_synthetic_modes_have_identical_raw_power_comparison(tmp_path):
    # FFT power is captured before mode 2/3 integrations, so the comparator
    # must not integrate its expected power based on spectrum mode.
    path, manifest, signal, power = _synthetic_capture(tmp_path)
    for mode in (0, 1, 2, 3):
        manifest["spectrum_mode"] = mode
        path.write_text(json.dumps(manifest), encoding="utf-8")
        stat = compare_original_fft_power_pair(path)["comparisons"]["source_derived_float32_fft"]
        assert stat["float32_bitwise_equal_count"] == len(power)



def _append_synthetic_complex_checkpoint(path, manifest, samples):
    n = samples.size
    windowed = np.asarray(
        samples.astype(np.float64) * idr_hann_rms(n).astype(np.float64),
        dtype=np.float32,
    )
    real, imag = fft_idr_float32_real(windowed)
    interleaved = np.empty(n*2, dtype="<f4")
    interleaved[0::2] = real
    interleaved[1::2] = imag
    interleaved.tofile(path.parent / "after_fft_complex.bin")
    manifest["complex_fft_file"] = "after_fft_complex.bin"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return interleaved


def test_optional_original_fft_complex_matches_source_derived_bitwise(tmp_path):
    path, manifest, samples, power = _synthetic_capture(tmp_path)
    expected = _append_synthetic_complex_checkpoint(path, manifest, samples)
    report = compare_original_fft_power_pair(path)
    assert report["optional_complex_fft_reference_compared"] is True
    optional = report["comparisons"]["optional_original_complex_fft"]
    for part in ("source_derived_real", "source_derived_imag"):
        assert optional[part]["bins"] == len(samples)
        assert optional[part]["float32_bitwise_equal_count"] == len(samples)
        assert optional[part]["float32_bitwise_unequal_count"] == 0
    assert report["comparisons"]["source_derived_float32_fft"][
        "float32_bitwise_equal_count"] == len(power)
    assert "after_fft_complex.bin" not in json.dumps(report)


def test_optional_complex_identifies_one_ulp_imaginary_error(tmp_path):
    path, manifest, samples, power = _synthetic_capture(tmp_path)
    interleaved = _append_synthetic_complex_checkpoint(path, manifest, samples)
    idx = 17
    assert interleaved[2*idx+1] > 0
    words = interleaved.view("<u4")
    words[2*idx+1] = np.uint32(int(words[2*idx+1]) + 1)
    interleaved.tofile(tmp_path / "after_fft_complex.bin")
    report = compare_original_fft_power_pair(path)
    imag = report["comparisons"]["optional_original_complex_fft"]["source_derived_imag"]
    assert imag["float32_bitwise_unequal_count"] == 1
    assert imag["max_float32_ulp_distance"] == 1
    assert imag["within_one_float32_ulp_count"] == len(samples)


def test_optional_complex_rejects_unsafe_file_and_wrong_length(tmp_path):
    path, manifest, samples, power = _synthetic_capture(tmp_path)
    original = _append_synthetic_complex_checkpoint(path, manifest, samples)
    payload = dict(manifest)
    payload["complex_fft_file"] = "../escape.bin"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)
    payload["complex_fft_file"] = "before_fft.bin"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "after_fft_complex.bin").write_bytes(original.tobytes()[:-4])
    with pytest.raises(ValueError):
        compare_original_fft_power_pair(path)


def test_optional_complex_signed_float32_negative_numbers_are_allowed(tmp_path):
    path, manifest, samples, power = _synthetic_capture(tmp_path)
    original = _append_synthetic_complex_checkpoint(path, manifest, samples)
    # Positive-angle FFT has signed real/imag; this must not be rejected.
    assert np.any(original < 0) and np.any(original > 0)
    report = compare_original_fft_power_pair(path)
    real = report["comparisons"]["optional_original_complex_fft"]["source_derived_real"]
    imag = report["comparisons"]["optional_original_complex_fft"]["source_derived_imag"]
    assert real["float32_bitwise_equal_count"] == len(samples)
    assert imag["float32_bitwise_equal_count"] == len(samples)



def test_stage111z8_original_shaped_zero_pair_is_not_claimed_as_perfect_fft(tmp_path):
    """This case reproduces only the uploaded file SIZES and zero-valued shape.

    No real uploaded original bytes are committed. Both inputs are synthetic
    zeros, 1,048,576 and 524,288 bytes respectively.
    """
    path, manifest, _signal, _power = _synthetic_capture(tmp_path, 1024)
    n = 262144
    manifest["fft_n"] = n
    path.write_text(json.dumps(manifest), encoding="utf-8")
    np.zeros(n, dtype="<f4").tofile(tmp_path / "before_fft.bin")
    np.zeros(n//2, dtype="<f4").tofile(tmp_path / "after_power.bin")
    report = compare_original_fft_power_pair(path)
    q = report["capture_quality"]
    assert report["operator_supplied_fft_n"] == n
    assert report["fft_numeric_comparison_performed"] is False
    assert report["original_delphi_fft_bitwise_parity_accepted"] is False
    assert report["optional_complex_fft_reference_compared"] is False
    assert report["comparisons"] == {}
    assert q["capture_status"] == "EMPTY_INPUT_AND_POWER"
    assert q["input_nonzero_count"] == q["power_nonzero_count"] == 0
    assert q["capture_informative_for_fft_numeric_parity"] is False
    text = json.dumps(report)
    assert str(tmp_path) not in text
    assert "before_fft.bin" not in text
    assert "after_power.bin" not in text


def test_stage111z8_zero_input_and_nonzero_power_reports_inconsistent(tmp_path):
    path, manifest, _signal, _power = _synthetic_capture(tmp_path, 1024)
    np.zeros(1024, dtype="<f4").tofile(tmp_path / "before_fft.bin")
    result = compare_original_fft_power_pair(path)
    assert result["capture_quality"]["capture_status"] == (
        "ZERO_INPUT_WITH_NONZERO_POWER_INCONSISTENT"
    )
    assert not result["fft_numeric_comparison_performed"]
    assert result["comparisons"] == {}


def test_stage111z8_nonzero_synthetic_reference_remains_comparable(tmp_path):
    path, manifest, signal, power = _synthetic_capture(tmp_path, 1024)
    report = compare_original_fft_power_pair(path)
    assert report["capture_quality"]["capture_status"] == "NONZERO_INPUT_AND_POWER"
    assert report["fft_numeric_comparison_performed"] is True
    assert report["comparisons"]["source_derived_float32_fft"][
        "float32_bitwise_equal_count"] == len(power)
