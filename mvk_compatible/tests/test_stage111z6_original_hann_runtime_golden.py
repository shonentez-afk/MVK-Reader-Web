"""Stage111Z.6: user-reported original Windows Hann runtime reference at four indices.

These four Single bit patterns were read by the operator in x32dbg from the
running original MVKView (BSS at 0x0096DA48), with the Spectrum tab opened.
They were NOT independently captured inside CI. Do not claim full 262144
table parity, general Delphi/Win32 parity, or instrument-signal provenance.

Native x87 replayer is source-derived and separate from original Delphi.
"""
from __future__ import annotations

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import MAX_FFT_N, idr_hann_rms
from mvk_compatible.tests.test_stage111z5_native_hann_probe import (
    _run, native_hann_executable,
)


# Original x32dbg memory observations: dword:[0096DA48 + 4*index].
# All four anomalous positions observed separately by the operator.
# These are NOT a complete original runtime table golden.
USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS = {
    1: 0x2F80EF9C,
    5: 0x31C97664,
    262139: 0x31C97664,
    262143: 0x2F80EF9C,
}


def test_original_hann_reference_indexes_and_capture_coverage():
    assert MAX_FFT_N == 262144
    assert 0 < len(USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS) < MAX_FFT_N
    assert all(isinstance(i, int) and 0 <= i < MAX_FFT_N
               for i in USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS)
    assert all(isinstance(bits, int) and 0 <= bits <= 0xFFFFFFFF
               for bits in USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS)


def test_user_reported_original_hann_bits_match_native_cw1372(
    native_hann_executable,
):
    """Exact 4-point x87 replay comparison, not complete Delphi acceptance."""
    result = _run(native_hann_executable, "--summary")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0].startswith("# source=STAGE111Z5_SYNTHETIC_X87_HANN ")
    assert "restored=1" in lines[0]
    assert "active_cw=0x1372" in lines[0] or "active_cw=0x1332" in lines[0]
    native_samples = {
        int(index): int(bits, 16)
        for index, bits in (line.split(",") for line in lines[1:-1])
    }
    for index, original_bits in USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS.items():
        assert native_samples[index] == original_bits


def test_full_hann_table_uses_all_four_exact_original_runtime_bits():
    full = idr_hann_rms(MAX_FFT_N)
    assert full.dtype == np.float32 and len(full) == MAX_FFT_N
    bits = full.view(np.uint32)
    for index, original_bits in USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS.items():
        assert int(bits[index]) == original_bits
    # Public API returns a fresh copy and cannot corrupt cached FFT data.
    full[1] = np.float32(0)
    assert int(idr_hann_rms(MAX_FFT_N).view(np.uint32)[1]) == 0x2F80EF9C


@pytest.mark.parametrize("n", [256, 1024, 4096, 8192, 65536, 131072])
def test_original_four_odd_edge_indices_do_not_change_smaller_fft(n):
    """Original Hann stride samples only even indices for N < 262144."""
    stride = MAX_FFT_N // n
    assert stride >= 2 and (stride & (stride - 1)) == 0
    assert all(index % stride != 0
               for index in USER_REPORTED_ORIGINAL_RUNTIME_HANN_BITS)
    # Independent unpatched NumPy baseline: previous behavior is preserved.
    indices = np.arange(n, dtype=np.float64) * stride
    baseline = np.asarray(
        (1. - np.cos((2. * np.pi / MAX_FFT_N) * indices)) /
        np.sqrt(1.5), dtype=np.float32)
    actual = idr_hann_rms(n)
    np.testing.assert_array_equal(actual.view(np.uint32), baseline.view(np.uint32))
