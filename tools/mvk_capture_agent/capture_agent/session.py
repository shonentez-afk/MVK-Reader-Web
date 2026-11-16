"""Single-target capture, timeline correlation, and consent enforcement."""
from __future__ import annotations
from collections import deque
import hashlib
import json
import queue
import threading
import time
from .config import CaptureConfig, CaptureError
from .events import WinEventObserver
from .memory import MemoryReader
from .store import EvidenceStore
from .windows import WindowsBackend
from .debugger_import import import_debugger_log

MAX_WIN_EVENTS = 50000


class CaptureSession:
    def __init__(self, config: CaptureConfig, backend, target: dict,
                 observer_factory=WinEventObserver, memory_factory=MemoryReader):
        self.config = config
        self.backend = backend
        self.target = dict(target)
        self.pid = int(target["pid"])
        self.hwnd = int(target["hwnd"])
        self.observer_factory = observer_factory
        self.memory_factory = memory_factory
        self.incoming = queue.Queue(maxsize=4096)
        self.stop_signal = threading.Event()
        self.worker = None
        self.observer = None
        self.last_ui_digest = None
        self.last_event_screenshot = 0.0
        self.events_seen = 0
        self.status_label = "created"
        self.last_error = None
        self.store = None
        self._lock = threading.RLock()

    def start(self):
        if self.store is not None:
            raise CaptureError("Session already started")
        self.backend.check_target(self.pid, self.hwnd)
        self.store = EvidenceStore(self.config.output_dir, self.target,
                                   self.config.safe_dict())
        self.status_label = "capturing"
        self.store.event("capture_started", {"target_pid": self.pid,
                                             "target_hwnd": self.hwnd,
                                             "observation_only": True})
        self.snapshot(reason="initial", memory=False)
        self.observer = self.observer_factory(self.pid, self.incoming)
        try:
            self.observer.start()
        except CaptureError as exc:
            self.store.event("win_event_unavailable", {"error": str(exc)})
        self.worker = threading.Thread(target=self._loop, name="MVK-Capture", daemon=True)
        self.worker.start()
        return self.status()

    def _loop(self):
        try:
            next_poll = time.monotonic() + self.config.poll_seconds
            while not self.stop_signal.is_set():
                elapsed = time.monotonic()
                try:
                    event = self.incoming.get(timeout=min(max(0.05, next_poll-elapsed), 0.3))
                except queue.Empty:
                    event = None
                if event is not None and self.events_seen < MAX_WIN_EVENTS:
                    self.events_seen += 1
                    self.store.event("win_event", event)
                    if event.get("event") in {"OBJECT_SHOW", "OBJECT_HIDE",
                         "OBJECT_SELECTION", "OBJECT_INVOKED", "OBJECT_FOCUS"}:
                        now = time.monotonic()
                        if now - self.last_event_screenshot >= 1.0:
                            self.last_event_screenshot = now
                            # Read state and image after notification, not in WinEvent callback.
                            self.snapshot(reason="win_event", memory=False,
                                          screenshot=True, only_if_changed=True)
                if time.monotonic() >= next_poll:
                    self.backend.check_target(self.pid, self.hwnd)
                    self.snapshot(reason="poll", memory=False, screenshot=False,
                                  only_if_changed=True)
                    next_poll = time.monotonic() + self.config.poll_seconds
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            try:
                self.store.event("capture_failed", {"error": self.last_error})
            except Exception:
                pass
            self.status_label = "failed"
            self.stop_signal.set()
            if self.observer:
                self.observer.stop()
            self.store.close("failed")

    def snapshot(self, reason="manual", memory=False, screenshot=True,
                 only_if_changed=False):
        if self.store is None:
            raise CaptureError("Capture session not started")
        with self._lock:
            self.backend.check_target(self.pid, self.hwnd)
            ui = self.backend.snapshot(self.pid, self.hwnd,
                                       limit=self.config.max_controls,
                                       uia=self.config.ui_automation)
            fingerprint = hashlib.sha256(json.dumps(ui, sort_keys=True,
                                                     ensure_ascii=True).encode()).hexdigest()
            if only_if_changed and fingerprint == self.last_ui_digest:
                return {"changed": False, "reason": reason}
            self.last_ui_digest = fingerprint
            detail = {"reason": reason, "ui_sha256": fingerprint, "ui": ui}
            if screenshot and self.config.screenshot:
                try:
                    detail["screenshot"] = self.store.screenshot(
                        self.backend, self.pid, self.hwnd)
                    popups = []
                    for window in ui.get("toplevel_windows", []):
                        handle = window.get("hwnd")
                        if (handle != self.hwnd and window.get("visible") is True
                                and handle and len(popups) < 4):
                            try:
                                capture = self.store.screenshot(self.backend, self.pid, handle)
                                popups.append({"hwnd": handle, "class_name": window.get("class_name"),
                                               "screenshot": capture})
                            except (CaptureError, OSError, TypeError, ValueError):
                                continue
                    if popups:
                        detail["additional_process_windows"] = popups
                except (CaptureError, OSError, TypeError, ValueError) as exc:
                    detail["screenshot_error"] = str(exc)[:300]
            if memory:
                if not self.config.memory_read or not self.config.watches:
                    detail["memory_note"] = "No explicitly enabled memory watches"
                else:
                    reader = self.memory_factory(self.backend, self.pid, self.hwnd)
                    writer = self.store.raw if self.config.save_raw_memory else None
                    detail["memory"] = reader.sample(self.config.watches, writer)
            seq = self.store.json_snapshot(0, detail)
            return {"changed": True, "reason": reason, "timeline_seq": seq,
                    "screenshot": detail.get("screenshot"),
                    "screenshot_error": detail.get("screenshot_error"),
                    "memory_watches": len(detail.get("memory", []))}

    def import_debugger(self, path):
        if self.store is None:
            raise CaptureError("Capture session not started")
        return import_debugger_log(self, path)

    def stop(self):
        if self.store is None:
            raise CaptureError("Capture session not started")
        self.stop_signal.set()
        if self.observer:
            self.observer.stop()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=3)
        with self._lock:
            self.store.close("failed" if self.status_label == "failed" else "stopped")
            if self.status_label != "failed":
                self.status_label = "stopped"
        return self.status()

    def status(self):
        return {"status": self.status_label,
                "target_pid": self.pid, "target_hwnd": self.hwnd,
                "session_dir": str(self.store.path) if self.store else None,
                "events": self.store.meta["events"] if self.store else 0,
                "snapshots": self.store.meta["snapshots"] if self.store else 0,
                "last_error": self.last_error,
                "win_events_seen": self.events_seen}


