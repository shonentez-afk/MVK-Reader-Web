"""Stage111Z.26: validated offline snapshots of the already-running Native R6.1.

NO sockets; never decodes instrument commands. The producer is the sole Go
TCP/10230 client. A live JSON snapshot is NOT the audited final BIN/TSXML and
never makes a provisional waveform a certified MVKView measurement.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

SCHEMA = "MVK_NATIVE_R6_LIVE_STATUS_V1"
FILENAME = "MVK_NATIVE_LIVE_STATUS.json"
PHASES = frozenset({"CONNECTING", "RECORDING", "VERIFYING", "COMPLETED", "REFUSED"})
_MAX_STATUS_BYTES = 128_000
_RUN_RE = re.compile(r"TEST_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.\d{3}(?:_\d+)?\Z")
_DSP_RE = re.compile(r"0x[0-9A-F]{8}\Z")


def _positive_int(value, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Native live status: invalid {name}")
    return value


def _utc_stamp(value: str, name: str) -> datetime:
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError(f"Native live status: invalid {name}")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Native live status: invalid {name}") from exc
    if result.tzinfo is None:
        raise ValueError(f"Native live status: timezone required for {name}")
    return result.astimezone(timezone.utc)


def _rate_list(value) -> list[int]:
    if not isinstance(value, list) or len(value) > 3:
        raise ValueError("Native live status: invalid frequency list")
    rates = [_positive_int(v, "sample rate") for v in value]
    if any(v == 0 or v > 1_000_000 for v in rates):
        raise ValueError("Native live status: invalid sample rate")
    return rates


def _channel_quality(ch: dict) -> str:
    if ch["sequence_discontinuities"] or ch["nonfinite_samples"] or len(ch["sample_rates_hz"]) > 1:
        return "ОШИБКА ПОТОКА"
    if ch["samples"] == 0:
        return "НЕТ ДАННЫХ"
    if ch["type"] == "TACH":
        return "ПОТОК ПОЛУЧЕН"
    code = ch["dsp_sensor_status_hex"]
    if code is None:
        return "DSP НЕ ПОЛУЧЕН"
    return "DSP: OK (0x0)" if code == "0x00000000" else "DSP: ПРЕДУПРЕЖДЕНИЕ"


def validate_live_status(payload: dict, *, expected_run: str,
                         instrument_ipv4: str | None = None,
                         local_ipv4: str | None = None,
                         now: datetime | None = None) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Native live status: unknown schema")
    if payload.get("session_id") != expected_run:
        raise ValueError("Native live status: session identity mismatch")
    if payload.get("phase") not in PHASES:
        raise ValueError("Native live status: unexpected phase")
    if payload.get("read_only_no_app_payload_sent") is not True:
        raise ValueError("Native live status: receiver not marked read-only")
    if instrument_ipv4 is not None and payload.get("instrument_ipv4") != instrument_ipv4:
        raise ValueError("Native live status: different MVK device")
    selected = payload.get("selected_local_ipv4")
    if local_ipv4 is not None and selected not in ("", local_ipv4):
        raise ValueError("Native live status: different Ethernet adapter")
    ts = _utc_stamp(payload.get("updated_utc"), "updated_utc")
    dt = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = max(0.0, (dt-ts).total_seconds())
    if age > 30*24*3600:
        raise ValueError("Native live status: stale data from another capture")
    for key in ("raw_bytes", "frames_decoded", "invalid_frames", "aux4700_updates",
                "full_register_snapshots", "warning_count", "target_seconds"):
        _positive_int(payload.get(key), key)
    elapsed = payload.get("elapsed_seconds")
    if type(elapsed) not in (float, int) or not 0 <= elapsed < 365*24*3600:
        raise ValueError("Native live status: invalid elapsed time")
    if type(payload.get("capture_only")) is not bool:
        raise ValueError("Native live status: invalid capture_only")
    silent = payload.get("seconds_since_last_packet")
    if silent is not None and (type(silent) not in (float, int) or not 0 <= silent <= 365*24*3600):
        raise ValueError("Native live status: invalid packet age")
    channels = payload.get("channels")
    if not isinstance(channels, list) or len(channels) != 10:
        raise ValueError("Native live status: expected 8 ADC + 2 TACH")
    safe = []
    for number, entry in enumerate(channels, 1):
        if not isinstance(entry, dict) or entry.get("channel") != number:
            raise ValueError("Native live status: mixed channel order")
        typ = "ADC" if number <= 8 else "TACH"
        if entry.get("type") != typ:
            raise ValueError("Native live status: invalid channel type")
        record = {"channel": number, "type": typ}
        for field in ("frames", "samples", "sequence_discontinuities", "nonfinite_samples"):
            record[field] = _positive_int(entry.get(field), field)
        record["sample_rates_hz"] = _rate_list(entry.get("sample_rates_hz"))
        status = entry.get("dsp_sensor_status_hex")
        if status is not None and (typ != "ADC" or not isinstance(status, str)
                                    or _DSP_RE.fullmatch(status) is None):
            raise ValueError("Native live status: invalid measured DSP status")
        record["dsp_sensor_status_hex"] = status
        record["quality"] = _channel_quality(record)
        safe.append(record)
    result = dict(payload)
    result["channels"] = safe
    result["snapshot_age_s"] = age
    result["snapshot_stale"] = age > 5.0 and result["phase"] in ("CONNECTING", "RECORDING")
    result["quality_alert"] = (
        result["capture_only"] or result["invalid_frames"] > 0 or
        result["snapshot_stale"] or
        (silent is not None and silent > 4.0) or
        any(ch["quality"] in ("ОШИБКА ПОТОКА", "DSP: ПРЕДУПРЕЖДЕНИЕ") for ch in safe))
    return result


def load_capture_live_status(capture_root: str | Path, *,
                             instrument_ipv4: str | None = None,
                             local_ipv4: str | None = None,
                             now: datetime | None = None) -> dict | None:
    """Find only one local run in the unique GUI root; None until Go starts it.

    Never reads BIN/RAW or follows symlinks. Atomic Go rename ensures the
    parser cannot read a partially serialized JSON snapshot.
    """
    root = Path(capture_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Native live root must be a local regular directory")
    runs = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
            and _RUN_RE.fullmatch(p.name) and (p / FILENAME).exists()]
    if not runs:
        return None
    if len(runs) != 1:
        raise ValueError("Native live: multiple run directories; cannot mix sessions")
    run = runs[0]
    path = run / FILENAME
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_STATUS_BYTES:
        raise ValueError("Native live: status file missing/too large/symlink")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Native live: invalid atomic status JSON") from exc
    result = validate_live_status(payload, expected_run=run.name,
                                  instrument_ipv4=instrument_ipv4,
                                  local_ipv4=local_ipv4, now=now)
    result["run_directory"] = str(run)
    return result
