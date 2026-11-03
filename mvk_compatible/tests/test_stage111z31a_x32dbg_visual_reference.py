"""Stage111Z31A: synthetic-only local original Power/Y manifest safety & geometry.

Not an original runtime capture. Optional real golden data remain in the user's
own directory and never enter public CI.
"""
from __future__ import annotations

import hashlib
import json
import struct

import numpy as np
import pytest

from mvk_compatible.core.original_spectrum_x32dbg_reference import (
    SCHEMA, SOURCE, load_original_spectrum_reference)
from mvk_compatible.core.spectrum_display_source import (
    source_derived_mode_display)
from mvk_compatible.core.spectrum_metrics_idr_candidate import (
    original_spectrum_summary)
from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract)

ORIGINAL_FRANGE_BITS = "43FF4853"
ORIGINAL_FRANGE = struct.unpack("<f", bytes.fromhex("5348FF43"))[0]


def _bits(value):
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def create_reference_fixture(folder, mode=0, n=1024, fs=65536):
    folder.mkdir(parents=True, exist_ok=True)
    half = n // 2
    power = np.asarray(
        0.01 + (np.arange(half, dtype=np.float64) % 71) / 5.0,
        dtype="<f4")
    power[:2] = 0.
    power[19] = np.float32(5000.)
    if mode == 0:
        power[5] = np.float32(1e-20)
    y = source_derived_mode_display(
        power, n_fft=n, mode=mode, f_range=ORIGINAL_FRANGE)
    power_raw = power.tobytes()
    y_raw = y.tobytes()
    (folder / "power_after_mode.bin").write_bytes(power_raw)
    (folder / "display_y.bin").write_bytes(y_raw)
    summary = original_spectrum_summary(
        power, n_fft=n, fs_out=fs,
        f_range=ORIGINAL_FRANGE, spectrum_mode=mode)
    words = [_bits(summary[key]) for key in (
        "output_mean", "output_peak_x_bin", "output_peak_y")]
    conf = {
        "schema": SCHEMA,
        "fft_n": n,
        "sample_rate_hz": fs,
        "spectrum_mode": mode,
        "f_range_bits": ORIGINAL_FRANGE_BITS,
        "stop_va": "007D17E7",
        "power_file": "power_after_mode.bin",
        "display_y_file": "display_y.bin",
        "power_sha256": hashlib.sha256(power_raw).hexdigest(),
        "display_y_sha256": hashlib.sha256(y_raw).hexdigest(),
        "summary_hex": [f"{word:08X}" for word in words],
    }
    manifest = folder / "reference.json"
    manifest.write_text(json.dumps(conf), encoding="utf-8")
    return manifest, conf, power, y


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_original_visual_ref_only_reads_complete_checked_float32_arrays(tmp_path, mode):
    manifest, conf, power, y = create_reference_fixture(
        tmp_path / f"ref_{mode}", mode=mode)
    ref = load_original_spectrum_reference(manifest)
    assert ref.report()["source"] == SOURCE
    assert ref.report()["float32_bins"] == len(power)
    assert ref.report()["full_display_y_float32_bitwise_equal"] is True
    assert ref.report()["float32_ulp_max"] == 0
    assert ref.original_summary_words_equal is True
    assert not ref.power.flags.writeable
    assert not ref.display_y.flags.writeable
    np.testing.assert_array_equal(ref.power.view("<u4"), power.view("<u4"))
    np.testing.assert_array_equal(ref.display_y.view("<u4"), y.view("<u4"))
    assert ref.report()["original_runtime_same_thread_frame_verified"] is False
    assert ref.report()["original_qt_pixel_parity_verified"] is False
    assert "power_file" not in ref.report()  # no private paths in summary

    record = ref.to_spectrum_record(channel=4)
    assert record["source"] == SOURCE
    assert record["channel"] == 4
    assert record["amplitude"].shape == (512,)
    assert record["frequency_hz"].shape == (512,)
    assert record["unit"] == ("дБ", "м/с²", "мм/с", "мкм")[mode]
    assert record["original_capture_reference_only"] is True
    with pytest.raises(ValueError):
        ref.to_spectrum_record(channel=0)