class CaptureService:
    def __init__(self, backend=None):
        self.backend = backend
        self.session = None
        self._lock = threading.RLock()

    def _backend(self):
        if self.backend is None:
            self.backend = WindowsBackend()
        return self.backend

    def discover(self):
        return self._backend().targets()

    def start(self, *, acknowledge_local_capture=False, config_path=None, pid=None):
        if acknowledge_local_capture is not True:
            raise CaptureError("Start requires acknowledge_local_capture=true from the operator")
        with self._lock:
            if self.session and self.session.status_label == "capturing":
                raise CaptureError("Capture already running")
            matches = self.discover()
            if pid is not None:
                if type(pid) is not int or pid <= 0:
                    raise CaptureError("PID must be an integer")
                matches = [m for m in matches if m["pid"] == pid]
            if len(matches) != 1:
                raise CaptureError(f"Expected exactly one chosen Tmvkform, found {len(matches)}")
            config = CaptureConfig.load(config_path)
            session = CaptureSession(config, self._backend(), matches[0])
            session.start()
            self.session = session
            return session.status()

    def snapshot(self, *, include_memory=False):
        with self._lock:
            if not self.session or self.session.status_label != "capturing":
                raise CaptureError("No active capture")
            if type(include_memory) is not bool:
                raise CaptureError("include_memory must be boolean")
            return self.session.snapshot(reason="manual", memory=include_memory)

    def stop(self):
        with self._lock:
            if not self.session:
                raise CaptureError("No capture session exists")
            return self.session.stop()

    def export(self):
        with self._lock:
            if not self.session or self.session.status_label != "stopped":
                raise CaptureError("Stop capture before export")
            return self.session.store.export()

    def import_debugger(self, path):
        with self._lock:
            if not self.session or self.session.status_label != "capturing":
                raise CaptureError("Debugger log import requires an active session")
            return self.session.import_debugger(path)

    def status(self):
        with self._lock:
            if not self.session:
                return {"status": "idle", "target": "MVKView.exe/Tmvkform",
                        "requires_explicit_consent": True}
            return self.session.status()