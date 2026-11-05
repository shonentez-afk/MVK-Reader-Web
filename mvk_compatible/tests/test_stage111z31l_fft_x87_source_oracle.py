"""Stage111Z31L: independent x87 full Hann + radix2 spectral-power regression.

The expected SHA256 values are derived from reproducible SYNTHETIC
integer-LCG Float32 signals and separately implemented x87 C code.
They are not original MVKView operator captures, not device data,
not proof of arbitrary original numerical or signal-window parity.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import idr_power_spectrum

SOURCE = "SOURCE_DERIVED_X87_FFT_POWER_SYNTHETIC_ORACLE_STAGE111Z31L"
X87_SOURCE_SYNTHETIC_GOLDENS = {
    1024: "1944a3747121bf4ccee17623721a6646dc976ac86b3e338e663dddc7d30331da",
    2048: "e78f71958dd790ad8a329d4a6622877504d7e69f4d85d506ec0123f1d7995388",
    4096: "7cd1ee68570365b2dc2c8713e54a156ceddd831d5ec3e13c80dfde6b1aac6d19",
    16384: "1f645ef429abaae6d456ef50d8de3ba785975b805d2327b0c679f9b5d6cb6b53",
    65536: "68652624978cf9fb20e162cee9b4c6926a32248f3c1a8aca2ef1066f0319688e",
    262144: "84f2b70dad10d5bf507ef2e7bae46d8987e77442e26ea52044eae852f4969237",
}


def synthetic_original_prefft_candidate(n: int) -> np.ndarray:
    """Deterministic exact 32-bit arithmetic, no platform RNG or sin()."""
    if n not in X87_SOURCE_SYNTHETIC_GOLDENS:
        raise ValueError("unknown synthetic FFT test length")
    indices = np.arange(n, dtype=np.uint32)
    with np.errstate(over="ignore"):
        state = (indices*np.uint32(1664525)+np.uint32(1013904223))
    data = np.asarray(
        (state >> np.uint32(8)).astype(np.float64) * (2. / (2**24)) - 1.,
        dtype="<f4",
    )
    assert data.size == n and np.isfinite(data).all()
    return data


@pytest.mark.parametrize("n", tuple(X87_SOURCE_SYNTHETIC_GOLDENS))
def test_current_float32_fft_matches_independently_derived_x87_hash(n):
    samples = synthetic_original_prefft_candidate(n)
    original_bits = samples.view("<u4").copy()
    power, removed = idr_power_spectrum(
        samples, backend="idr_float32", remove_dc=False)
    assert removed == 0.
    assert power.dtype == np.dtype("<f4")
    assert power.size == n//2
    assert np.isfinite(power).all()
    assert np.all(power >= 0)
    assert hashlib.sha256(power.astype("<f4").tobytes()).hexdigest() == (
        X87_SOURCE_SYNTHETIC_GOLDENS[n])
    np.testing.assert_array_equal(samples.view("<u4"), original_bits)


@pytest.mark.skipif(
    sys.platform != "linux" or sys.byteorder != "little" or
    shutil.which("cc") is None,
    reason="Independent GNU x87 C compiler only available on x86 Linux",
)
@pytest.mark.parametrize("n", [1024, 4096, 262144])
def test_rebuild_independent_x87_c_and_compare_full_power(tmp_path, n):
    root = Path(__file__).resolve().parents[2]
    source = root/"tools"/"research"/"fft_x87_reference_stage111z31l.c"
    assert source.is_file()
    program = tmp_path/"fft_x87_replay"
    subprocess.run([
        "cc","-O2","-std=gnu11","-ffp-contract=off",
        "-fno-fast-math",str(source),"-lm","-o",str(program),
    ], capture_output=True, text=True, timeout=60, check=True)
    samples = synthetic_original_prefft_candidate(n)
    result = subprocess.run(
        [str(program),str(n)],input=samples.tobytes(),
        capture_output=True, timeout=60, check=True)
    assert len(result.stdout)==n//2*4
    power,mean = idr_power_spectrum(
        samples,backend="idr_float32",remove_dc=False)
    assert mean==0.
    np.testing.assert_array_equal(
        np.frombuffer(result.stdout,dtype="<u4"),
        power.view("<u4"))
    assert hashlib.sha256(result.stdout).hexdigest() == (
        X87_SOURCE_SYNTHETIC_GOLDENS[n])


def test_source_x87_checks_cannot_be_misinterpreted_as_original_data():
    assert SOURCE.startswith("SOURCE_DERIVED_")
    assert all(len(x)==64 and
               all(k in "0123456789abcdef" for k in x)
               for x in X87_SOURCE_SYNTHETIC_GOLDENS.values())