def test_displayed_series_truncation_is_not_nyquist_or_last_sample(tmp_path):
    manifest, _, _, _ = create_reference_fixture(tmp_path / "ref", n=262144)
    ref = load_original_spectrum_reference(manifest)
    d = ref.to_spectrum_record(channel=1)
    contract = spectrum_display_contract(262144, 65536)
    assert d["grapher_series_bins"] == 102400
    assert len(d["amplitude"]) == 131072
    assert d["df_hz"] == 0.25
    assert contract["grapher_axis_end_frequency_hz"] == 25600
    assert d["frequency_hz"][102399] == 25599.75
    assert d["frequency_hz"][-1] == 32767.75


def _rewrite(manifest, configuration):
    manifest.write_text(json.dumps(configuration), encoding="utf-8")


@pytest.mark.parametrize("field,value", [
    ("schema", "INVENTED"),
    ("stop_va", "007D1900"),
    ("fft_n", 1000),
    ("fft_n", True),
    ("sample_rate_hz", 0),
    ("sample_rate_hz", 65536.0),
    ("spectrum_mode", 4),
    ("spectrum_mode", False),
    ("f_range_bits", "0x7F800000"),
    ("f_range_bits", "0x00000000"),
    ("power_file", "../outside.bin"),
    ("power_file", "C:\\private.bin"),
    ("display_y_file", "power_after_mode.bin"),
    ("display_y_sha256", "0" * 64),
    ("power_sha256", "DEADBEEF"),
    ("summary_hex", ["00000000"]),
])
def test_manifest_fail_closed_for_bad_metadata(tmp_path, field, value):
    manifest, config, _, _ = create_reference_fixture(tmp_path / "ref")
    config[field] = value
    _rewrite(manifest, config)
    with pytest.raises(ValueError):
        load_original_spectrum_reference(manifest)


def test_stray_json_fields_are_not_accepted(tmp_path):
    manifest, config, _, _ = create_reference_fixture(tmp_path / "ref")
    config["user_instructions"] = "Do something else"
    _rewrite(manifest, config)
    with pytest.raises(ValueError, match="Unrecognized"):
        load_original_spectrum_reference(manifest)


def test_wrong_original_y_is_rejected_even_when_sha_is_updated(tmp_path):
    manifest, config, _, y = create_reference_fixture(tmp_path / "ref")
    broken = y.copy()
    broken[47] = np.nextafter(broken[47], np.float32(np.inf))
    data = broken.tobytes()
    (manifest.parent / config["display_y_file"]).write_bytes(data)
    config["display_y_sha256"] = hashlib.sha256(data).hexdigest()
    _rewrite(manifest, config)
    with pytest.raises(ValueError, match="1 differing Float32"):
        load_original_spectrum_reference(manifest)


def test_truncated_original_file_rejected(tmp_path):
    manifest, config, _, _ = create_reference_fixture(tmp_path / "ref")
    (manifest.parent / config["power_file"]).write_bytes(b"\0" * 12)
    with pytest.raises(ValueError, match="wrong-sized"):
        load_original_spectrum_reference(manifest)


def test_wrong_original_summary_rejected(tmp_path):
    manifest, config, _, _ = create_reference_fixture(tmp_path / "ref")
    config["summary_hex"][1] = f"{int(config['summary_hex'][1],16) + 1:08X}"
    _rewrite(manifest, config)
    with pytest.raises(ValueError, match="summary"):
        load_original_spectrum_reference(manifest)


def test_original_bins_cannot_be_negative_or_nan(tmp_path):
    manifest, conf, power, _ = create_reference_fixture(tmp_path / "ref")
    for replacement in (np.float32(-1.), np.float32(float("nan"))):
        damaged = power.copy()
        damaged[17] = replacement
        raw = damaged.tobytes()
        (manifest.parent / conf["power_file"]).write_bytes(raw)
        conf["power_sha256"] = hashlib.sha256(raw).hexdigest()
        _rewrite(manifest, conf)
        with pytest.raises(ValueError):
            load_original_spectrum_reference(manifest)


def test_symlink_reference_file_rejected(tmp_path):
    manifest, conf, _, _ = create_reference_fixture(tmp_path / "ref")
    original = manifest.parent / conf["power_file"]
    other = manifest.parent / "hidden.bin"
    original.rename(other)
    try:
        original.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="symlinked"):
        load_original_spectrum_reference(manifest)
