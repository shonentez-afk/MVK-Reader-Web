"""Strict same-RX evidence gate: synthetic fixtures never certify hardware."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pytest
from ..core.original_mode2_source_files import (
    build_original_tsxml_compatible, source_data_filename,
)
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
        "VALUES_CSV", "TABLE_CSV",
        "GETSIGNAL_F32",
        "GETSPECTRUM_PRE_HANN_F32", "GETSPECTRUM_WINDOWED_F32",
        "GETSPECTRUM_FFT_COMPLEX_F32", "GETSPECTRUM_POWER_F32",
    ] if full else ["GETSPECTRUM_Y_F32"]
    descriptors = []
    for idx, kind in enumerate(kinds):
        name = f"pair{idx}.dat"
        body = (np.arange(8, dtype="<f4") + idx).tobytes() if kind not in (
            "VALUES_CSV", "TABLE_CSV") else b"same file bytes"
        (reference / name).write_bytes(body)
        (candidate / name).write_bytes(body)
        descriptors.append(dict(kind=kind, reference_name=name, candidate_name=name))
    if full:
        # The original reads the local clock inside its per-channel open loop.
        # Adjacent filename timestamps may differ; XML uses its own close clock.
        close = datetime(2026, 11, 25, 0, 0, 10, tzinfo=timezone.utc)
        for ch, label, kind, start, binary in (
                (1, "ADC1", "ADC_BIN_F32",
                 datetime(2026, 11, 24, 23, 59, 59, tzinfo=timezone.utc),
                 np.arange(8, dtype="<f4").tobytes()),
                (9, "TACH1", "TACH_BIN_BYTES",
                 datetime(2026, 11, 25, 0, 0, 0, tzinfo=timezone.utc),
                 bytes((0, 255, 1, 16, 128)))):
            basename = source_data_filename(device="МВК-ТЕСТ", channel_label=label,
                                            when=start)
            xml, _proof = build_original_tsxml_compatible(
                channel=ch, binary_basename=basename, size_bytes=len(binary),
                rate_hz=65536, local_time=close, device_label="МВК-ТЕСТ",
                channel_label=label)
            for name, body, role in ((basename, binary, kind),
                    (basename+".tsxml", xml, "TSXML_CP1251")):
                for folder in (reference, candidate):
                    (folder / name).write_bytes(body)
                descriptors.append(dict(kind=role, reference_name=name,
                                        candidate_name=name, source_writer_channel=ch))
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
    if full:
        manifest["write_data_channels"] = [1, 9]
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    return reference, candidate, manifest, manifest_file

def test_incomplete_identical_pairs_must_fail_strict_cli(tmp_path, capsys):
    reference, candidate, manifest, manifest_file = _make_pair(tmp_path, full=False)
    result = compare_original_mode2_pair(reference, candidate,
        files=manifest["files"], session_id=manifest["session_id"],
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin",
        write_data_channels=manifest.get("write_data_channels"))
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
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin",
        write_data_channels=manifest.get("write_data_channels"))
    assert result["strict_same_raw_file_evidence_complete"]
    coverage = result["source_write_data_channel_coverage"]
    assert coverage["expected_channels"] == [1, 9]
    assert coverage["reference_bin_channel_and_clock_patterns_complete"]
    assert coverage["all_selected_channel_pairs_structurally_bound"]
    assert not coverage["reference_file_runtime_clock_verified"]
    assert "МВК-ТЕСТ" not in json.dumps(coverage, ensure_ascii=False)
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
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin",
        write_data_channels=manifest.get("write_data_channels"))
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
        reference_raw_name="raw.bin", candidate_raw_name="raw.bin",
        write_data_channels=manifest.get("write_data_channels"))
    assert result["all_pairs_byte_identical"]
    assert result["source_same_raw_four_mode_numeric_comparison_complete"]
    assert result["source_write_data_values_output_families_supplied"]
    assert not result["strict_getsignal_pair_supplied"]
    assert not result["strict_same_raw_file_evidence_complete"]


def _strict_result(reference, candidate, manifest):
    return compare_original_mode2_pair(reference, candidate, **manifest)


def _writer_role(manifest, kind, channel):
    return next(row for row in manifest["files"] if row["kind"] == kind
                and row.get("source_writer_channel") == channel)


def test_equal_files_cannot_hide_absent_selected_tach_or_undeclared_channel(tmp_path):
    reference, candidate, manifest, _ = _make_pair(tmp_path, full=True)
    assert _strict_result(reference, candidate, manifest)["strict_same_raw_file_evidence_complete"]
    reduced = dict(manifest, files=[row for row in manifest["files"]
                                  if row.get("source_writer_channel") != 9])
    report = _strict_result(reference, candidate, reduced)
    assert report["all_pairs_byte_identical"]
    assert report["source_write_data_values_output_families_supplied"]
    assert not report["strict_same_raw_file_evidence_complete"]
    assert not report["source_write_data_channel_coverage"]["channels"][1]["bin_pair_supplied"]
    # ADC-only is valid when the operator actually declares ADC-only scope.
    assert _strict_result(reference, candidate, dict(
        reduced, write_data_channels=[1]))["strict_same_raw_file_evidence_complete"]
    # Do not silently ignore an additional tagged channel.
    report = _strict_result(reference, candidate, dict(manifest, write_data_channels=[1]))
    assert report["source_write_data_channel_coverage"]["unexpected_tagged_channels"] == [9]
    assert not report["strict_same_raw_file_evidence_complete"]
    # The old manifest still provides a byte comparison, not strict coverage.
    report = _strict_result(reference, candidate, dict(manifest, write_data_channels=None))
    assert report["all_pairs_byte_identical"]
    assert not report["strict_same_raw_file_evidence_complete"]


@pytest.mark.parametrize(("before", "after"), [
    (b"<ChannelNumber>9", b"<ChannelNumber>10"),
    (b"<RealDataType>Byte", b"<RealDataType>Single"),
    (b"<DataLength>5", b"<DataLength>4"),
    (b"<Units>Count", b"<Units>RPM"),
    (b'<To Units="ms">0.08', b'<To Units="ms">0.02'),
    (b".bin</DataFileName>", b".different.bin</DataFileName>"),
    (b"12:00:10 AM", b"99:00:10 AM"),
    (b"<MainRoot>", b"<!DOCTYPE MainRoot><MainRoot>"),
])
def test_identical_invalid_tsxml_does_not_supply_tach_role(tmp_path, before, after):
    reference, candidate, manifest, _ = _make_pair(tmp_path, full=True)
    entry = _writer_role(manifest, "TSXML_CP1251", 9)
    for root, key in ((reference, "reference_name"), (candidate, "candidate_name")):
        path = root / entry[key]
        original = path.read_bytes()
        assert before in original
        path.write_bytes(original.replace(before, after, 1))
    report = _strict_result(reference, candidate, manifest)
    assert report["all_pairs_byte_identical"]
    assert not report["strict_same_raw_file_evidence_complete"]
    assert not report["source_write_data_channel_coverage"]["channels"][1]["reference_tsxml_bound_to_bin"]


def test_wrong_role_or_duplicate_rejected_before_file_comparison(tmp_path):
    reference, candidate, manifest, _ = _make_pair(tmp_path, full=True)
    tach = _writer_role(manifest, "TACH_BIN_BYTES", 9)
    wrong = [dict(row, source_writer_channel=2) if row is tach else row
             for row in manifest["files"]]
    with pytest.raises(ValueError, match="channel/kind mismatched"):
        _strict_result(reference, candidate, dict(manifest, files=wrong))
    with pytest.raises(ValueError, match="duplicate WriteData"):
        _strict_result(reference, candidate, dict(manifest, files=[*manifest["files"], tach]))
    with pytest.raises(ValueError, match="unique channels"):
        _strict_result(reference, candidate, dict(manifest, write_data_channels=[1, 1]))


def test_candidate_open_and_close_clocks_report_separately(tmp_path):
    reference, candidate, manifest, _ = _make_pair(tmp_path, full=True)
    tach = _writer_role(manifest, "TACH_BIN_BYTES", 9)
    xml = _writer_role(manifest, "TSXML_CP1251", 9)
    old = tach["candidate_name"]
    new = old.replace("--00-00-00", "--00-00-02")
    (candidate / old).rename(candidate / new)
    xml_body = (candidate / xml["candidate_name"]).read_bytes()
    xml_body = xml_body.replace(old.encode("cp1251"), new.encode("cp1251"))
    (candidate / (new+".tsxml")).write_bytes(xml_body)
    tach["candidate_name"] = new
    xml["candidate_name"] = new+".tsxml"
    report = _strict_result(reference, candidate, manifest)
    row = report["source_write_data_channel_coverage"]["channels"][1]
    assert row["candidate_tsxml_bound_to_bin"]
    assert row["local_filename_clock_equal_for_pair"] is False
    assert row["local_tsxml_close_clock_equal_for_pair"] is True
    assert not report["all_pairs_byte_identical"]
    assert not report["strict_same_raw_file_evidence_complete"]
