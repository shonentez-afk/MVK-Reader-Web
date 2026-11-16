"""Import user-approved x32dbg event records; never control the debugger."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from .config import CaptureError
from .store import sha256_file

MAX_DEBUGGER_LOG = 32 * 1024 * 1024
MAX_DEBUGGER_LINES = 20000
ALLOWED_REGISTERS = ("eip", "eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp",
                     "eflags", "tid", "pid", "spectrum_mode", "envelope_code", "fft_n")
SAFE_MARKER = re.compile(r"(?:Z31R_[A-Za-z0-9_:.-]+|EIP\s*[=:]\s*(?:0x)?[0-9A-Fa-f]{6,8})")


def import_debugger_log(session, path):
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or not (0 < source.stat().st_size <= MAX_DEBUGGER_LOG):
        raise CaptureError("Debugger log must be an existing local file <= 32 MiB")
    if source.suffix.lower() not in {".jsonl", ".log", ".txt"}:
        raise CaptureError("Only JSONL or x32dbg plain-text logs are supported")
    digest = sha256_file(source)
    imported = 0
    with source.open("r", encoding="utf-8-sig", errors="replace") as stream:
        for ordinal, line in enumerate(stream, 1):
            if ordinal > MAX_DEBUGGER_LINES:
                session.store.event("debugger_import_truncated", {"max_lines": MAX_DEBUGGER_LINES})
                break
            line = line.rstrip("\r\n")
            if len(line) > 8192:
                continue
            evidence = None
            if source.suffix.lower() == ".jsonl":
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(data, dict):
                    continue
                # Preserve only expected x32dbg telemetry; unknown fields and
                # potentially sensitive raw memory are not imported.
                evidence = {str(k).lower(): v for k, v in data.items()
                            if str(k).lower() in ALLOWED_REGISTERS and
                            type(v) in (str, int, float)}
                if not evidence:
                    continue
            else:
                match = SAFE_MARKER.search(line)
                if not match:
                    continue
                evidence = {"marker": match.group(0), "line": ordinal}
            session.store.event("debugger_observation_imported", evidence)
            imported += 1
    record = {"source_file_name": source.name, "source_sha256": digest,
              "imported_events": imported,
              "interpretation": "Imported debugger telemetry, NOT a live register capture"}
    session.store.event("debugger_import_complete", record)
    return record