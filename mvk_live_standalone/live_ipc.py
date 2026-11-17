"""Authenticated, single-consumer local IPC client for Native R6.1 Go rings.

This code never creates a socket to the MVK01. It connects ONLY to
127.0.0.1:the explicitly published random port, with the one-session token
from a restricted file in the approved recorder session directory.
No HTTP redirect, environment proxy, external device command or raw gain.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re

import numpy as np

from .live_ring import DOMAIN

SCHEMA = "MVK_NATIVE_CALIBRATED_IPC_V1"
NAME = "MVK_NATIVE_LIVE_IPC.json"
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
RATES = frozenset((512, 2048, 8192, 32768, 65536))
MAX_SAMPLES = 262144
UINT32 = 1 << 32


class IPCNotReady(ValueError):
    """The receiver is healthy but no contiguous calibrated window exists."""


@dataclass(frozen=True)
class IPCChannel:
    number: int
    rate_hz: int
    samples: np.ndarray
    next_index: int
    captured_samples: int
    sha256: str


@dataclass(frozen=True)
class IPCPreview:
    session_id: str
    input_domain: str
    provisional: bool
    updated_utc: datetime
    channels: dict[int, IPCChannel]


@dataclass(frozen=True)
class LocalIPC:
    port: int
    token: str
    session_id: str

    def read_channel(self, adc: int, count: int) -> IPCPreview:
        if type(adc) is not int or not 1 <= adc <= 8:
            raise ValueError("Invalid ADC number")
        if type(count) is not int or not 1 <= count <= MAX_SAMPLES:
            raise ValueError("Invalid bounded IPC window")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=0.55)
        try:
            path = f"/v1/adc/{adc}/window?count={count}"
            connection.request("GET", path, headers={
                "Authorization": "Bearer " + self.token,
                "Host": f"127.0.0.1:{self.port}",
                "Connection": "close",
                "Accept": "application/octet-stream",
            })
            reply = connection.getresponse()
            if reply.status == 409:
                raise IPCNotReady("Ожидание непрерывного откалиброванного окна АЦП")
            if reply.status != 200:
                raise ValueError(f"Local Native IPC refused request ({reply.status})")
            # Never allocate for a forged 64-bit content length or gzip.
            if reply.getheader("Content-Encoding") is not None:
                raise ValueError("Compressed IPC data not allowed")
            if reply.getheader("Content-Length") != str(count * 4):
                raise ValueError("IPC payload size differs from requested Float32")
            if reply.getheader("X-MVK-Schema") != SCHEMA:
                raise ValueError("Unknown Native IPC schema")
            if reply.getheader("X-MVK-Session") != self.session_id:
                raise ValueError("Wrong Native recording session")
            if reply.getheader("X-MVK-Domain") != DOMAIN:
                raise ValueError("Native source is not calibrated")
            if reply.getheader("X-MVK-ADC") != str(adc) or reply.getheader("X-MVK-Count") != str(count):
                raise ValueError("Native channel/count mismatch")
            if reply.getheader("Content-Type") != "application/octet-stream":
                raise ValueError("Unexpected Native IPC body type")

            def number_header(name: str, maximum: int) -> int:
                raw = reply.getheader(name)
                if raw is None or not raw.isdecimal() or len(raw) > 20:
                    raise ValueError(f"Malformed Native header {name}")
                value = int(raw)
                if value < 0 or value > maximum:
                    raise ValueError(f"Native {name} outside valid range")
                return value

            rate = number_header("X-MVK-Rate", 1_000_000)
            end = number_header("X-MVK-RxPos", (1 << 64) - 1)
            next_index = number_header("X-MVK-NextIndex", UINT32 - 1)
            available = number_header("X-MVK-Available", 1 << 21)
            first = number_header("X-MVK-FirstReadable", (1 << 64) - 1)
            sha = reply.getheader("X-MVK-SHA256", "")
            if (
                rate not in RATES or end < count or available < count
                or first > end or end - first != available
                or not _HEX64.fullmatch(sha)
            ):
                raise ValueError("Native IPC inconsistent source ring receipt")
            raw = reply.read(count * 4 + 1)
            if len(raw) != count * 4:
                raise ValueError("Native IPC truncated/oversized Float32 payload")
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("Native IPC bytes fail SHA256")
            data = np.frombuffer(raw, dtype="<f4").copy()
            if not np.all(np.isfinite(data)):
                raise ValueError("Native IPC contains nonfinite calibrated ADC")
            channel = IPCChannel(adc, rate, data, next_index, end, sha)
            return IPCPreview(
                self.session_id, DOMAIN, True, datetime.now(timezone.utc),
                {adc: channel},
            )
        finally:
            connection.close()


def discover_local_ipc(capture_root: str | Path, status: dict) -> LocalIPC | None:
    """Locate the IPC secret only within the already validated Native run.

    Caller must use the live status validated by native_r6_live_status, not
    untrusted raw JSON. Never use a host or URL supplied by the descriptor.
    """
    if (
        status.get("phase") != "RECORDING" or status.get("capture_only")
        or status.get("invalid_frames") or status.get("snapshot_stale")
        or status.get("source_tcp_multi_socket")
        or status.get("source_rate_transition_during_live")
        or status.get("read_only_no_app_payload_sent") is not True
    ):
        return None
    if status.get("seconds_since_last_packet") is not None and status["seconds_since_last_packet"] > 4:
        return None
    root = Path(capture_root)
    run = Path(status["run_directory"])
    if (
        root.is_symlink() or not root.is_dir()
        or run.is_symlink() or not run.is_dir()
        or run.parent.resolve() != root.resolve()
        or run.name != status.get("session_id")
    ):
        raise ValueError("Native IPC run directory differs from verified capture")
    f = run / NAME
    if not f.exists():
        return None  # old accepted Native R6.1 without opt-in local IPC
    if f.is_symlink() or not f.is_file() or f.stat().st_size > 4096:
        raise ValueError("Unsafe local IPC descriptor")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Corrupt local IPC descriptor") from exc
    if not isinstance(doc, dict) or (
        doc.get("schema") != SCHEMA or doc.get("session_id") != run.name
        or doc.get("host") != "127.0.0.1"
        or doc.get("source_domain") != DOMAIN
        or doc.get("read_only") is not True
        or doc.get("max_window_samples") != MAX_SAMPLES
    ):
        raise ValueError("Unrecognized Native local IPC contract")
    port, token = doc.get("port"), doc.get("token")
    if (
        type(port) is not int or not 1 <= port <= 65535 or
        not isinstance(token, str) or not _HEX64.fullmatch(token)
    ):
        raise ValueError("Invalid session-bound loopback endpoint")
    return LocalIPC(port=port, token=token, session_id=run.name)
