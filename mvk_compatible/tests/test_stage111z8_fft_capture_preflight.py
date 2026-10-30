"""Stage111Z.8: synthetic-only FFT capture preflight regression tests.

Fixtures are generated in tmp_path. No operator-provided original memory
dumps, private IDP, EXE or actual measurement data are uploaded to CI.
"""
from __future__ import annotations

import json
import numpy as np
import pytest

from mvk_compatible.private_getspectrum_capture_preflight import (
    SOURCE, _quality, inspect_fft_capture_pair,
)


def _write_pair(tmp_path, before, after):
    before_path = tmp_path / "before_fft.bin"
    after_path = tmp_path / "after_power.bin"
    np.asarray(before, dtype="<f4").tofile(before_path)
    np.asarray(after, dtype="<f4").tofile(after_path)
    return before_path, after_path


def test_empty_pair_with_same_dimensions_as_received_operator_files(tmp_path):
    b, a = _write_pair(
        tmp_path, np.zeros(262144, dtype="<f4"),
        np.zeros(131072, dtype="<f4"),
    )
    report = inspect_fft_capture_pair(b, a)
    assert report["source"] == SOURCE
    assert report["fft_n_inferred_from_byte_sizes"] == 262144
    assert report["input_float32_count"] == 262144
    assert report["power_float32_count"] == 131072
    assert report["input_nonzero_count"] == 0
    assert report["power_nonzero_count"] == 0
    assert report["capture_status"] == "EMPTY_INPUT_AND_POWER"
    assert report["capture_informative_for_fft_numeric_parity"] is False
    assert report["original_delphi_fft_bitwise_parity_verified"] is False
    # Output must not leak raw bytes, path names or per-bin values.
    printed = json.dumps(report, sort_keys=True)
    assert "before_fft.bin" not in printed
    assert "after_power.bin" not in printed
    assert str(tmp_path) not in printed


def test_synthetic_nonzero_pair_can_proceed_to_comparison(tmp_path):
    n = 8192
    t = np.arange(n)
    signal = np.sin(2*np.pi*41*t/n).astype("<f4")
    power = np.abs(np.fft.fft(signal.astype(np.float64))[:n//2])**2
    b, a = _write_pair(tmp_path, signal, power)
    report = inspect_fft_capture_pair(b, a)
    assert report["fft_n_inferred_from_byte_sizes"] == n
    assert report["input_nonzero_count"] > n//2
    assert report["power_nonzero_count"] > 0
    assert report["capture_status"] == "NONZERO_INPUT_AND_POWER"
    assert report["capture_informative_for_fft_numeric_parity"] is True
    assert report["original_delphi_fft_bitwise_parity_verified"] is False


def test_zero_input_with_power_and_reverse_are_not_accepted(tmp_path):
    n = 1024
    b, a = _write_pair(
        tmp_path, np.zeros(n, dtype=np.float32),
        np.ones(n//2, dtype=np.float32),
    )
    r = inspect_fft_capture_pair(b, a)
    assert r["capture_status"] == "ZERO_INPUT_WITH_NONZERO_POWER_INCONSISTENT"
    assert not r["capture_informative_for_fft_numeric_parity"]
    b, a = _write_pair(
        tmp_path, np.ones(n, dtype=np.float32),
        np.zeros(n//2, dtype=np.float32),
    )
    r = inspect_fft_capture_pair(b, a)
    assert r["capture_status"] == "NONZERO_INPUT_WITH_ZERO_POWER_UNINFORMATIVE"
    assert not r["capture_informative_for_fft_numeric_parity"]


@pytest.mark.parametrize(("bad_n", "bad_power_n"), [
    (1000, 500), (1024, 511), (8192, 8192), (262145, 131072),
    (0, 0),
])
def test_sizes_fail_closed(tmp_path, bad_n, bad_power_n):
    b, a = _write_pair(
        tmp_path, np.zeros(bad_n, dtype=np.float32),
        np.zeros(bad_power_n, dtype=np.float32),
    )
    with pytest.raises(ValueError):
        inspect_fft_capture_pair(b, a)


def test_nonfinite_and_negative_power_fail_closed(tmp_path):
    n = 1024
    for values_before, values_after in [
        (np.full(n,np.nan,dtype=np.float32),np.zeros(n//2,dtype=np.float32)),
        (np.full(n,np.inf,dtype=np.float32),np.zeros(n//2,dtype=np.float32)),
        (np.zeros(n,dtype=np.float32),np.full(n//2,-1,dtype=np.float32)),
        (np.zeros(n,dtype=np.float32),np.full(n//2,-0.0,dtype=np.float32)),
    ]:
        b, a = _write_pair(tmp_path, values_before, values_after)
        with pytest.raises(ValueError):
            inspect_fft_capture_pair(b, a)


def test_symlink_is_rejected_without_source_path_leak(tmp_path):
    n = 1024
    b, a = _write_pair(tmp_path, np.ones(n), np.ones(n//2))
    alias = tmp_path / "another.bin"
    try:
        alias.symlink_to(b)
    except (OSError, NotImplementedError):
        pytest.skip("Host filesystem does not allow symlinks")
    with pytest.raises(ValueError):
        inspect_fft_capture_pair(alias, a)


def test_same_file_does_not_qualify_as_original_pair(tmp_path):
    b, a = _write_pair(tmp_path,np.ones(1024),np.ones(512))
    with pytest.raises(ValueError):
        inspect_fft_capture_pair(b,b)


def test_direct_quality_is_compatible_with_existing_comparator(tmp_path):
    n = 1024
    b, a = _write_pair(tmp_path, np.ones(n), np.ones(n//2))
    left=np.fromfile(b,dtype="<f4")
    right=np.fromfile(a,dtype="<f4")
    q = _quality(left,right)
    assert q["capture_informative_for_fft_numeric_parity"]
    assert q["input_nonzero_count"]==n
    assert q["power_nonzero_count"]==n//2
