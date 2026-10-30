"""Stage111Z.5: original-structure synthetic x87 Hann vs NumPy candidate.

The native program executes GCC/x87, NOT original Delphi/Windows. All 262144
inputs are synthetic indices, no original IDP, measurement or archive is used.
A host CPU's FCOS result may vary: CI asserts sane numerical closeness, not
a purported universal bitwise Delphi golden.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import idr_hann_rms, MAX_FFT_N


@pytest.fixture(scope="module")
def native_hann_executable(tmp_path_factory):
    gcc = shutil.which("gcc")
    if not gcc or platform.machine().lower() not in (
        "x86_64", "amd64", "i386", "i486", "i586", "i686", "x86"
    ):
        pytest.skip("GNU x87/80-bit Extended compiler unavailable")
    source = Path(__file__).parents[1] / "native_probe" / "x87_hann_table_probe.c"
    executable = tmp_path_factory.mktemp("native_hann") / (
        "x87_hann.exe" if os.name == "nt" else "x87_hann"
    )
    result = subprocess.run(
        [gcc, "-O0", "-fno-fast-math", "-mfpmath=387", "-std=c11",
         "-Wall", "-Wextra", str(source), "-lm", "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0 and "requires 80-bit extended" in result.stderr:
        pytest.skip("Host compiler does not support x87 80-bit long double")
    assert result.returncode == 0, result.stderr[-1500:]
    return executable


def _run(probe, mode: str):
    return subprocess.run(
        [str(probe), mode], capture_output=True, text=True, check=False, timeout=30,
    )


def test_native_hann_summary_finite_symmetry_and_cw_restoration(native_hann_executable):
    output = _run(native_hann_executable, "--summary")
    assert output.returncode == 0, output.stderr
    assert not output.stderr
    lines = output.stdout.splitlines()
    assert len(lines) == 16
    assert lines[0].startswith("# source=STAGE111Z5_SYNTHETIC_X87_HANN ")
    assert "initial_cw=0x1332" in lines[0]
    assert ("active_cw=0x1372" in lines[0] or
            "active_cw=0x1332" in lines[0])
    assert "restored=1" in lines[0] and "n=262144" in lines[0]
    assert lines[-1].startswith("# fnv64=")
    observed = {int(k): int(v, 16) for k, v in (line.split(",") for line in lines[1:-1])}
    assert len(observed) == 14
    assert observed[0] == 0x00000000
    assert observed[131072] == 0x3FD105EC
    assert observed[65536] == observed[196608]
    assert observed[1] == observed[262143]
    assert observed[5] == observed[262139]
    assert observed[8192] > 0


def test_full_native_x87_hann_is_close_to_numpy_and_subsampled_correctly(
    native_hann_executable,
):
    output = _run(native_hann_executable, "--hex-all")
    assert output.returncode == 0, output.stderr
    assert not output.stderr
    lines = output.stdout.splitlines()
    assert len(lines) == MAX_FFT_N
    source_bits = np.fromiter((int(s, 16) for s in lines), dtype=np.uint32,
                              count=MAX_FFT_N)
    reference = idr_hann_rms(MAX_FFT_N)
    assert reference.dtype == np.float32
    assert len(reference) == len(source_bits)
    assert source_bits[0] == 0
    assert source_bits[MAX_FFT_N // 2] == reference.view(np.uint32)[MAX_FFT_N // 2]
    original_candidate_bits = reference.view(np.uint32)
    ulps = np.abs(source_bits.astype(np.int64) -
                  original_candidate_bits.astype(np.int64))
    # Avoid host-CPU-dependent exact bit-count assertions; the source runtime
    # FCOS and Delphi FPU state are NOT witnessed by this synthetic test.
    assert int(ulps.max()) <= 4
    assert int(np.count_nonzero(ulps)) < MAX_FFT_N // 32
    for n in (256, 1024, 8192, 65536, 131072, MAX_FFT_N):
        idx = np.arange(n, dtype=np.int64) * (MAX_FFT_N // n)
        candidate = idr_hann_rms(n)
        np.testing.assert_array_equal(
            candidate.view(np.uint32), original_candidate_bits[idx])
        assert np.max(ulps[idx]) <= 4


@pytest.mark.parametrize("bad_args", [
    [], ["--help"], ["--summary", "unexpected"], ["--raw-pcap"], ["--hex-all", "1"],
])
def test_native_hann_rejects_unknown_modes_without_writing(native_hann_executable, bad_args):
    result = subprocess.run(
        [str(native_hann_executable), *bad_args],
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert result.returncode == 2
    assert not result.stdout
    assert "usage:" in result.stderr
