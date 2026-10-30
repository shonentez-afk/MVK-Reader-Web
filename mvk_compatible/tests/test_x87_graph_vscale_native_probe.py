"""Stage111V: independent machine-instruction probe, synthetic only.

The test compiles source-derived x87 instructions on x86 with GCC; it is
optional on platforms without an x87 toolchain. The output cannot prove
Delphi/VCL parity, differing 32-bit control word or actual original FRange.
"""
from __future__ import annotations
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess

import pytest
from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale,
)


@pytest.fixture(scope='module')
def native_x87_probe(tmp_path_factory):
    gcc = shutil.which('gcc')
    if not gcc or platform.machine().lower() not in (
        'x86_64', 'amd64', 'i386', 'i486', 'i586', 'i686', 'x86'
    ):
        pytest.skip('GNU x87 compiler not available on this CI worker')
    source = (Path(__file__).parents[1] / 'native_probe' /
              'x87_graph_vscale_probe.c')
    assert source.is_file()
    output = tmp_path_factory.mktemp('native_x87') / (
        'x87_probe.exe' if os.name == 'nt' else 'x87_probe')
    # No shell; fixed source file and synthetic-only CLI prevent injection,
    # implicit private-file reads or unexpected command execution.
    compile_result = subprocess.run(
        [gcc, '-O0', '-fno-fast-math', '-mfpmath=387', '-std=c11',
         '-Wall', '-Wextra', str(source), '-lm', '-o', str(output)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr[-1600:]
    result = subprocess.run([str(output), '--selftest'],
                            capture_output=True, text=True,
                            timeout=15, check=False)
    assert result.returncode == 0, result.stderr[-1600:]
    assert result.stderr == ''
    return result.stdout.splitlines()


def test_actual_x87_fldlg2_fyl2x_f2xm1_fscale_synthetic(native_x87_probe):
    lines = native_x87_probe
    assert len(lines) == 28
    assert lines[0].startswith('# source=STAGE111V_SYNTHETIC_X87_HELPER_PROBE')
    assert 'x87_control_word=0x' in lines[0]
    values = []
    for line in lines[1:]:
        raw, mode, result, nice_step, fraction = line.split(',')
        assert int(mode) in (0, 1, 2, 3)
        assert int(nice_step) in (2, 5, 10)
        assert math.isfinite(float(fraction))
        assert math.isfinite(float(result)) and float(result) > 0
        predicted = spectrum_graph_default_vscale(float(raw), int(mode))
        assert predicted['selected_nice_step'] == int(nice_step)
        assert predicted['candidate_graph_default_vscale_single'] == pytest.approx(
            float(result), rel=2e-7, abs=1e-9)
        assert not predicted['original_math_helpers_x87_rounding_verified']
        values.append((float(raw), int(nice_step), float(result)))
    assert values[4] == (2.0, 5, 5.0)
    assert values[5] == (5.0, 10, 10.0)
    assert values[7] == (20.0, 5, 50.0)


def test_hardware_oracle_handles_source_negative_log10_branch(native_x87_probe):
    rows = [tuple(float(item) for item in line.split(','))
            for line in native_x87_probe[1:]]
    assert rows[0][0] < 1 and rows[0][2] > rows[0][0]
    assert rows[1][0] < 1 and rows[1][2] == pytest.approx(rows[1][0])
    assert rows[2][0] == .5 and rows[2][2] == .5
    assert rows[3][0] == 1.0 and rows[3][2] == 1.0


def test_float32_ulp_neighbours_around_2_5_10_are_probed(native_x87_probe):
    """Source check must cover adjacent 32-bit floats, not 64-bit guesses."""
    rows = [tuple(float(item) for item in line.split(','))
            for line in native_x87_probe[1:]]
    for centre, pair in ((2., rows[15:17]), (5., rows[17:19]),
                         (10., rows[19:21])):
        assert pair[0][0] < centre < pair[1][0]
        assert pair[0][2] <= pair[1][2]
        for value in pair:
            assert value[3] in (2.,5.,10.)


def test_hardware_mode_multipliers_0_1_2_3_are_checked(native_x87_probe):
    rows = [tuple(float(item) for item in line.split(','))
            for line in native_x87_probe[22:]]
    assert [int(row[1]) for row in rows] == [0,1,2,3,2,3]
    assert rows[0][2] == pytest.approx(.5)
    assert rows[1][2] == pytest.approx(.5)
    assert rows[2][2] == pytest.approx(5.)
    assert rows[3][2] == pytest.approx(50.)
