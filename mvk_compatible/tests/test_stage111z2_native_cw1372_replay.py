"""Stage111Z.2: native source-derived x87 CW replay vs user-reported four-mode golden.

The x32dbg original reading of CW=0x1372 was performed for Tag=0 only.
Applying it to Tags 1..3 is a hypothesis. The test verifies four observations
against a separate GNU x87 process, not general Delphi numerical parity.
The native probe never reads local EXE/IDP/BIN/PCAP or connects to a device.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess

import pytest

from mvk_compatible.tests.test_stage111z_original_runtime_golden import (
    Stage111ZRuntimeGoldenRegression,
)


@pytest.fixture(scope="module")
def native_cw_replay_executable(tmp_path_factory):
    gcc = shutil.which("gcc")
    if not gcc or platform.machine().lower() not in (
        "x86_64", "amd64", "i386", "i486", "i586", "i686", "x86"
    ):
        pytest.skip("GNU x87 toolchain not available")
    source = Path(__file__).parents[1] / "native_probe" / "x87_graph_vscale_probe.c"
    executable = tmp_path_factory.mktemp("native_x87_cw_replay") / (
        "x87_replay.exe" if os.name == "nt" else "x87_replay"
    )
    build = subprocess.run(
        [gcc, "-O0", "-fno-fast-math", "-mfpmath=387", "-std=c11",
         "-Wall", "-Wextra", str(source), "-lm", "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert build.returncode == 0, build.stderr[-1200:]
    return executable


def _run(executable, f_range_hex: str, cw_hex: str = "1372"):
    return subprocess.run(
        [str(executable), "--replay-hex", f_range_hex, cw_hex],
        capture_output=True, text=True, timeout=10, check=False,
    )


def _parse_success(result):
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("# source=STAGE111Z2_NATIVE_X87_REPLAY ")
    assert "restored=1" in lines[0]
    rows = []
    for line in lines[1:]:
        fields = line.split(",")
        assert len(fields) == 5
        mode, scaled, graph_default, step, fraction = fields
        assert len(scaled) == len(graph_default) == len(fraction) == 8
        assert int(step) in (2, 5, 10)
        rows.append((int(mode), scaled, graph_default, int(step), fraction))
    assert [row[0] for row in rows] == [0, 1, 2, 3]
    return lines[0], rows


def test_real_4_mode_snapshots_against_native_cw1372(native_cw_replay_executable):
    # Original values are from x32dbg, not synthesized from the native probe.
    case = Stage111ZRuntimeGoldenRegression
    header, rows = _parse_success(
        _run(native_cw_replay_executable, case.F_RANGE_HEX, "1372")
    )
    assert "requested_cw=0x1372" in header
    assert "active_cw=0x1372" in header
    for (mode, observed_before, observed_after), result in zip(case.CASES, rows):
        assert result[0] == mode
        assert result[1] == observed_before
        assert result[2] == observed_after


def test_reserved_control_word_bit_does_not_change_outputs(native_cw_replay_executable):
    case = Stage111ZRuntimeGoldenRegression
    header, rows = _parse_success(
        _run(native_cw_replay_executable, case.F_RANGE_HEX, "1332")
    )
    assert "requested_cw=0x1332" in header
    assert "active_cw=0x1372" in header or "active_cw=0x1332" in header
    _, measured = _parse_success(
        _run(native_cw_replay_executable, case.F_RANGE_HEX, "1372")
    )
    assert rows == measured


def test_native_boundary_is_characterization_not_delphi_certificate(
    native_cw_replay_executable,
):
    # The original's FRange was ~510, not the synthetic exact boundary 1000.
    header, rows = _parse_success(
        _run(native_cw_replay_executable, "447A0000", "1372")
    )
    assert "restored=1" in header
    assert rows[0][1] == "447A0000"
    # A legitimate platform-specific x87 FYL2X one-ULP difference; keep
    # both outcomes valid until an original Delphi boundary golden exists.
    assert rows[0][2] in ("447A0000", "44FA0000")


@pytest.mark.parametrize(("f_range", "cw"), [
    ("00000000", "1372"),
    ("7F800000", "1372"),
    ("7FC00000", "1372"),
    ("FF800000", "1372"),
    ("7F7FFFFF", "1372"),
    ("00000001", "1372"),
    ("43FF4853", "037F"),
    ("43FF4853", "FFFF"),
    ("43FF4853", "137"),
    ("X3FF4853", "1372"),
])
def test_invalid_or_unbounded_inputs_are_rejected(
    native_cw_replay_executable, f_range, cw,
):
    result = _run(native_cw_replay_executable, f_range, cw)
    assert result.returncode == 2
    assert not result.stdout
    assert result.stderr


def test_legacy_selftest_still_available(native_cw_replay_executable):
    result = subprocess.run(
        [str(native_cw_replay_executable), "--selftest"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 28
