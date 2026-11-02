"""Stage111Z.26: synthetic, entirely offline, one-receiver live-quality gate."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import pytest

from mvk_compatible.core.native_r6_live_status import (
    FILENAME, SCHEMA, load_capture_live_status, validate_live_status,
)


def fixture_state(*, phase="RECORDING"):
    return {
        "schema": SCHEMA, "phase": phase,
        "session_id": "TEST_2026-11-02_12-01-02.123",
        "updated_utc": "2026-11-02T09:01:05Z",
        "elapsed_seconds": 3.5, "target_seconds": 30,
        "instrument_ipv4": "10.13.42.84",
        "selected_local_ipv4": "10.13.42.22",
        "socket_remote": "10.13.42.84:10230",
        "read_only_no_app_payload_sent": True,
        "raw_bytes": 1_000_000, "frames_decoded": 1200,
        "invalid_frames": 0, "capture_only": False,
        "aux4700_updates": 4, "full_register_snapshots": 1,
        "warning_count": 0, "seconds_since_last_packet": 0.01,
        "last_aux_received_utc": "2026-11-02T09:01:04Z",
        "channels": [{
            "channel": i, "type": "ADC" if i <= 8 else "TACH",
            "frames": 300, "samples": 300*256 if i <= 8 else 300*64,
            "sample_rates_hz": [65536] if i <= 8 else [256],
            "sequence_discontinuities": 0, "nonfinite_samples": 0,
            "dsp_sensor_status_hex": ("0x00000000" if i <= 6 else
                                      "0x00000400" if i <= 8 else None),
        } for i in range(1, 11)],
    }


def now():
    return datetime(2026, 11, 2, 9, 1, 6, tzinfo=timezone.utc)


def test_live_adc7_adc8_alert_are_not_declared_healthy():
    obj = validate_live_status(fixture_state(),
                               expected_run="TEST_2026-11-02_12-01-02.123",
                               instrument_ipv4="10.13.42.84",
                               local_ipv4="10.13.42.22", now=now())
    assert obj["quality_alert"]
    assert obj["channels"][0]["quality"] == "DSP: OK (0x0)"
    assert obj["channels"][6]["quality"] == "DSP: ПРЕДУПРЕЖДЕНИЕ"
    assert obj["channels"][7]["dsp_sensor_status_hex"] == "0x00000400"
    assert obj["channels"][8]["quality"] == "ПОТОК ПОЛУЧЕН"
    assert obj["aux4700_updates"] == 4


def test_missing_aux_never_becomes_fake_ok():
    x = fixture_state()
    x["aux4700_updates"] = 0
    x["last_aux_received_utc"] = None
    for c in x["channels"][:8]:
        c["dsp_sensor_status_hex"] = None
    parsed = validate_live_status(x, expected_run=x["session_id"], now=now())
    assert parsed["channels"][0]["quality"] == "DSP НЕ ПОЛУЧЕН"
    assert parsed["channels"][7]["quality"] == "DSP НЕ ПОЛУЧЕН"


@pytest.mark.parametrize("change", [
    lambda x: x.update(read_only_no_app_payload_sent=False),
    lambda x: x.update(session_id="TEST_other"),
    lambda x: x.update(schema="unknown"),
    lambda x: x.update(raw_bytes=-1),
    lambda x: x.update(phase="PUBLISHING_UNVERIFIED"),
    lambda x: x["channels"].pop(),
    lambda x: x["channels"][8].update(type="ADC"),
    lambda x: x["channels"][0].update(dsp_sensor_status_hex="OK"),
    lambda x: x["channels"][0].update(sequence_discontinuities=-1),
    lambda x: x["channels"][0].update(sample_rates_hz=[-65536]),
])
def test_invalid_live_snapshot_fails_closed(change):
    state = fixture_state()
    change(state)
    with pytest.raises(ValueError):
        validate_live_status(state,
                             expected_run="TEST_2026-11-02_12-01-02.123",
                             now=now())


def test_stale_snapshot_and_packet_gap_mark_warning():
    data = fixture_state()
    data["seconds_since_last_packet"] = 5.1
    parsed = validate_live_status(data, expected_run=data["session_id"], now=now())
    assert parsed["quality_alert"]
    parsed = validate_live_status(data, expected_run=data["session_id"],
                                  now=now() + timedelta(seconds=6))
    assert parsed["snapshot_stale"]
    assert parsed["quality_alert"]


def test_local_file_is_read_only_and_session_bound(tmp_path):
    parent = tmp_path / "private"
    run = parent / "TEST_2026-11-02_12-01-02.123"
    run.mkdir(parents=True)
    state = fixture_state()
    payload = run / FILENAME
    payload.write_text(json.dumps(state), encoding="utf-8")
    result = load_capture_live_status(parent, instrument_ipv4="10.13.42.84",
                                      local_ipv4="10.13.42.22", now=now())
    assert result["run_directory"] == str(run)
    assert result["frames_decoded"] == 1200
    assert json.loads(payload.read_text()) == state  # reader never writes
    with pytest.raises(ValueError, match="different MVK"):
        load_capture_live_status(parent, instrument_ipv4="10.13.42.83", now=now())


def test_missing_file_not_a_phantom_live_connection(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    assert load_capture_live_status(root) is None


def test_status_symlink_rejected(tmp_path):
    root = tmp_path / "private"
    run = root / "TEST_2026-11-02_12-01-02.123"
    run.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(fixture_state()), encoding="utf-8")
    try:
        (run / FILENAME).symlink_to(outside)
    except OSError:
        pytest.skip("symlink requires elevated permissions on this Windows host")
    with pytest.raises(ValueError, match="symlink"):
        load_capture_live_status(root, now=now())
