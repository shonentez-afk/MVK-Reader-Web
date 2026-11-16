"""Single-target capture, timeline correlation, and consent enforcement."""
from __future__ import annotations
from dataclasses import replace
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
from .frida_trace import FridaTraceObserver

MAX_WIN_EVENTS = 50000


class CaptureSession:
    def __init__(self, config: CaptureConfig, backend, target: dict,
                 observer_factory=WinEventObserver, memory_factory=MemoryReader,
                 tracer_factory=FridaTraceObserver):
        self.config = config
        self.backend = backend
        self.target = dict(target)
        self.pid = int(target["pid"])
        self.hwnd = int(target["hwnd"])
        self.observer_factory = observer_factory
        self.memory_factory = memory_factory
        self.tracer_factory = tracer_factory
        self.tracer = None
        self.trace_info = None
        self.trace_events = 0
        self.incoming = queue.Queue(maxsize=4096)
        self.stop_signal = threading.Event()
        self.worker = None
        self.observer = None
        self.last_ui_digest = None
        # Event HWNDs have no text of their own. Associate observed HWNDs with
        # names/classes only when the selected target's Win32 tree establishes it.
        self._controls_by_hwnd = {}
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
                                             "observation_only": not self.config.auto_trace})
        self.snapshot(reason="initial", memory=False)
        self.observer = self.observer_factory(self.pid, self.incoming)
        try:
            self.observer.start()
        except CaptureError as exc:
            self.store.event("win_event_unavailable", {"error": str(exc)})
        if self.config.auto_trace:
            self.tracer = self.tracer_factory(self.pid, self.incoming,
                self.target["executable"], full_arrays=self.config.trace_arrays)
            try:
                self.trace_info = self.tracer.start()
                self.store.event("frida_instrumentation_ready", self.trace_info)
            except (CaptureError, OSError, ValueError) as exc:
                self.store.event("frida_instrumentation_rejected", {"reason": str(exc)})
                if self.observer:
                    self.observer.stop()
                if self.tracer:
                    self.tracer.stop()
                self.status_label = "failed"
                self.store.close("failed")
                raise CaptureError("Automatic trace startup failed: " + str(exc)) from exc
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
                if event is not None and event.get("source") == "frida":
                    self._record_trace(event)
                elif event is not None and self.events_seen < MAX_WIN_EVENTS:
                    self.events_seen += 1
                    self.store.event("win_event", self._annotate_win_event(event))
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
            if self.tracer:
                self.tracer.stop()
            self.store.close("failed")

    def _record_trace(self, event):
        if not self.store or self.store._closed:
            return
        payload = dict(event.get("payload") or {})
        if not payload or self.trace_events >= 5000:
            return
        binary = event.get("binary")
        if binary:
            # Frida attaches to known x86 sites; these bytes are untrusted
            # candidates until matched to the original BIN and mode.
            name = payload.get("site", "raw") + "_" + payload.get("array_type", "sample")
            stored = self.store.raw(name, binary)
            payload["binary"] = {"file": stored, "size": len(binary),
                                 "sha256": hashlib.sha256(binary).hexdigest(),
                                 "source_parity_verified": False}
        self.trace_events += 1
        self.store.event("frida_trace", payload)

    def _update_known_controls(self, ui):
        # Retain only lightweight, target-bound HWND labels. Handles are only
        # valid within this live capture; never treat them as stable identities.
        observed = {}
        for control in list(ui.get("child_controls") or []) + list(ui.get("toplevel_windows") or []):
            handle = control.get("hwnd")
            if type(handle) is int and handle > 0:
                observed[handle] = {
                    "control_name": str(control.get("name") or "")[:160],
                    "control_class": str(control.get("class_name") or "")[:100],
                }
        self._controls_by_hwnd = observed

    def _annotate_win_event(self, event):
        entry = dict(event)
        handle = entry.get("hwnd")
        if type(handle) is int:
            info = self._controls_by_hwnd.get(handle)
            if info:
                entry.update(info)
        return entry

    def _visual_popup_windows(self, ui):
        # Capture actual popup/menu and modal forms. Do not record visual-only
        # SysShadow, GDI helpers or 1x1 infrastructure windows as evidence.
        results = []
        blocked = {"sysshadow", "tapplication", "gdi+ hook window class",
                   "msctfime ui", "ime", "tputilwindow"}
        for window in ui.get("toplevel_windows") or []:
            handle = window.get("hwnd")
            cls = str(window.get("class_name") or "").casefold()
            rect = window.get("rect")
            if (type(handle) is not int or handle <= 0 or handle == self.hwnd
                    or window.get("visible") is not True or cls in blocked
                    or not isinstance(rect, list) or len(rect) != 4):
                continue
            try:
                w, h = int(rect[2]) - int(rect[0]), int(rect[3]) - int(rect[1])
            except (ValueError, TypeError):
                continue
            if w < 32 or h < 32:
                continue
            results.append(window)
            if len(results) >= 4:
                break
        return results

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
            self._update_known_controls(ui)
            detail = {"reason": reason, "ui_sha256": fingerprint, "ui": ui}
            # v0.2 lost six of seven observed popup menus: poll(screenshot=False)
            # consumed the new UI digest, so the later win-event snapshot had
            # nothing left to save. A visible genuine popup is always a visual
            # evidence transition, even on a low-cost periodic poll.
            visible_popups = self._visual_popup_windows(ui)
            take_screenshot = screenshot or bool(visible_popups)
            if take_screenshot and self.config.screenshot:
                try:
                    detail["screenshot"] = self.store.screenshot(
                        self.backend, self.pid, self.hwnd)
                    popups = []
                    for window in visible_popups:
                        handle = window["hwnd"]
                        try:
                            capture = self.store.screenshot(self.backend, self.pid, handle)
                            popups.append({"hwnd": handle,
                                           "class_name": window.get("class_name"),
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
        if self.tracer:
            self.tracer.stop()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=3)
        with self._lock:
            for _ in range(512):
                try:
                    event = self.incoming.get_nowait()
                except queue.Empty:
                    break
                if event.get("source") == "frida":
                    self._record_trace(event)
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
                "win_events_seen": self.events_seen,
                "automatic_internal_trace": bool(self.config.auto_trace),
                "frida_ready": bool(self.trace_info),
                "frida_trace_events": self.trace_events,
                "frida_dropped": self.tracer.dropped if self.tracer else 0}


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

    def start(self, *, acknowledge_local_capture=False, config_path=None, pid=None,
              auto_trace=False, trace_arrays=False, acknowledge_instrumentation=False):
        if type(auto_trace) is not bool or type(trace_arrays) is not bool:
            raise CaptureError("auto_trace and trace_arrays must be bool")
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
            trace_requested = auto_trace or config.auto_trace
            array_requested = trace_arrays or config.trace_arrays
            if array_requested and not trace_requested:
                raise CaptureError("Array capture requires auto trace")
            if trace_requested and acknowledge_instrumentation is not True:
                raise CaptureError("Frida modifies target RAM; explicit acknowledge_instrumentation=true required")
            if trace_requested:
                config = replace(config, auto_trace=True, trace_arrays=array_requested)
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