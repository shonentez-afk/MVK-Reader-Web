"""Stage111Z30C — original-operator Tag0 full stored Float32 Y numerical regression.

Public CI exercises synthetic log-Y behavior and checks only original-derived
metadata/hash/summary words. Original sample arrays are never committed.
Opt-in private full-bin replay:
 MVK_STAGE111Z30C_TAG0_PRIVATE_DIR=<directory containing
 power_after_mode.bin + display_y.bin>
Observed from x32dbg at 0x007D17E7, user-reported same stop, 2026-11-03.
No independent runtime provenance or pixel-level Qt parity asserted.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_display_source import (
    source_derived_mode_display,
)
from mvk_compatible.core.spectrum_metrics_idr_candidate import (
    original_spectrum_summary,
)

ORIGINAL_N = 262144
ORIGINAL_FS = 65536
ORIGINAL_FRANGE_BITS = 0x43FF4853
ORIGINAL_MODE = 0
ORIGINAL_POWER_SHA256 = (
    "81456d63be57536572fc2e0fe174f57454157c41c00890233554558e74f2ce09"
)
ORIGINAL_Y_SHA256 = (
    "28c605d9864e9f52a79e09e874f39243ab08b4696e2bb2c8946dab7c71467d90"
)
ORIGINAL_FIELD_WORDS = (0x40DC8F5E, 0x466D8095, 0x3F475279)
ORIGINAL_Y_PEAK = np.float32(-55.32063674926758)
PRIVATE_DIR_ENV = "MVK_STAGE111Z30C_TAG0_PRIVATE_DIR"


def _f32_from_bits(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def _bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def test_operator_metadata_baseline_only_contains_hashes_and_scalar_words():
    assert ORIGINAL_N // 2 == 131072
    assert ORIGINAL_FS / ORIGINAL_N == 0.25
    assert ORIGINAL_MODE == 0
    assert _bits(_f32_from_bits(ORIGINAL_FRANGE_BITS)) == ORIGINAL_FRANGE_BITS
    assert len(ORIGINAL_POWER_SHA256) == len(ORIGINAL_Y_SHA256) == 64
    assert all(x in "0123456789abcdef" for x in ORIGINAL_POWER_SHA256 + ORIGINAL_Y_SHA256)
    assert tuple(_bits(_f32_from_bits(x)) for x in ORIGINAL_FIELD_WORDS) == ORIGINAL_FIELD_WORDS
    assert _f32_from_bits(ORIGINAL_FIELD_WORDS[0]) == 6.892500877380371


def test_tag0_log_y_preserves_zero_floor_but_does_not_clamp_small_power():
    p = np.zeros(1024 // 2, dtype="<f4")
    p[2] = np.float32(1e-15)
    p[10] = np.float32(1.)
    p[47] = np.float32(100.)
    snapshot = p.copy()
    y = source_derived_mode_display(p, n_fft=1024, mode=0,
                                    f_range=_f32_from_bits(ORIGINAL_FRANGE_BITS))
    assert y.dtype == np.dtype("<f4")
    np.testing.assert_array_equal(snapshot.view("<u4"), p.view("<u4"))
    assert y[0] == y[1] == np.float32(-180.)
    assert y[2] < np.float32(-180.)  # Valid positive power can be below -180 dB.
    offset = float(np.float32(2. * math.log10(float(np.float32(512)))))
    assert _bits(y[47]) == _bits(np.float32((math.log10(100.) - offset) * 10.))
    assert bool(np.isfinite(y).all())
    assert len(y) == 512


def test_tag0_log_y_ignores_scale_in_post_mode_power_to_display_conversion():
    p = np.ones(512, dtype="<f4")
    p[0] = p[1] = 0
    p[2] = np.float32(1e-12)
    ya = source_derived_mode_display(p, n_fft=1024, mode=0, f_range=1.)
    yb = source_derived_mode_display(
        p, n_fft=1024, mode=0,
        f_range=_f32_from_bits(ORIGINAL_FRANGE_BITS))
    np.testing.assert_array_equal(ya.view("<u4"), yb.view("<u4"))


def test_private_original_tag0_capture_full_131072_float32_bitwise_replay():
    directory = os.environ.get(PRIVATE_DIR_ENV)
    if not directory:
        pytest.skip("Original operator-supplied x32dbg Float32 arrays remain private")

    root = Path(directory)
    assert root.is_dir() and not root.is_symlink()

    def read_original(name: str, expected_sha: str) -> np.ndarray:
        path = root / name
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == 524288
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_sha
        arr = np.frombuffer(raw, dtype="<f4")
        assert len(arr) == ORIGINAL_N // 2
        assert bool(np.isfinite(arr).all())
        return arr

    p = read_original("power_after_mode.bin", ORIGINAL_POWER_SHA256)
    y = read_original("display_y.bin", ORIGINAL_Y_SHA256)
    assert bool((p >= 0).all())
    assert bool(np.all(p[:2] == 0))
    assert bool(np.all(y[:2] == np.float32(-180)))
    assert int((p == 0).sum()) == 2
    assert int((y < -180.).sum()) == 3
    assert int(np.argmax(p)) == int(np.argmax(y)) == 15200
    assert _bits(y[15200]) == _bits(ORIGINAL_Y_PEAK)

    predicted = source_derived_mode_display(
        p, n_fft=ORIGINAL_N, mode=ORIGINAL_MODE,
        f_range=_f32_from_bits(ORIGINAL_FRANGE_BITS))
    np.testing.assert_array_equal(
        predicted.view("<u4"), y.view("<u4"))
    assert hashlib.sha256(predicted.tobytes()).hexdigest() == ORIGINAL_Y_SHA256

    summary = original_spectrum_summary(
        p, n_fft=ORIGINAL_N, fs_out=ORIGINAL_FS,
        f_range=_f32_from_bits(ORIGINAL_FRANGE_BITS),
        spectrum_mode=ORIGINAL_MODE)
    assert tuple(_bits(summary[field]) for field in (
        "output_mean", "output_peak_x_bin", "output_peak_y")) == ORIGINAL_FIELD_WORDS
    assert summary["raw_max_power_bin"] == 15200
    assert summary["output_peak_frequency_hz"] == 3800.036376953125
    assert summary["original_delphi_numerical_parity_verified"] is False
