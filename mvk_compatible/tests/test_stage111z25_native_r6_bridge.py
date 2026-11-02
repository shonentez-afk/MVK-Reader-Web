"""Stage111Z.25: no-hardware tests of the already proven Native R6.1 bridge."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from mvk_compatible.core.native_r6_bridge import (
    CaptureSpec, EXPORT_DIR, EXPORT_ZIP, NATIVE_EXE, NATIVE_SHA_FILE,
    STOP_REQUEST, native_executable, pack_completed_export,
    request_graceful_stop, validate_ipv4,
)
from .test_offline_core import fixture_zip


def test_native_executable_bundled_and_hash_guard(tmp_path):
    folder = tmp_path / "mvk_native"
    folder.mkdir()
    exe = folder / NATIVE_EXE
    data = b"MZ" + b"synthetic offline fixture"
    exe.write_bytes(data)
    (folder / NATIVE_SHA_FILE).write_text(hashlib.sha256(data).hexdigest(),
                                          encoding="ascii")
    assert native_executable(tmp_path) == exe
    exe.write_bytes(data + b"changed")
    with pytest.raises(ValueError, match="сумма"):
        native_executable(tmp_path)


def test_capture_args_consent_and_stop_file_are_local(tmp_path):
    spec = CaptureSpec("10.13.42.84", "10.13.42.22", 30, 256, tmp_path)
    root = spec.create_root()
    args = spec.native_args(root)
    assert args[:4] == ["-ip", "10.13.42.84", "-local-ip", "10.13.42.22"]
    assert "-approve=true" in args and "-export=true" in args
    assert args[-2] == "-stop-file"
    assert Path(args[-1]) == root / STOP_REQUEST
    assert not (root / STOP_REQUEST).exists()
    request_graceful_stop(root)
    assert (root / STOP_REQUEST).read_text(encoding="ascii") == "STOP\n"
    with pytest.raises(ValueError, match="Устаревший"):
        spec.native_args(root)
    with pytest.raises(FileExistsError):
        request_graceful_stop(root)


@pytest.mark.parametrize("invalid", [
    "", "127.0.0.1", "0.0.0.0", "224.0.0.1",
    "255.255.255.255", "192.168.01.12", "10.0.0.1:10230", " 10.0.0.1",
])
def test_invalid_ip_fails_before_any_device_connection(invalid):
    with pytest.raises(ValueError):
        validate_ipv4(invalid, field="IP прибора")


def synthetic_completed_run(tmp_path):
    """Mimic authentic *layout* of a Go export without a device or its data."""
    fixture = fixture_zip(tmp_path)
    root = tmp_path / "private_capture"
    run = root / "MVK_test_synthetic"
    export = run / EXPORT_DIR
    export.mkdir(parents=True)
    with zipfile.ZipFile(fixture) as z:
        for item in z.namelist():
            (export / item).write_bytes(z.read(item))
    aux = export / "aux4700.jsonl"
    aux.rename(run / "aux4700.jsonl")
    (export / "AUX_PROVENANCE.json").unlink()
    raw = run / "incoming.raw"
    raw.write_bytes(b"offline-only test raw data, not an instrument capture")
    sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    audit_path = export / "EXPORT_AUDIT.json"
    audit = json.loads(audit_path.read_text())
    audit["source_raw_sha256"] = sha
    timeline = b"[]\n"
    (export / "TIMELINE.json").write_bytes(timeline)
    audit["output_file_sha256"]["TIMELINE.json"] = hashlib.sha256(timeline).hexdigest()
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    status = {"state": "EXPORTED", "capture_end_reason": "DURATION_REACHED",
              "source_raw_sha256": sha, "output_directory": EXPORT_DIR,
              "during_capture_bin_spool_verified": True, "adc_bin_files": 8}
    (run / "STAGE108_EXPORT_STATUS.json").write_text(json.dumps(status),
                                                       encoding="utf-8")
    return root, run, audit_path


def test_completed_native_export_opens_in_existing_qt_offline_core(tmp_path):
    from mvk_compatible.core import OfflineSession
    root, run, _ = synthetic_completed_run(tmp_path)
    original_raw = (run / "incoming.raw").read_bytes()
    archive = pack_completed_export(root)
    assert archive == run / EXPORT_ZIP
    assert (run / "incoming.raw").read_bytes() == original_raw
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 22  # 19 manifest files + audit + AUX + provenance
        assert "AUX_PROVENANCE.json" in z.namelist()
    session = OfflineSession.open(archive)
    assert session.calculations()["peak_metrics_available"]
    assert len(session.samples(1)[0]) >= 1024
    with pytest.raises(ValueError, match="уже существует"):
        pack_completed_export(root)


def test_tampered_native_bin_refuses_publication(tmp_path):
    root, run, audit_path = synthetic_completed_run(tmp_path)
    audit = json.loads(audit_path.read_text())
    first = next(n for n in audit["output_file_sha256"] if n.endswith(".bin"))
    with (run / EXPORT_DIR / first).open("ab") as handle:
        handle.write(b"evil")
    with pytest.raises(ValueError, match="сумма"):
        pack_completed_export(root)
    assert (run / "incoming.raw").is_file()
    assert not (run / EXPORT_ZIP).exists()


def test_failed_closed_export_is_never_opened(tmp_path):
    root, run, _ = synthetic_completed_run(tmp_path)
    p = run / "STAGE108_EXPORT_STATUS.json"
    status = json.loads(p.read_text())
    status["state"] = "FAILED_CLOSED"
    p.write_text(json.dumps(status), encoding="utf-8")
    with pytest.raises(ValueError, match="не подтвердил"):
        pack_completed_export(root)
