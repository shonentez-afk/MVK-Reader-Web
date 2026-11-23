"""Strict same-RX evidence gate: synthetic fixtures never certify hardware."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from ..core.original_mode2_paired_acceptance import (
    compare_original_mode2_pair, main,
)

def _make_pair(tmp_path: Path, *, full: bool, mismatch: bool = False):
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    reference.mkdir()
    candidate.mkdir()
    raw = b"synthetic-one-socket-frame" * 20
    (reference / "raw.bin").write_bytes(raw)
    (candidate / "raw.bin").write_bytes(raw)
    kinds = [
        "ADC_BIN_F32", "TSXML_CP1251", "VALUES_CSV", "TABLE_CSV",\n        "GETSIGNAL_F32",
        "GETSPECTRUM_PRE_HANN_F32", "GETSPECTRUM_WINDOWED_F32",
        "GETSPECTRUM_FFT_COMPLEX_F32", "GETSPECTRUM_POWER_F32",
    ] if full else ["GETSPECTRUM_Y_F32"]
    descriptors = []
    for idx, kind in enumerate(kinds):
        name = f"pair{idx}.dat"
        body = (np.arange(8, dtype="<f4") + idx).tobytes() if kind not in (
            "TSXML_CP1251", "VALUES_CSV", "TABLE_CSV") else b"same file bytes"
        (reference / name).write_bytes(body)
        (candidate / name).write_bytes(body)
        descriptors.append(dict(kind=kind, reference_name=name, candidate_name=name))
    if full:
        tags = [("GETSPECTRUM_Y_F32", tag) for tag in range(4)]
        tags += [("GETSPECTRUM_POSTMODE_POWER_F32", tag) for tag in (2, 3)]
        for idx, (kind, mode) in enumerate(tags):
            name = f"mode_{idx}.dat"
            body = (np.arange(8, dtype="<f4") + idx).tobytes()
            (reference / name).write_bytes(body)
            (candidate / name).write_bytes(body)
            descriptors.append(dict(kind=kind, reference_name=name,
                                    candidate_name=name, source_spectrum_mode=mode))
        if mismatch:
            (candidate / "mode_0.dat").write_bytes(
                (np.arange(8, dtype="<f4") + np.float32(0.25)).tobytes())
    manifest = dict(session_id="SYNTHETIC_NOT_HARDWARE", files=descriptors,
                    reference_raw_name="raw.bin", candidate_raw_name="raw.bin")
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    return reference, candidate, manifest, manifest_file

def test_incomplete_identical_pairs_must_fail_strict_cli(tmp_path, capsys):
    reference, candidate, manifest, manifest_file = _make_pair(tmp_path, full=False)
    result = compare_original_mode2_pair(reference, candidate,
        files=manifest["files"], session_id=manifest["session_id"],
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin")
    assert result["all_pairs_byte_identical"]
    assert not result["strict_same_raw_file_evidence_complete"]
    argv = ["--reference-dir", str(reference), "--candidate-dir", str(candidate),
            "--manifest", str(manifest_file)]
    assert main(argv) == 0   # legacy compare contract unchanged
    assert main(argv + ["--require-complete-same-raw"]) == 3
    capsys.readouterr()

def test_full_synthetic_file_evidence_is_not_hardware_attestation(tmp_path, capsys):
    reference, candidate, manifest, manifest_file = _make_pair(tmp_path, full=True)
    result = compare_original_mode2_pair(reference, candidate,
        files=manifest["files"], session_id=manifest["session_id"],
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin")
    assert result["strict_same_raw_file_evidence_complete"]
    assert not result["strict_same_raw_is_physical_attestation"]
    assert not result["original_hardware_parity_verified"]
    assert not result["original_1_to_1_release_gate_passed"]
    argv = ["--reference-dir", str(reference), "--candidate-dir", str(candidate),
            "--manifest", str(manifest_file), "--require-complete-same-raw"]
    assert main(argv) == 0
    capsys.readouterr()

def test_one_changed_mode_fails_closed(tmp_path, capsys):
    reference, candidate, manifest, manifest_file = _make_pair(
        tmp_path, full=True, mismatch=True)
    result = compare_original_mode2_pair(reference, candidate,
        files=manifest["files"], session_id=manifest["session_id"],
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin")
    assert not result["strict_same_raw_file_evidence_complete"]
    assert main(["--reference-dir", str(reference),
                 "--candidate-dir", str(candidate), "--manifest", str(manifest_file),
                 "--require-complete-same-raw"]) == 3
    capsys.readouterr()

def test_missing_getsignal_rejects_otherwise_complete_same_raw(tmp_path):
    reference, candidate, manifest, _manifest_file = _make_pair(tmp_path, full=True)
    without_signal = [x for x in manifest["files"]
                      if x["kind"] != "GETSIGNAL_F32"]
    result = compare_original_mode2_pair(reference, candidate,
        files=without_signal, session_id=manifest["session_id"],
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin")
    assert result["all_pairs_byte_identical"]
    assert result["source_same_raw_four_mode_numeric_comparison_complete"]
    assert result["source_write_data_values_output_families_supplied"]
    assert not result["strict_getsignal_pair_supplied"]
    assert not result["strict_same_raw_file_evidence_complete"]
