"""Strict local configuration for MVKView Capture Agent."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re

TARGET_EXE = "mvkview.exe"
TARGET_WINDOW_CLASS = "Tmvkform"
MAX_WATCH_COUNT = 16
MAX_ONE_WATCH = 1024 * 1024
MAX_TOTAL_WATCH_BYTES = 2 * 1024 * 1024


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class MemoryWatch:
    name: str
    address: int
    size: int
    encoding: str = "hex"

    @classmethod
    def parse(cls, value: dict) -> "MemoryWatch":
        if not isinstance(value, dict) or set(value) != {"name", "address", "size", "encoding"}:
            raise CaptureError("Each memory watch requires name, address, size and encoding")
        name = value["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", name):
            raise CaptureError("Memory watch names must be short ASCII identifiers")
        raw = value["address"]
        try:
            address = int(raw, 0) if isinstance(raw, str) else int(raw)
        except (ValueError, TypeError) as exc:
            raise CaptureError("Invalid watch address") from exc
        size = value["size"]
        if type(size) is not int or not 1 <= size <= MAX_ONE_WATCH:
            raise CaptureError("Memory watch size must be between 1 and 1048576 bytes")
        if not 0x10000 <= address <= 0xFFFFFFFF or address + size > 0x100000000:
            raise CaptureError("Only bounded x86 user-mode memory addresses are supported")
        encoding = value["encoding"]
        if encoding not in {"hex", "u32", "i32", "f32", "f32_array"}:
            raise CaptureError("Unsupported memory encoding")
        if encoding in {"u32", "i32", "f32"} and size != 4:
            raise CaptureError("Scalar watch requires exactly 4 bytes")
        if encoding == "f32_array" and size % 4:
            raise CaptureError("Float32 array size must be divisible by 4")
        return cls(name, address, size, encoding)

    def safe_dict(self):
        return {"name": self.name, "address": f"0x{self.address:08X}",
                "size": self.size, "encoding": self.encoding}


@dataclass(frozen=True)
class CaptureConfig:
    output_dir: Path
    poll_seconds: float = 1.0
    screenshot: bool = True
    ui_automation: bool = False
    memory_read: bool = False
    save_raw_memory: bool = False
    watches: tuple[MemoryWatch, ...] = ()
    max_controls: int = 400
    auto_trace: bool = False
    trace_arrays: bool = False

    @staticmethod
    def defaults() -> "CaptureConfig":
        return CaptureConfig(Path.home() / "Documents" / "MVK_Research" / "captures")

    @classmethod
    def load(cls, path: str | Path | None = None) -> "CaptureConfig":
        if path is None:
            return cls.defaults()
        file = Path(path).expanduser().resolve(strict=True)
        if not file.is_file() or file.stat().st_size > 65536:
            raise CaptureError("Configuration must be a regular local JSON file <= 64 KiB")
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise CaptureError("Invalid configuration JSON") from exc
        if not isinstance(data, dict):
            raise CaptureError("Configuration must be a JSON object")
        allowed = {"output_dir", "poll_seconds", "screenshot", "ui_automation",
                   "memory_read", "save_raw_memory", "watches", "max_controls",
                   "auto_trace", "trace_arrays"}
        if set(data) - allowed:
            raise CaptureError("Unexpected configuration keys: " + ", ".join(sorted(set(data)-allowed)))
        default = cls.defaults()
        out = Path(data.get("output_dir", str(default.output_dir))).expanduser().absolute()
        if str(out).startswith("\\\\"):
            raise CaptureError("Network/UNC capture directories are not allowed")
        seconds = data.get("poll_seconds", 1.0)
        if type(seconds) not in (int, float) or not 0.25 <= seconds <= 30:
            raise CaptureError("poll_seconds must be 0.25..30")
        controls = data.get("max_controls", 400)
        if type(controls) is not int or not 10 <= controls <= 1000:
            raise CaptureError("max_controls must be 10..1000")
        for flag in ("screenshot", "ui_automation", "memory_read", "save_raw_memory",
                     "auto_trace", "trace_arrays"):
            if type(data.get(flag, getattr(default, flag))) is not bool:
                raise CaptureError(f"{flag} must be boolean")
        raw_watches = data.get("watches", [])
        if not isinstance(raw_watches, list) or len(raw_watches) > MAX_WATCH_COUNT:
            raise CaptureError("Too many memory watches")
        watches = tuple(MemoryWatch.parse(w) for w in raw_watches)
        if len({w.name for w in watches}) != len(watches):
            raise CaptureError("Duplicate memory watch names")
        if sum(w.size for w in watches) > MAX_TOTAL_WATCH_BYTES:
            raise CaptureError("Memory watch total exceeds 2 MiB")
        mem = data.get("memory_read", False)
        raw = data.get("save_raw_memory", False)
        if raw and not mem:
            raise CaptureError("save_raw_memory requires memory_read=true")
        if watches and not mem:
            raise CaptureError("watches require memory_read=true")
        if data.get("trace_arrays", False) and not data.get("auto_trace", False):
            raise CaptureError("trace_arrays requires auto_trace=true")
        return cls(out, float(seconds), data.get("screenshot", True),
                   data.get("ui_automation", False), mem, raw, watches, controls,
                   data.get("auto_trace", False), data.get("trace_arrays", False))

    def safe_dict(self):
        result = asdict(self)
        result["output_dir"] = str(self.output_dir)
        result["watches"] = [w.safe_dict() for w in self.watches]
        return result