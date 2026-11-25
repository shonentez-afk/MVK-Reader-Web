"""Persist local recording choices apart from the original program's XML."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .original_device_ip_settings import compatible_device_settings_path
from .original_pagefile_recording import ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE

DEFAULT_PAGEFILE_SETTINGS = {
    "write_tsxml": True,
    "use_folder_prefix": False,
    "use_custom_name": False,
    "folder_prefix": ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE,
    "custom_name": "",
    "file_prefix": "",
    "library": "",
}
_MAX_SETTINGS_SIZE = 16384


def pagefile_settings_path():
    device = compatible_device_settings_path()
    return device.with_name("pagefile.json") if device is not None else None


def checked_pagefile_settings(settings):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULT_PAGEFILE_SETTINGS):
        raise ValueError("Invalid PageFile settings shape")
    for key, default in DEFAULT_PAGEFILE_SETTINGS.items():
        value = settings[key]
        if type(value) is not type(default):
            raise ValueError(f"Invalid PageFile setting: {key}")
        if isinstance(value,str) and (
                len(value) > (4096 if key == "library" else 255)
                or any(ord(c) < 32 for c in value)):
            raise ValueError(f"Invalid PageFile text: {key}")
    return dict(settings)


def load_pagefile_settings(path=None):
    path = pagefile_settings_path() if path is None else Path(path)
    if path is None or not path.exists():
        return dict(DEFAULT_PAGEFILE_SETTINGS)
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError("PageFile settings cannot be linked")
    if path.stat().st_size > _MAX_SETTINGS_SIZE:
        raise ValueError("PageFile settings are too large")
    return checked_pagefile_settings(json.loads(path.read_text(encoding="utf-8")))


def save_pagefile_settings(settings, path=None):
    checked = checked_pagefile_settings(settings)
    path = pagefile_settings_path() if path is None else Path(path)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("PageFile settings cannot be linked")
    payload = json.dumps(checked, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > _MAX_SETTINGS_SIZE:
        raise ValueError("PageFile settings are too large")
    tmp = None
    try:
        with NamedTemporaryFile(mode="wb", prefix=".mvk_pagefile_",
                                dir=path.parent, delete=False) as out:
            tmp = Path(out.name)
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return path
