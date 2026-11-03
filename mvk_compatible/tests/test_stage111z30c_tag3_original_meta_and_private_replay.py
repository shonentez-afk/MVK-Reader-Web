"""Stage111Z30C — Tag3 original metadata and bin-2 peak boundary regression.

All public tests below use synthetic arrays only. Original operator-supplied
binary buffers are NEVER committed. An optional private full 131072-bin replay
requires MVK_STAGE111Z30C_TAG3_PRIVATE_DIR pointing at a local V6 TAG3 folder.
Expected hashes/three tiny float words originate from the operator-reported
original x32dbg session on 2026-11-03; not independent process attestation.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import struct

import numpy as np
import pytest

from mvk_compatible.core.envelope_spectrum_idr_candidate import _delphi_integration_power
from mvk_compatible.core.spectrum_display_source import source_derived_mode_display
from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary

N = 262144
FS = 65536
F_RANGE_BITS = 0x43FF4853
ORIGINAL_SUMMARY_HEX = (0x42B1B034, 0x00000000, 0x00000000)
ORIGINAL_WINDOW_LOW = 0x003C8000  # Different from Tag2's 0x00290000.
PRIOR_TAG2_WINDOW_LOW = 0x00290000
ORIGINAL_SHA = {
    "power_before_mode.bin": "16ecc83ef511fc1809b474ec4c0dd3d8ce96321e81fd1ccad1af94e5fffa1c34",
    "power_after_mode.bin": "9dfb017893d8a5f85f27b59917002fde0329885d420713fde768fa567f3379c6",
    "display_y.bin": "3475f53063d34f098356bdd31aa68b75521ed2d828e9946530072169c4c6e92f",
    "summary_triplet.bin": "e5353f25b35be7f6a1eebd5d4100fa5b148da1ec174095454e9a5871306780a5",
}
PRIVATE_ENV = "MVK_STAGE111Z30C_TAG3_PRIVATE_DIR"


def _word(b: bytes, pos: int = 0) -> int:
    return struct.unpack_from("<I", b, pos)[0]


def _bits(value: float) -> int:
    return _word(struct.pack("<f", float(np.float32(value))))


def _f32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


def test_operator_scalar_metadata_is_exact_without_original_sample_bytes():
    assert (N, FS, ORIGINAL_WINDOW_LOW, PRIOR_TAG2_WINDOW_LOW) == (
        262144, 65536, 0x003C8000, 0x00290000)
    assert ORIGINAL_WINDOW_LOW != PRIOR_TAG2_WINDOW_LOW
    assert _bits(_f32(F_RANGE_BITS)) == F_RANGE_BITS
    assert _bits(_f32(ORIGINAL_SUMMARY_HEX[0])) == ORIGINAL_SUMMARY_HEX[0]
    assert _f32(ORIGINAL_SUMMARY_HEX[0]) == 88.84414672851562
    assert ORIGINAL_SUMMARY_HEX[1:] == (0, 0)


def test_source_peak_bin_two_keeps_mean_but_skips_peak_fields():
    # Synthetic illustration of the *observed* original edge case:
    # an energy maximum in spectral bin 2 is not considered a valid
    # +/-2-bin peak under the original strict "candidate > 2" branch.
    n = 4096
    fs = 65536
    raw = np.zeros(n // 2, dtype="<f4")
    raw[2] = np.float32(0.1)
    raw[80] = np.float32(1000.)
    once = _delphi_integration_power(raw, n, fs, 1)
    twice = _delphi_integration_power(raw, n, fs, 2)
    np.testing.assert_array_equal(
        _delphi_integration_power(once, n, fs, 1).view("<u4"),
        twice.view("<u4"),
    )
    assert int(np.argmax(once)) == 80
    assert int(np.argmax(twice)) == 2
    assert np.all(twice[:2] == np.float32(0))
    result = original_spectrum_summary(
        twice, n_fft=n, fs_out=fs, f_range=_f32(F_RANGE_BITS),
        spectrum_mode=3,
    )
    assert result["raw_max_power_bin"] == 2
    assert result["output_mean"] > 0
    assert _bits(result["output_peak_x_bin"]) == 0
    assert _bits(result["output_peak_y"]) == 0
    shown = source_derived_mode_display(
        twice, n_fft=n, mode=3, f_range=_f32(F_RANGE_BITS))
    assert int(np.argmax(shown)) == 2
    assert shown[2] > 0
    assert shown.dtype == np.dtype("<f4")


def test_source_peak_bin_three_still_calculates_peak():
    n, fs = 1024, 65536
    raw = np.zeros(n // 2, dtype="<f4")
    raw[3] = np.float32(1000.)
    raw[4] = np.float32(50.)
    summary = original_spectrum_summary(
        raw, n_fft=n, fs_out=fs, f_range=_f32(F_RANGE_BITS), spectrum_mode=3)
    assert summary["raw_max_power_bin"] == 3
    assert summary["output_peak_x_bin"] > 0
    assert summary["output_peak_y"] > 0


def test_optional_private_operator_capture_matches_all_three_stages():
    folder_name = os.environ.get(PRIVATE_ENV)
    if not folder_name:
        pytest.skip("Original 131072-bin Tag3 buffers are private and not in CI")
    folder = Path(folder_name)
    assert folder.is_dir() and not folder.is_symlink()

    def read(name: str, size: int) -> bytes:
        path = folder / name
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == size
        raw = path.read_bytes()
        assert len(raw) == size
        return raw

    buffers = {name: read(name, (N // 2) * 4)
               for name in ("power_before_mode.bin",
                            "power_after_mode.bin", "display_y.bin")}
    triplet = read("summary_triplet.bin", 12)
    buffers["summary_triplet.bin"] = triplet
    for name, expected_sha in ORIGINAL_SHA.items():
        assert hashlib.sha256(buffers[name]).hexdigest() == expected_sha
    before, after, y = (
        np.frombuffer(buffers[name], dtype="<f4")
        for name in ("power_before_mode.bin",
                     "power_after_mode.bin", "display_y.bin")
    )
    assert all(bool(np.isfinite(a).all()) and not bool(np.signbit(a).any())
               for a in (before, after, y))
    assert int(np.argmax(after)) == 2
    assert bool(np.all(after[:2] == 0))

    for key in ("params_before.bin", "params_after.bin", "params_summary.bin"):
        assert len(read(key, 60)) == 60
    pre = read("params_before.bin", 60)
    post = read("params_after.bin", 60)
    summ = read("params_summary.bin", 60)
    assert pre == post
    assert pre[:0x30] == summ[:0x30]
    assert summ[0x30:0x3C] == triplet
    assert (_word(pre, 4), _word(pre, 8), _word(pre, 0x18),
            _word(pre, 0x20), _word(pre, 0x24),
            _word(pre, 0x28), _word(pre, 0x2C)) == (
            N, 0, 3, ORIGINAL_WINDOW_LOW, 0, N // 2, FS)
    assert _word(read("frange.bin", 4)) == F_RANGE_BITS

    power = before.copy()
    power[:2] = np.float32(0)
    expected_power = _delphi_integration_power(power, N, FS, 2)
    np.testing.assert_array_equal(expected_power.view("<u4"), after.view("<u4"))
    expected_y = source_derived_mode_display(
        after, n_fft=N, mode=3, f_range=_f32(F_RANGE_BITS))
    np.testing.assert_array_equal(expected_y.view("<u4"), y.view("<u4"))
    summary = original_spectrum_summary(
        after, n_fft=N, fs_out=FS, f_range=_f32(F_RANGE_BITS), spectrum_mode=3)
    assert tuple(map(_bits, (
        summary["output_mean"], summary["output_peak_x_bin"],
        summary["output_peak_y"]))) == ORIGINAL_SUMMARY_HEX
    assert tuple(struct.unpack("<III", triplet)) == ORIGINAL_SUMMARY_HEX
    # Even a successful private test cannot prove the original thread/frame.
    assert summary["original_delphi_numerical_parity_verified"] is False
