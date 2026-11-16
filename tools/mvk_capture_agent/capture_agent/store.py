"""Private, immutable-by-default local evidence store and ZIP export."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time
import zipfile
from .config import CaptureError

MAX_ARTIFACTS = 10000
MAX_ZIP_BYTES = 512 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       allow_nan=False, indent=2) + "\n").encode("utf-8")


class EvidenceStore:
    def __init__(self, root: Path, target: dict, config: dict):
        root = Path(root).expanduser().absolute()
        if str(root).startswith("\\\\"):
            raise CaptureError("Network output directories are not allowed")
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = root / ("MVK_CAPTURE_" + stamp + "_" + secrets.token_hex(3))
        self.path.mkdir(mode=0o700)
        (self.path / "screenshots").mkdir()
        (self.path / "memory").mkdir()
        self._lock = threading.RLock()
        self._seq = 0
        self._screens = 0
        self._closed = False
        self.meta = {"schema": "mvk.capture.session.v1", "started_utc": utc_now(),
                     "ended_utc": None, "target": target, "config": config,
                     "events": 0, "snapshots": 0, "status": "capturing",
                     "safety": {"automatic_ui_actions": False,
                                "device_commands": False,
                                "debugger_attach_or_breakpoints": False,
                                "automatic_cloud_upload": False}}
        self._write_json("session.json", self.meta)

    def _validated(self, relative: str) -> Path:
        p = Path(relative)
        if p.is_absolute() or ".." in p.parts or p.parts[0] not in {
                "screenshots", "memory", "session.json", "timeline.jsonl",
                "summary.json", "imported_debugger.jsonl", "evidence_manifest.json"}:
            raise CaptureError("Unsafe evidence path")
        dest = self.path / p
        if not dest.resolve().is_relative_to(self.path.resolve()):
            raise CaptureError("Evidence path escapes session")
        return dest

    def _write_json(self, name, value):
        path = self._validated(name)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(json_bytes(value))
        temp.replace(path)

    def event(self, event_type: str, payload: dict):
        with self._lock:
            if self._closed:
                raise CaptureError("Capture session closed")
            self._seq += 1
            record = {"seq": self._seq, "timestamp_utc": utc_now(),
                      "monotonic_ns": time.monotonic_ns(),
                      "kind": event_type, "payload": payload}
            with self._validated("timeline.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False,
                                        separators=(",", ":")) + "\n")
            self.meta["events"] = self._seq
            return self._seq

    def json_snapshot(self, seq, info):
        # Snapshot JSON is carried in the timeline. Screenshots are immutable files.
        with self._lock:
            self.meta["snapshots"] += 1
            return self.event("snapshot", {"ordinal": self.meta["snapshots"], **info})

    def screenshot(self, backend, pid, hwnd):
        with self._lock:
            if self._screens >= MAX_ARTIFACTS:
                raise CaptureError("Screenshot limit reached")
            self._screens += 1
            rel = f"screenshots/{self._screens:05d}.png"
            path = self._validated(rel)
            try:
                meta = backend.screenshot(pid, hwnd, path)
                if not path.is_file() or path.stat().st_size == 0:
                    raise CaptureError("No screenshot was written")
                return {"path": rel, "sha256": sha256_file(path), **meta}
            except Exception:
                path.unlink(missing_ok=True)
                raise

    def raw(self, name: str, data: bytes):
        with self._lock:
            if not name.replace("_", "").replace("-", "").isalnum():
                raise CaptureError("Invalid binary artifact label")
            if len(data) > 1024 * 1024:
                raise CaptureError("Single raw memory snapshot too large")
            rel = f"memory/{self._seq + 1:07d}_{name}.bin"
            path = self._validated(rel)
            with path.open("xb") as handle:
                handle.write(data)
            return rel

    def close(self, state="stopped"):
        with self._lock:
            if not self._closed:
                self.meta["ended_utc"] = utc_now()
                self.meta["status"] = state
                self._write_json("session.json", self.meta)
                self._closed = True

    def export(self):
        with self._lock:
            if not self._closed:
                raise CaptureError("Stop capture before exporting a final archive")
            included = []
            total = 0
            for path in sorted(self.path.rglob("*")):
                if not path.is_file() or path.is_symlink() or path.name.endswith(".tmp") or path.name == "evidence_manifest.json":
                    continue
                rel = path.relative_to(self.path).as_posix()
                size = path.stat().st_size
                total += size
                if len(included) >= MAX_ARTIFACTS + 16 or total > MAX_ZIP_BYTES:
                    raise CaptureError("Capture ZIP exceeds safe 512 MiB / artifact limit")
                included.append({"path": rel, "size_bytes": size, "sha256": sha256_file(path)})
            manifest = {"schema": "mvk.capture.export.v1", "created_utc": utc_now(),
                        "original_capture_path": self.path.name,
                        "files": included, "file_count": len(included),
                        "private_local_evidence": True,
                        "original_mvkview_parity_verified": False}
            self._write_json("evidence_manifest.json", manifest)
            dest = self.path.with_suffix(".zip")
            if dest.exists():
                raise CaptureError("Archive already exists; refusing overwrite")
            with zipfile.ZipFile(dest, "x", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6) as z:
                for item in included:
                    z.write(self.path / item["path"], item["path"])
                z.write(self.path / "evidence_manifest.json", "evidence_manifest.json")
            return {"zip": str(dest), "sha256": sha256_file(dest),
                    "files": len(included)+1, "size_bytes": dest.stat().st_size}