"""Bounded, explicitly authorized, read-only Win32 process memory sampling."""
from __future__ import annotations
import hashlib
import math
import struct
import sys
from .config import CaptureError, MemoryWatch, MAX_TOTAL_WATCH_BYTES


def interpret(watch: MemoryWatch, data: bytes) -> dict:
    if len(data) != watch.size:
        raise CaptureError("Memory read is incomplete")
    report = {"watch": watch.name, "address": f"0x{watch.address:08X}",
              "size": len(data), "encoding": watch.encoding,
              "sha256": hashlib.sha256(data).hexdigest()}
    if watch.encoding == "hex":
        report["preview_hex"] = data[:32].hex()
    elif watch.encoding in ("u32", "i32", "f32"):
        code = {"u32": "I", "i32": "i", "f32": "f"}[watch.encoding]
        value = struct.unpack("<"+code, data)[0]
        report["value"] = value if not isinstance(value, float) or math.isfinite(value) else str(value)
        report["raw_hex"] = data.hex()
    else:
        count = len(data)//4
        values = struct.unpack("<"+str(count)+"f", data)
        finite = [x for x in values if math.isfinite(x)]
        report.update({"count": count, "finite_count": len(finite),
                       "min_finite": min(finite) if finite else None,
                       "max_finite": max(finite) if finite else None,
                       "preview": [x if math.isfinite(x) else str(x) for x in values[:12]]})
    return report


class MemoryReader:
    def __init__(self, backend, pid, hwnd):
        if sys.platform != "win32":
            raise CaptureError("ReadProcessMemory requires Windows")
        self.backend, self.pid, self.hwnd = backend, pid, hwnd

    def read(self, watch: MemoryWatch) -> bytes:
        self.backend.check_target(self.pid, self.hwnd)
        import ctypes
        from ctypes import wintypes
        k = self.backend.k
        k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]
        k.ReadProcessMemory.restype = wintypes.BOOL
        # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ. Never request write,
        # execute, debug attach, suspend, or PROCESS_ALL_ACCESS.
        process = k.OpenProcess(0x1000 | 0x0010, False, self.pid)
        if not process:
            raise CaptureError("Cannot open MVKView process read-only (permissions)")
        try:
            buf = ctypes.create_string_buffer(watch.size)
            nread = ctypes.c_size_t(0)
            ok = k.ReadProcessMemory(process, ctypes.c_void_p(watch.address), buf,
                                     watch.size, ctypes.byref(nread))
            if not ok or nread.value != watch.size:
                raise CaptureError(f"Memory region unreadable at 0x{watch.address:08X}")
            return bytes(buf.raw)
        finally:
            k.CloseHandle(process)

    def sample(self, watches, raw_store=None):
        if sum(w.size for w in watches) > MAX_TOTAL_WATCH_BYTES:
            raise CaptureError("Total memory sampling limit exceeded")
        output = []
        for watch in watches:
            try:
                raw = self.read(watch)
                result = interpret(watch, raw)
                if raw_store is not None:
                    result["local_binary"] = raw_store(watch.name, raw)
                output.append(result)
            except (CaptureError, OSError) as exc:
                output.append({"watch": watch.name, "error": str(exc)})
        return output