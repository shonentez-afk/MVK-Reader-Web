"""Optional consent-gated Frida x86 trace, no x32dbg or human breakpoints.

The original executable on disk is never modified. Interceptor.attach DOES patch
process memory temporarily, so this mode is not read-only in the strict sense.
All sites are checked for exact original opcode bytes before attaching ANY hooks.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import queue
import struct
import threading
from typing import Any
from .config import CaptureError


@dataclass(frozen=True)
class TraceSite:
    name: str
    original_va: int
    signature: str

    @property
    def rva(self) -> int:
        return self.original_va - 0x00400000


# The six signatures come from the prior operator-approved Z31R CHECK_READY.
# They are machine code checkpoints, NOT function entrypoints.
SITES = (
    TraceSite("pre_dc", 0x007D14AA, "8b4b04"),
    TraceSite("after_dc", 0x007D14B8, "8b4308"),
    TraceSite("pre_fft", 0x007D153D, "8b4b04"),
    TraceSite("power_before_mode", 0x007D154B, "8b4328"),
    TraceSite("power_after_mode_y", 0x007D17E7, "33c0"),
    TraceSite("summary", 0x007D1900, "33c0"),
)
MAX_MESSAGE_BYTES = 1_048_576
MAX_PENDING_FRIDA_EVENTS = 4096


def image_identity(path: str | Path) -> dict:
    """Check a user-selected PE image is ordinary x86 MVKView before injection.

    This is a static identity check, not a substitute for all six runtime bytes.
    """
    p = Path(path)
    if p.name.casefold() != "mvkview.exe" or not p.is_file():
        raise CaptureError("Frida requires the selected mvkview.exe image")
    if not 1024 <= p.stat().st_size <= 64 * 1024 * 1024:
        raise CaptureError("Unexpected MVKView executable size")
    with p.open("rb") as stream:
        dos = stream.read(64)
        if len(dos) < 64 or dos[:2] != b"MZ":
            raise CaptureError("Not a PE/MZ image")
        off = struct.unpack_from("<I", dos, 0x3C)[0]
        if off > 1_048_576:
            raise CaptureError("Malformed PE offset")
        stream.seek(off)
        pe = stream.read(128)
    if pe[:4] != b"PE\0\0" or len(pe) < 64:
        raise CaptureError("Not a valid Windows PE image")
    if struct.unpack_from("<H", pe, 4)[0] != 0x014C:
        raise CaptureError("Only the original 32-bit x86 image is supported")
    if struct.unpack_from("<H", pe, 24)[0] != 0x010B:
        raise CaptureError("PE32 expected")
    image_base = struct.unpack_from("<I", pe, 24 + 28)[0]
    if image_base != 0x00400000:
        raise CaptureError("Unexpected PE32 ImageBase; original trace offsets unverified")
    h = sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1_048_576), b""):
            h.update(chunk)
    return {"exe_sha256": h.hexdigest(), "image_base": "0x00400000",
            "pe_machine": "I386", "image_size_bytes": p.stat().st_size}


def javascript_source(*, full_arrays=False) -> str:
    if type(full_arrays) is not bool:
        raise CaptureError("full_arrays must be bool")
    asset = Path(__file__).with_name("frida_trace.js")
    source = asset.read_text(encoding="utf-8")
    points = [{"name": x.name, "rva": x.rva, "signature": x.signature} for x in SITES]
    return source.replace("__MVK_SITES_JSON__", json.dumps(points, separators=(",", ":"))).replace(
        "__MVK_ARRAYS_BOOL__", "true" if full_arrays else "false")


class FridaTraceObserver:
    """Record only one verified MVKView PID, with explicit operator consent.

    The observer forwards tiny records and bounded raw samples to the session
    queue. It never calls Frida to resume, step, write data or control UI.
    """
    def __init__(self, pid: int, output: queue.Queue, exe_path: str,
                 *, full_arrays=False, frida_module=None):
        self.pid, self.output, self.exe_path = pid, output, exe_path
        self.full_arrays = full_arrays
        self.frida = frida_module
        self.session = None
        self.script = None
        self.ready = threading.Event()
        self.error = None
        self.identity = None
        self.received = 0
        self.dropped = 0

    def _message(self, message: dict, data: bytes | None):
        if message.get("type") == "error":
            self.error = str(message.get("description") or "Frida script error")[:500]
            self.ready.set()
            return
        if message.get("type") != "send":
            return
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        kind = payload.get("kind")
        if kind == "ready":
            if payload.get("architecture") != "ia32" or payload.get("hook_count") != len(SITES):
                self.error = "Trace startup did not verify all x86 sites"
            self.ready.set()
            return
        if kind == "trace_error":
            self.error = str(payload.get("reason") or "Unknown trace failure")[:500]
            self.ready.set()
            return
        if kind not in ("hit", "array", "trace_end"):
            return
        if not isinstance(payload.get("site"), str) or payload["site"] not in {
                x.name for x in SITES}:
            return
        if data is not None and (not isinstance(data, bytes) or len(data) > MAX_MESSAGE_BYTES):
            self.dropped += 1
            return
        # Keep only fields from our fixed schema; not arbitrary JS/AI payload.
        allowed = {"kind", "site", "timestamp_ms", "thread_id", "registers",
                   "params_hex", "stack_hex", "storage_hex", "n", "mode",
                   "envelope_code", "array_type", "byte_length", "reason"}
        filtered = {key: value for key, value in payload.items() if key in allowed}
        try:
            self.output.put_nowait({"source": "frida", "payload": filtered,
                                    "binary": data})
            self.received += 1
        except queue.Full:
            self.dropped += 1

    def start(self):
        self.identity = image_identity(self.exe_path)
        if self.frida is None:
            try:
                import frida
            except ImportError as exc:
                raise CaptureError("Frida is not installed. Install Windows Frida package or use a Frida-enabled build") from exc
            self.frida = frida
        try:
            self.session = self.frida.attach(self.pid)
            self.script = self.session.create_script(javascript_source(full_arrays=self.full_arrays))
            self.script.on("message", self._message)
            self.script.load()
            if not self.ready.wait(timeout=10.0):
                raise CaptureError("Frida trace failed readiness handshake within 10 seconds")
            if self.error:
                raise CaptureError("Frida trace not started: " + self.error)
        except Exception as exc:
            self.stop()
            if isinstance(exc, CaptureError):
                raise
            raise CaptureError("Frida attach failed: " + type(exc).__name__ + ": " + str(exc)[:240]) from exc
        return {"profile": "original_getspectrum_6points", "sites": len(SITES),
                "arrays": self.full_arrays, **self.identity}

    def stop(self):
        if self.script is not None:
            try:
                self.script.unload()
            except Exception:
                pass
            self.script = None
        if self.session is not None:
            try:
                self.session.detach()
            except Exception:
                pass
            self.session = None