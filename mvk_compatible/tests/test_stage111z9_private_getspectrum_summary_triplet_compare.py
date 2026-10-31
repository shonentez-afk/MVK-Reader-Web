"""Stage111Z.9 — fabricated-only 3-single post-spectrum regression tests.

No original EXE, IDP, archive, FFT memory dump, BIN, or copied clipboard
values are embedded in GitHub or used in CI.
"""
from __future__ import annotations

import json
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary
from mvk_compatible.private_getspectrum_summary_triplet_compare import (
    SOURCE, SCHEMA, _compare_single, compare_original_summary_triplet,
)


def _bits(value):
    return "0x" + struct.pack("<f", float(np.float32(value)))[::-1].hex().upper()


def _fake_capture(tmp_path, n=1024, fs=65536, mode=1):
    # Synthetic post-mode power, NOT raw original field measurements.
    p = np.full(n//2, np.float32(0.01), dtype="<f4")
    p[25] = np.float32(90.0)
    p[26] = np.float32(160.0)
    p[27] = np.float32(80.0)
    p[128] = np.float32(12.5)
    file = tmp_path/"summary_power.bin"
    p.tofile(file)
    ref = original_spectrum_summary(
        p, n_fft=n, fs_out=fs, f_range=2.0, spectrum_mode=mode
    )
    manifest = {
        "schema": SCHEMA,
        "summary_power_stop_va": "0x007D17E7",
        "summary_fields_stop_va": "0x007D1900",
        "fft_n": n,
        "sample_rate_hz": fs,
        "spectrum_mode": mode,
        "f_range_bits": "0x40000000",
        "summary_power_file": "summary_power.bin",
        "output_mean_bits": _bits(ref["output_mean"]),
        "output_peak_x_bits": _bits(ref["output_peak_x_bin"]),
        "output_peak_y_bits": _bits(ref["output_peak_y"]),
    }
    mp = tmp_path/"summary_capture.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    return mp, manifest, ref, p


def test_synthetic_original_triplet_bitwise_equal_without_authentication(tmp_path):
    mp, data, ref, powers = _fake_capture(tmp_path)
    report = compare_original_summary_triplet(mp)
    assert report["source"] == SOURCE and report["schema"] == SCHEMA
    assert report["fft_n"] == 1024
    assert report["all_three_float32_bits_equal"] is True
    assert report["original_delphi_summary_bitwise_parity_accepted"] is False
    assert report["same_original_GetSpectrum_invocation_authenticated"] is False
    assert report["original_summary_fields_and_metadata_in_report"] is False
    for name in ("output_mean","output_peak_x_bin","output_peak_y"):
        item = report["field_differences"][name]
        assert item["float32_bitwise_equal"] is True
        assert item["float32_ulp_distance"] == 0
        assert item["absolute_difference"] == 0.0
    exposed=json.dumps(report)
    assert "summary_power.bin" not in exposed
    assert "summary_capture.json" not in exposed
    assert str(tmp_path) not in exposed
    assert "40000000" not in exposed


def test_synthetic_original_peak_x_one_ulp_is_reported(tmp_path):
    mp, data, ref, powers = _fake_capture(tmp_path)
    original_int = int(data["output_peak_x_bits"], 16)
    data["output_peak_x_bits"] = f"0x{original_int+1:08X}"
    mp.write_text(json.dumps(data), encoding="utf-8")
    report = compare_original_summary_triplet(mp)
    assert report["all_three_float32_bits_equal"] is False
    p = report["field_differences"]["output_peak_x_bin"]
    assert p["float32_bitwise_equal"] is False
    assert p["float32_ulp_distance"] == 1
    assert p["absolute_difference"] > 0
    for k in ("output_mean","output_peak_y"):
        assert report["field_differences"][k]["float32_ulp_distance"] == 0


@pytest.mark.parametrize("mode", [0,1,2,3])
def test_all_synthetic_mode_metadata_are_supported_after_mode_stage(tmp_path,mode):
    mp, _, _, _ = _fake_capture(tmp_path,mode=mode)
    report = compare_original_summary_triplet(mp)
    assert report["mode_operator_supplied"] == mode
    assert report["all_three_float32_bits_equal"]


@pytest.mark.parametrize(("field", "bad"), [
    ("schema","wrong"),
    ("summary_power_stop_va","0x007D154B"),
    ("summary_fields_stop_va","0x007D18FF"),
    ("fft_n",1000), ("fft_n",True),
    ("sample_rate_hz",0),("sample_rate_hz",True),
    ("spectrum_mode",4),("spectrum_mode",True),
    ("f_range_bits","0x00000000"),
    ("f_range_bits","0x7F800000"),
    ("f_range_bits","3F800000"),
    ("output_mean_bits","0x7FC00000"),
    ("output_peak_x_bits","0xZZZZZZZZ"),
    ("output_peak_y_bits","0xBF800000"),
    ("summary_power_file","../private_dump.bin"),
    ("summary_power_file","C:\\Secret\\my_file.bin"),
])
def test_invalid_capture_metadata_rejected(tmp_path,field,bad):
    mp, data, _, _ = _fake_capture(tmp_path)
    data[field] = bad
    mp.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)


def test_missing_and_extra_fields_rejected(tmp_path):
    mp, data, _, _ = _fake_capture(tmp_path)
    data.pop("output_peak_y_bits")
    mp.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)
    mp, data, _, _ = _fake_capture(tmp_path)
    data["unauthorized"] = "do not print"
    mp.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)


def test_invalid_power_data_and_empty_capture_rejected(tmp_path):
    mp, data, _, power = _fake_capture(tmp_path)
    f = tmp_path/"summary_power.bin"
    f.write_bytes(f.read_bytes()[:-4])
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)
    power[8] = np.float32(np.nan)
    power.tofile(f)
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)
    power[8] = np.float32(-1)
    power.tofile(f)
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)
    np.zeros_like(power).tofile(f)
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)


def test_power_file_symlink_rejected(tmp_path):
    mp, data, _, power = _fake_capture(tmp_path)
    f = tmp_path/"summary_power.bin"
    f.unlink()
    private = tmp_path/"other.bin"
    power.tofile(private)
    try:
        f.symlink_to(private)
    except (OSError,NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(ValueError):
        compare_original_summary_triplet(mp)


def test_signed_float32_ulp_distance_for_negative_values_is_not_silent():
    with pytest.raises(ValueError):
        _compare_single(0xBF800000, 1.0)
