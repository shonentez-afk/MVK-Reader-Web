"""Read-only Win32/UIA inventory pinned to a single MVKView.exe PID.

Never sends messages, clicks, activates or restores a window.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from .config import CaptureError, TARGET_EXE, TARGET_WINDOW_CLASS


class WindowsBackend:
    def __init__(self):
        if sys.platform != "win32":
            raise CaptureError("Live capture is only available on interactive Windows")
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wt = wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u, self.k = u, k
        self.enumproc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows.argtypes = [self.enumproc, wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL
        u.EnumChildWindows.argtypes = [wintypes.HWND, self.enumproc, wintypes.LPARAM]
        u.EnumChildWindows.restype = wintypes.BOOL
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL
        u.IsWindow.argtypes = [wintypes.HWND]
        u.IsWindow.restype = wintypes.BOOL
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsWindowVisible.restype = wintypes.BOOL
        u.IsWindowEnabled.argtypes = [wintypes.HWND]
        u.IsWindowEnabled.restype = wintypes.BOOL
        u.IsIconic.argtypes = [wintypes.HWND]
        u.IsIconic.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        dpi = getattr(u, "GetDpiForWindow", None)
        if dpi is not None:
            dpi.argtypes = [wintypes.HWND]
            dpi.restype = wintypes.UINT

    def pid_for_hwnd(self, hwnd):
        pid = self.wt.DWORD(0)
        self.u.GetWindowThreadProcessId(int(hwnd), self.ctypes.byref(pid))
        return int(pid.value)

    def executable(self, pid):
        h = self.k.OpenProcess(0x1000, False, pid)
        if not h:
            return None
        try:
            path = self.ctypes.create_unicode_buffer(32768)
            n = self.wt.DWORD(len(path))
            if not self.k.QueryFullProcessImageNameW(h, 0, path, self.ctypes.byref(n)):
                return None
            return path.value
        finally:
            self.k.CloseHandle(h)

    def _class(self, hwnd):
        b = self.ctypes.create_unicode_buffer(256)
        self.u.GetClassNameW(int(hwnd), b, len(b))
        return b.value

    def _name(self, hwnd):
        b = self.ctypes.create_unicode_buffer(1024)
        self.u.GetWindowTextW(int(hwnd), b, len(b))
        return b.value[:240]

    def control(self, hwnd):
        r = self.wt.RECT()
        rect = None
        if self.u.GetWindowRect(int(hwnd), self.ctypes.byref(r)):
            rect = [int(r.left), int(r.top), int(r.right), int(r.bottom)]
        return {"hwnd": int(hwnd), "class_name": self._class(hwnd),
                "name": self._name(hwnd), "rect": rect,
                "visible": bool(self.u.IsWindowVisible(int(hwnd))),
                "enabled": bool(self.u.IsWindowEnabled(int(hwnd)))}

    def targets(self):
        observed = []
        def each(hwnd, unused):
            try:
                if self._class(hwnd).casefold() != TARGET_WINDOW_CLASS.casefold():
                    return True
                pid = self.pid_for_hwnd(hwnd)
                path = self.executable(pid)
                if not path or Path(path).name.casefold() != TARGET_EXE:
                    return True
                item = self.control(hwnd)
                item.update({"pid": pid, "executable": path,
                             "minimized": bool(self.u.IsIconic(hwnd))})
                observed.append(item)
            except Exception:
                pass
            return True
        self.u.EnumWindows(self.enumproc(each), 0)
        return sorted(observed, key=lambda x: (x["pid"], x["hwnd"]))

    def check_target(self, pid, hwnd):
        if not self.u.IsWindow(int(hwnd)) or self.pid_for_hwnd(hwnd) != pid:
            raise CaptureError("MVKView window/PID changed or disappeared; capture stopped")
        path = self.executable(pid)
        if not path or Path(path).name.casefold() != TARGET_EXE or self._class(hwnd).casefold() != TARGET_WINDOW_CLASS.casefold():
            raise CaptureError("Original target identity validation failed")
        return path

    def snapshot(self, pid, hwnd, limit=400, uia=False):
        self.check_target(pid, hwnd)
        controls = []
        truncated = False
        def each(child, unused):
            nonlocal truncated
            if len(controls) >= limit:
                truncated = True
                return False
            if self.pid_for_hwnd(child) == pid:
                controls.append(self.control(child))
            return True
        self.u.EnumChildWindows(int(hwnd), self.enumproc(each), 0)
        roots = []
        def top(window, unused):
            if self.pid_for_hwnd(window) == pid:
                roots.append(self.control(window))
            return True
        self.u.EnumWindows(self.enumproc(top), 0)
        dpi = None
        try:
            dpi_func = getattr(self.u, "GetDpiForWindow", None)
            dpi = int(dpi_func(hwnd)) if dpi_func is not None else None
        except Exception:
            pass
        result = {"target_pid": pid, "target_hwnd": int(hwnd),
                  "dpi": dpi, "root": self.control(hwnd),
                  "minimized": bool(self.u.IsIconic(int(hwnd))),
                  "toplevel_windows": roots[:16], "child_controls": controls,
                  "truncated": truncated, "backend": "Win32 read-only"}
        if uia:
            result["uia"] = self._uia(pid, hwnd, limit)
        return result

    def _uia(self, pid, hwnd, limit):
        try:
            from pywinauto import Desktop
            w = Desktop(backend="uia").window(handle=hwnd)
            data = []
            for element in w.descendants():
                if len(data) >= limit:
                    break
                try:
                    e = element.element_info
                    if int(e.process_id) != pid:
                        continue
                    r = element.rectangle()
                    data.append({"name": str(e.name or "")[:240],
                                 "automation_id": str(e.automation_id or "")[:100],
                                 "control_type": str(e.control_type or "")[:60],
                                 "class_name": str(e.class_name or "")[:100],
                                 "rect": [r.left, r.top, r.right, r.bottom],
                                 "enabled": bool(element.is_enabled()),
                                 "visible": bool(element.is_visible())})
                except Exception:
                    continue
            return {"controls": data, "truncated": len(data) == limit}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"[:300]}

    def screenshot(self, pid, hwnd, path):
        # A dropdown can live in a separate top-level HWND owned by the same
        # original process. Capture that HWND, never a generic screen rectangle.
        originals = [t for t in self.targets() if t["pid"] == pid]
        if len(originals) != 1 or not self.u.IsWindow(int(hwnd)) or self.pid_for_hwnd(hwnd) != pid:
            raise CaptureError("Screenshot target no longer belongs to original MVKView")
        if originals[0]["minimized"]:
            raise CaptureError("Window minimized; refusing potentially wrong screenshot")
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise CaptureError("Screenshot requires Pillow: py -m pip install pillow") from exc
        # This captures the chosen HWND, never the whole desktop or overlapping apps.
        image = ImageGrab.grab(window=int(hwnd))
        if not image or image.width < 32 or image.height < 32:
            raise CaptureError("Window screenshot was empty")
        image.save(path, "PNG")
        return {"width": image.width, "height": image.height}