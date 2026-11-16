"""Out-of-process WinEvent observer. No injection, SendMessage or UI actions."""
from __future__ import annotations
import queue
import sys
import threading
import time
from .config import CaptureError

EVENT_LABELS = {
    0x8000: "OBJECT_CREATE", 0x8001: "OBJECT_DESTROY",
    0x8002: "OBJECT_SHOW", 0x8003: "OBJECT_HIDE",
    0x8004: "OBJECT_REORDER", 0x8005: "OBJECT_FOCUS",
    0x8006: "OBJECT_SELECTION", 0x8007: "OBJECT_SELECTIONADD",
    0x8008: "OBJECT_SELECTIONREMOVE", 0x8009: "OBJECT_SELECTIONWITHIN",
    0x800A: "OBJECT_STATECHANGE", 0x800B: "OBJECT_LOCATIONCHANGE",
    0x800C: "OBJECT_NAMECHANGE", 0x800E: "OBJECT_VALUECHANGE",
    0x8013: "OBJECT_INVOKED",
}


class WinEventObserver:
    """Observe only events emitted by the chosen PID on the current desktop."""
    def __init__(self, pid: int, output: queue.Queue):
        self.pid, self.output = pid, output
        self._stop = threading.Event()
        self._thread = None
        self.start_error = None

    def start(self):
        if sys.platform != "win32":
            raise CaptureError("Windows WinEventHook requires Windows")
        if self._thread and self._thread.is_alive():
            raise CaptureError("Event observation already running")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="MVK-WinEvent", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.5)

    def _run(self):
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.WinDLL("user32", use_last_error=True)
            proc_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
                                           wintypes.HWND, wintypes.LONG, wintypes.LONG,
                                           wintypes.DWORD, wintypes.DWORD)
            u.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                           proc_type, wintypes.DWORD, wintypes.DWORD,
                                           wintypes.DWORD]
            u.SetWinEventHook.restype = wintypes.HANDLE
            u.UnhookWinEvent.argtypes = [wintypes.HANDLE]
            u.UnhookWinEvent.restype = wintypes.BOOL
            u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                       wintypes.UINT, wintypes.UINT, wintypes.UINT]
            u.PeekMessageW.restype = wintypes.BOOL
            def callback(hook, event, hwnd, object_id, child_id, thread_id, event_ms):
                try:
                    if event not in EVENT_LABELS:
                        return
                    entry = {"event": EVENT_LABELS[event], "event_code": event,
                             "hwnd": int(hwnd or 0), "object_id": object_id,
                             "child_id": child_id, "thread_id": thread_id,
                             "win_event_ms": event_ms}
                    self.output.put_nowait(entry)
                except queue.Full:
                    pass
                except Exception:
                    pass
            # Keep callback alive for the entire message-pump lifetime.
            listener = proc_type(callback)
            hook = u.SetWinEventHook(0x8000, 0x8015, None, listener, self.pid, 0, 2)
            if not hook:
                raise CaptureError("SetWinEventHook failed for target PID")
            try:
                msg = wintypes.MSG()
                while not self._stop.is_set():
                    while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                        pass
                    time.sleep(0.03)
            finally:
                u.UnhookWinEvent(hook)
        except Exception as exc:
            self.start_error = f"{type(exc).__name__}: {exc}"
            try:
                self.output.put_nowait({"event": "OBSERVER_ERROR", "message": self.start_error})
            except queue.Full:
                pass