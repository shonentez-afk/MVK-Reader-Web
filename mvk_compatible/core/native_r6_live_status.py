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

from .original_mode2_rx_evidence import FIELDS as SOURCE_RX_FIELDS
from .original_mode2_status_cells import parse_source_cells
from .original_mode2_transmit_evidence import validate_original_task2_tx
from .original_mode2_retry_timing import SOURCE_BACKOFF_WAITS_MS
from .original_mode2_active_tx_provenance import verify_source_native_tx_origin
from .original_system_register_fields import verify_source_error_overlap

SCHEMA = "MVK_NATIVE_R6_LIVE_STATUS_V1"
_SOURCE_TCP_RETRY_CAUSES = frozenset((
    "CONNECT_FAILED", "REMOTE_DISCONNECTED",
    "SOURCE_READ_TIMEOUT", "SOCKET_READ_FAILED",
))
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
    if not isinstance(value, list) or len(value) > 5:
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
    physical_source_tx=verify_source_native_tx_origin(payload)
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
    # 0 is the original-unbounded mode; negative/oversized durations
    # cannot come from the approved native CLI contract.
    if payload["target_seconds"] > 300:
        raise ValueError("Native live status: unsupported capture duration")
    # New read-only Go producer publishes the three counters atomically.
    # Old statuses lacking all three remain valid but UNKNOWN; a partial
    # set, rollback, or synthetic overcount cannot claim Delphi readiness.
    source_fields=[key in payload for key in SOURCE_RX_FIELDS]
    source_values_ticks=payload.get("source_values_ticks_address_3100")
    if source_values_ticks is not None and (
            _positive_int(source_values_ticks,"source address 0x3100 VALUES ticks")
            >payload["frames_decoded"]):
        raise ValueError("Native source VALUES ticks exceed decoded frames")
    if any(source_fields) and not all(source_fields):
        raise ValueError("Native live status: partial source RX evidence")
    if all(source_fields):
        counts=[_positive_int(payload[key], key) for key in SOURCE_RX_FIELDS]
        if sum(counts)>payload["frames_decoded"]:
            raise ValueError("Native live status: RX counters exceed decoded frames")
    # The same passive Go monitor exposes 14 IDP-verified StatusCells.
    # Each DWORD requires *two* observed uint16 register words; a missing
    # cell is null/UNKNOWN, never the source Delphi FF init sentinel.
    status_cells=parse_source_cells(payload)
    verify_source_error_overlap(payload)
    validated_source_tx=validate_original_task2_tx(payload)
    tcp_keys=("source_tcp_connection_count","source_tcp_multi_socket",
              "source_tcp_reconnects_after_raw")
    tcp_present=[k in payload for k in tcp_keys]
    if any(tcp_present) and not all(tcp_present):
        raise ValueError("Partial original source TCP reconnection evidence")
    if all(tcp_present):
        tcp_count=_positive_int(payload[tcp_keys[0]],tcp_keys[0])
        tcp_multi=payload[tcp_keys[1]]
        tcp_retries=_positive_int(payload[tcp_keys[2]],tcp_keys[2])
        if (type(tcp_multi) is not bool or tcp_multi!=(tcp_count>1)
                or tcp_count>128 or tcp_retries>100000
                or (tcp_retries>0 and tcp_count==0)):
            raise ValueError("Contradictory source TCP connection/retry proof")
    else:
        tcp_count=0
        tcp_multi=False
        tcp_retries=0
    # Local original Task2 network retry evidence; not a Delphi device
    # status register, file row, source command or vendor error text.
    retry_keys=("source_initial_retry_attempts","source_retry_wait_ms",
                "source_reconnect_approved")
    retry_present=[key in payload for key in retry_keys]
    if any(retry_present) and not all(retry_present):
        raise ValueError("Partial source Task2 TCP retry evidence")
    if all(retry_present):
        retry_attempts=_positive_int(payload[retry_keys[0]],retry_keys[0])
        retry_wait=_positive_int(payload[retry_keys[1]],retry_keys[1])
        approved=payload[retry_keys[2]]
        reason=payload.get("source_retry_last_error","")
        if (type(approved) is not bool or
                not isinstance(reason,str) or retry_attempts>100_000 or
                (retry_attempts==0 and (retry_wait!=0 or reason)) or
                (retry_attempts>0 and
                    (reason not in _SOURCE_TCP_RETRY_CAUSES or
                     retry_wait not in SOURCE_BACKOFF_WAITS_MS)) or
                (tcp_retries>0 and not approved)):
            raise ValueError("Contradictory original Task2 TCP retry evidence")
    else:
        retry_attempts=0
        retry_wait=0
        approved=False
        reason=""
    rate_transition=payload.get("source_rate_transition_during_live",False)
    if type(rate_transition) is not bool:
        raise ValueError("Invalid real Task2 rate transition flag")
    source_system_error=bool(status_cells and status_cells[0].valid
                             and status_cells[0].value>0)
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
        # Source SampleHeader.Index is an ABSOLUTE device cursor,
        # distinct from "samples" counted since this TCP capture began.
        # Older Go sidecars without this new field remain unverified,
        # never receive an invented index zero.
        next_index=entry.get("next_sample_index")
        if next_index is not None and (
                type(next_index) is not int or
                not 0<=next_index<2**32 or record["samples"]==0):
            raise ValueError("Native live status: invalid absolute sample index")
        record["next_sample_index"]=next_index
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
    result["source_system_error_observed"] = source_system_error
    result["source_original_setrate_physically_sent"] = physical_source_tx
    result["source_rate_transition_during_live"] = rate_transition
    result["source_values_ticks_address_3100"] = source_values_ticks
    result["source_tcp_connection_count"] = tcp_count
    result["source_tcp_multi_socket"] = tcp_multi
    result["source_tcp_reconnects_after_raw"] = tcp_retries
    result["source_initial_retry_attempts"] = retry_attempts
    result["source_retry_wait_ms"] = retry_wait
    result["source_reconnect_approved"] = approved
    result["source_retry_last_error"] = reason
    result["source_retry_evidence_verified"] = all(retry_present)
    result["original_source_tx_proof"] = (
        validated_source_tx.receipt() if validated_source_tx is not None else None)
    result["snapshot_age_s"] = age
    result["snapshot_stale"] = age > 5.0 and result["phase"] in ("CONNECTING", "RECORDING")
    result["quality_alert"] = (
        result["capture_only"] or result["invalid_frames"] > 0 or
        result["snapshot_stale"] or
        (silent is not None and silent > 4.0) or
        (all(source_fields) and payload[SOURCE_RX_FIELDS[2]]>0) or
        source_system_error or rate_transition or tcp_multi or
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
