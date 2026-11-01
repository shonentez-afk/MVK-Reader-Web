"""Stage111Z.10 — original Win32 GetSpectrum summary, operator-reported golden.

A user's original x32dbg session yielded THREE exact IEEE754 Single outputs,
N, Fs, mode and channel FRange. CI stores only the four raw numeric metadata
fields and test logic; it NEVER includes original FFT power sample arrays,
private archive, IDP or EXE.

A fully bitwise regression of original material is deliberately opt-in:
set MVK_STAGE111Z10_PRIVATE_SUMMARY_BIN to a LOCAL, operator-owned 524288-byte
Float32 dump. To also verify the low-bin transition from Stage111Z.8, set
MVK_STAGE111Z8_PRIVATE_POWER_BIN. Both tests are skipped in public CI.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_metrics_idr_candidate import (
    original_spectrum_summary,
)
from mvk_compatible.private_getspectrum_summary_triplet_compare import (
    _compare_single,
)

# Operator read these from ONE original MVKView GetSpectrum x32dbg invocation.
# They are not static IDP constants or synthetic FFT output values.
ORIGINAL_N = 262144
ORIGINAL_FS = 65536
ORIGINAL_MODE = 0
ORIGINAL_FRANGE_BITS = 0x43FF4853
ORIGINAL_FIELDS = {
    "output_mean": 0x40DC8F5E,
    "output_peak_x_bin": 0x466D8095,
    "output_peak_y": 0x3F475279,
}
PRIVATE_SUMMARY_ENV = "MVK_STAGE111Z10_PRIVATE_SUMMARY_BIN"
PRIVATE_PRIOR_POWER_ENV = "MVK_STAGE111Z8_PRIVATE_POWER_BIN"


def _float_from_bits(raw: int) -> float:
    return struct.unpack("<f", struct.pack("<I", raw))[0]


def _bits_from_float(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def _load_private_capture(env_name: str) -> np.ndarray:
    name = os.environ.get(env_name)
    if not name:
        pytest.skip("Original operator-only Float32 capture is not in public CI")
    p = Path(name)
    assert p.is_file() and not p.is_symlink()
    assert p.stat().st_size == (ORIGINAL_N // 2) * 4
    samples = np.fromfile(p, dtype="<f4")
    assert samples.size == ORIGINAL_N // 2
    assert bool(np.isfinite(samples).all())
    assert not bool(np.signbit(samples).any())
    return samples


def test_operator_reference_words_are_independent_float32_observations():
    assert (ORIGINAL_N, ORIGINAL_FS, ORIGINAL_MODE) == (262144, 65536, 0)
    assert ORIGINAL_N // ORIGINAL_FS == 4
    frange = _float_from_bits(ORIGINAL_FRANGE_BITS)
    assert _bits_from_float(frange) == ORIGINAL_FRANGE_BITS
    assert frange > 0
    assert set(ORIGINAL_FIELDS) == {
        "output_mean", "output_peak_x_bin", "output_peak_y"
    }
    for raw in ORIGINAL_FIELDS.values():
        assert raw < 0x80000000
        value = _float_from_bits(raw)
        assert _bits_from_float(value) == raw
        assert value > 0


def test_runtime_metadata_expected_summary_band_and_peak_scale():
    # This tests only metadata/formula; runtime sample parity is separate.
    first = max(2, round(ORIGINAL_N / (2.0 * ORIGINAL_FS)))
    last = min(ORIGINAL_N // 2 - 1, int(ORIGINAL_N / 2.56))
    assert (first, last) == (2, 102400)
    # OutputPeakX is in FFT bins, not directly in Hz.
    position = _float_from_bits(ORIGINAL_FIELDS["output_peak_x_bin"])
    hz = float(np.float32(position * np.float32(ORIGINAL_FS / ORIGINAL_N)))
    assert hz == 3800.036376953125


def test_user_supplied_three_single_words_are_exact_comparator_references():
    # Sanity-check source comparator itself without forging original powers.
    for original_bits in ORIGINAL_FIELDS.values():
        result = _compare_single(original_bits, _float_from_bits(original_bits))
        assert result["float32_bitwise_equal"] is True
        assert result["float32_ulp_distance"] == 0
        assert result["absolute_difference"] == 0.0
    changed = _compare_single(
        ORIGINAL_FIELDS["output_mean"],
        _float_from_bits(ORIGINAL_FIELDS["output_mean"] + 1)
    )
    assert changed["float32_ulp_distance"] == 1


def test_private_original_post_mode_capture_replays_three_exact_words():
    """Skip in public CI; require the ACTUAL private 007D17E7 Float32 file."""
    power = _load_private_capture(PRIVATE_SUMMARY_ENV)
    assert np.count_nonzero(power) == power.size - 2
    assert int(np.argmax(power)) == 15200
    assert _bits_from_float(power[0]) == _bits_from_float(power[1]) == 0
    result = original_spectrum_summary(
        power, n_fft=ORIGINAL_N, fs_out=float(ORIGINAL_FS),
        f_range=_float_from_bits(ORIGINAL_FRANGE_BITS),
        spectrum_mode=ORIGINAL_MODE,
    )
    assert result["summary_first_bin"] == 2
    assert result["summary_last_bin"] == 102400
    assert result["raw_max_power_bin"] == 15200
    for field, original_bits in ORIGINAL_FIELDS.items():
        assert _bits_from_float(result[field]) == original_bits
    # Even after a successful source-derived calculation the original
    # Delphi process/thread provenance is only operator-reported.
    assert result["original_delphi_numerical_parity_verified"] is False


def test_private_stage111z8_to_stage111z10_power_transition():
    """Skip unless BOTH private original user uploads are explicitly present."""
    summary = _load_private_capture(PRIVATE_SUMMARY_ENV)
    prior = _load_private_capture(PRIVATE_PRIOR_POWER_ENV)
    equal = summary.view("<u4") == prior.view("<u4")
    assert np.flatnonzero(~equal).tolist() == [0, 1]
    assert bool(equal[2:].all())
    assert bool(np.any(prior[:2] > 0.0))
    assert bool(np.all(summary[:2] == 0.0))
