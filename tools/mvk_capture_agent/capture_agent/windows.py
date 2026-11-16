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
        # Target-bound visible popup fallback requires verified foreground and
        # physical DWM bounds, never a whole-desktop screenshot.
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = wintypes.HWND
        u.WindowFromPoint.argtypes = [wintypes.POINT]
        u.WindowFromPoint.restype = wintypes.HWND
        u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetAncestor.restype = wintypes.HWND
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

    @staticmethod
    def _image_is_solid(image):
        """A full black PrintWindow bitmap is not proof of popup contents."""
        rgb = image.convert("RGB")
        return all(lo == hi for lo, hi in rgb.getextrema())

    def _physical_window_rect(self, hwnd):
        """DWM returns physical pixels; GetWindowRect may be DPI-virtualized."""
        dwm = self.ctypes.WinDLL("dwmapi", use_last_error=True)
        getter = dwm.DwmGetWindowAttribute
        getter.argtypes = [self.wt.HWND, self.wt.DWORD,
                           self.ctypes.c_void_p, self.wt.DWORD]
        getter.restype = self.ctypes.c_long
        r = self.wt.RECT()
        hr = getter(int(hwnd), 9, self.ctypes.byref(r), self.ctypes.sizeof(r))
        if hr != 0:
            raise CaptureError(f"Physical popup bounds unavailable (DWM HRESULT={hr})")
        return [int(r.left), int(r.top), int(r.right), int(r.bottom)]

    def _grab_verified_popup(self, pid, hwnd, grabber):
        """Bounded *visible* menu pixels only; refuse non-target overlays.

        The original Delphi menu is an independent class #32768 surface.
        PIL's window=HWND/PrintWindow returns all-black for this popup on the
        supplied real Windows 150% DPI session. A narrowly bounded screen crop
        is allowed only while MVKView has focus AND every sampled interior
        pixel hit-tests to this specific PID and popup root. Never grab the
        full desktop, and never fall back if those guards fail.
        """
        if self._class(hwnd) != "#32768" or not self.u.IsWindowVisible(int(hwnd)):
            raise CaptureError("Screen-region fallback is only for visible original menus")
        fg = self.u.GetForegroundWindow()
        if not fg or self.pid_for_hwnd(fg) != pid:
            raise CaptureError("Popup screen crop refused: MVKView is not foreground")
        x1, y1, x2, y2 = self._physical_window_rect(hwnd)
        width, height = x2 - x1, y2 - y1
        if not 32 <= width <= 1100 or not 32 <= height <= 1100 or width * height > 900000:
            raise CaptureError("Popup physical bounds outside strict size limits")
        for qx, qy in ((.24,.25),(.50,.50),(.76,.75)):
            point = self.wt.POINT(x1+int(width*qx), y1+int(height*qy))
            hit = self.u.WindowFromPoint(point)
            if not hit or self.pid_for_hwnd(hit) != pid:
                raise CaptureError("Popup crop refused: another application's window overlaps")
            top = self.u.GetAncestor(hit, 2)  # GA_ROOT
            if int(hit) != int(hwnd) and int(top or 0) != int(hwnd):
                raise CaptureError("Popup crop refused: visible pixels do not belong to selected menu")
        image = grabber.grab(bbox=(x1,y1,x2,y2), all_screens=True,
                             include_layered_windows=True)
        if not image or image.width < 32 or image.height < 32 or self._image_is_solid(image):
            raise CaptureError("Popup bounded screen capture still empty/uniform")
        return image

    def screenshot(self, pid, hwnd, path):
        originals = [t for t in self.targets() if t["pid"] == pid]
        if len(originals) != 1 or not self.u.IsWindow(int(hwnd)) or self.pid_for_hwnd(hwnd) != pid:
            raise CaptureError("Screenshot target no longer belongs to original MVKView")
        if originals[0]["minimized"]:
            raise CaptureError("Window minimized; refusing potentially wrong screenshot")
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise CaptureError("Screenshot requires Pillow: py -m pip install pillow") from exc
        image = ImageGrab.grab(window=int(hwnd))
        if not image or image.width < 32 or image.height < 32:
            raise CaptureError("Window screenshot was empty")
        method = "window"
        if self._class(hwnd) == "#32768" and self._image_is_solid(image):
            image = self._grab_verified_popup(pid, hwnd, ImageGrab)
            method = "bounded_visible_menu_foreground_verified"
        image.save(path, "PNG")
        return {"width": image.width, "height": image.height,
                "capture_method": method}