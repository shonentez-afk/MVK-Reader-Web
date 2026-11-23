"""One Float32 window -> Hann -> FFT -> Power -> four original amplitudes.

Independent source-derived x87 C replay vs production NumPy candidate.
ONLY synthetic input is used: NO original Delphi measurements or hardware.
One-window source parity is not original Win32 runtime bitwise parity.
"""
from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import (
    idr_power_spectrum, mean_center_float32,
)
from mvk_compatible.core.envelope_spectrum_idr_candidate import (
    _delphi_integration_power,
)
from mvk_compatible.core.spectrum_display_source import (
    source_derived_mode_display,
)

X87_AVAILABLE = (
    sys.platform == "linux" and sys.byteorder == "little"
    and platform.machine().lower() in ("x86_64", "amd64", "i386", "i686")
    and shutil.which("cc") is not None
)


def synthetic_source_window(n: int) -> np.ndarray:
    """Deterministic integer-LCG Float32 raw signal, never device data."""
    j = np.arange(n, dtype=np.uint32)
    with np.errstate(over="ignore"):
        state = j * np.uint32(1664525) + np.uint32(1013904223)
    signal = np.asarray(
        (state >> np.uint32(8)).astype(np.float64) * (2. / 2**24) - 1.,
        dtype="<f4",
    )
    assert signal.shape == (n,) and np.isfinite(signal).all()
    return signal


@pytest.fixture(scope="module")
def reference_binaries(tmp_path_factory):
    if not X87_AVAILABLE:
        pytest.skip("GNU x87 compiler on little-endian x86 Linux required")
    root = Path(__file__).resolve().parents[2]
    sources = (
        root / "tools/research/fft_x87_reference_stage111z31l.c",
        root / "tools/research/x87_spectrum_modes_reference.c",
    )
    if any(not item.is_file() for item in sources):
        pytest.fail("Source-derived x87 reference missing")
    folder = tmp_path_factory.mktemp("original_source_x87_four_modes")
    results = []
    for index, source in enumerate(sources):
        binary = folder / ("x87_fft" if index == 0 else "x87_modes")
        subprocess.run([
            "cc", "-O2", "-std=gnu11", "-ffp-contract=off",
            "-fno-fast-math", str(source), "-lm", "-o", str(binary),
        ], capture_output=True, check=True, timeout=60)
        results.append(binary)
    return tuple(results)


def _run(binary: Path, args: list[str], input_bytes: bytes) -> np.ndarray:
    process = subprocess.run(
        [str(binary), *args], input=input_bytes,
        capture_output=True, check=True, timeout=80,
    )
    assert len(process.stdout) % 4 == 0
    return np.frombuffer(process.stdout, dtype="<f4").copy()


def _assert_single_bits(candidate: np.ndarray, independent: np.ndarray):
    assert candidate.dtype == np.dtype("<f4")
    assert independent.dtype == np.dtype("<f4")
    np.testing.assert_array_equal(
        candidate.view("<u4"), independent.view("<u4"))


@pytest.mark.parametrize("n,fs,f_range", [
    (1024, 65536, 1.0),
    (4096, 512, 1.25),
    (8192, 65536, 0.75),
])
def test_one_source_window_four_display_modes(
        reference_binaries, n, fs, f_range):
    """Full original-structure N/2 Single comparison including integration."""
    fft_exe, mode_exe = reference_binaries
    raw = synthetic_source_window(n)
    original_input_sha = hashlib.sha256(raw.tobytes()).hexdigest()
    centered, _mean = mean_center_float32(raw)
    independent_power = _run(fft_exe, [str(n)], centered.tobytes())
    candidate_power, _removed_mean = idr_power_spectrum(
        raw, backend="idr_float32", remove_dc=True)
    _assert_single_bits(candidate_power, independent_power)
    assert candidate_power.size == n // 2
    assert hashlib.sha256(raw.tobytes()).hexdigest() == original_input_sha
    low = max(2, round((n / fs) * 0.5))
    for mode in range(4):
        post = independent_power.copy()
        post[:low] = np.float32(0.)
        if mode in (2, 3):
            post = _delphi_integration_power(post, n, fs, mode - 1)
        reference_post = _run(
            mode_exe, [
                str(n), str(mode), str(f_range), str(fs), "--power"
            ], independent_power.tobytes())
        _assert_single_bits(post, reference_post)
        candidate_y = source_derived_mode_display(
            post, n_fft=n, mode=mode, f_range=f_range)
        reference_y = _run(
            mode_exe, [
                str(n), str(mode), str(f_range), str(fs), "--y"
            ], independent_power.tobytes())
        _assert_single_bits(candidate_y, reference_y)
        assert candidate_y.size == n // 2
        assert np.isfinite(candidate_y).all()
        if mode == 0:
            assert np.all(candidate_y[:low] == np.float32(-180.))
        else:
            assert np.all(candidate_y[:low] == np.float32(0.))
    np.testing.assert_array_equal(raw, synthetic_source_window(n))


def test_synthetic_x87_agreement_is_not_original_delphi_pass():
    from mvk_compatible.core.spectrum_display_source import (
        display_source_provenance,
    )
    flags = display_source_provenance()
    assert flags["original_x87_log10_sqrt_float32_bitwise_parity_verified"] is False
    assert flags["original_full_display_y_runtime_parity_verified"] is False
