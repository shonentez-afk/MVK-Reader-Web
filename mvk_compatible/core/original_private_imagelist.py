"""Opt-in, memory-only, bounded source icons from a PRIVATE Delphi DFM.

The user's own icAllImages collection has several PNG dimensions per icon.
Nothing from the original assets is packaged into the public repository,
PyInstaller binary, Github logs, or synthetic CI screenshots.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import struct

SOURCE = "LOCAL_PRIVATE_DFM_IMAGELIST_STAGE111Z31CQ"
MAX_DFM_BYTES = 12 * 1024 * 1024
MAX_ICON_BYTES = 512 * 1024
ALLOWED_TASK_NAMES = ("Gears", "Open", "EditGear", "EditNet", "BWHand")
ICON_SIZE_PREFERENCE = {
    "BWHand": 24, "Gears": 64, "Open": 64,
    "EditGear": 64, "EditNet": 64,
}
PNG_SIG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PrivateSourceImage:
    name: str
    width: int
    height: int
    data: bytes

    @property
    def source_is_private(self):
        return True


def _inspect_png(data: bytes):
    if (len(data) < 45 or len(data) > MAX_ICON_BYTES
            or not data.startswith(PNG_SIG) or data[12:16] != b"IHDR"):
        raise ValueError("Invalid or oversized private source PNG")
    width, height = struct.unpack(">II", data[16:24])
    if not 1 <= width <= 512 or not 1 <= height <= 512:
        raise ValueError("Unsafe private PNG dimensions")
    if b"IEND" not in data[-20:]:
        raise ValueError("Incomplete source PNG")
    return width, height


def source_task_icons_from_dfm(dfm: bytes) -> dict[str, PrivateSourceImage]:
    """Extract five named PNGs at the closest source ImageList resolution.

    The top-level Delphi TImageCollection has up to 34 items, each with
    multiple Image.Data PNGs. Only the five requested source UI names
    are returned; fail closed on malformed images, duplicates, or gaps.
    """
    if (not isinstance(dfm, bytes) or not 1 <= len(dfm) <= MAX_DFM_BYTES):
        raise ValueError("Bounded operator-provided DFM bytes required")
    text = dfm.decode("latin1")
    collection = re.search(
        r"(?m)^  object icAllImages: TImageCollection\r?$", text)
    if collection is None:
        raise ValueError("Private DFM has no source image collection")
    remaining = text[collection.end():]
    finish = re.search(r"(?m)^  end\r?$", remaining)
    if finish is None:
        raise ValueError("Unterminated private source collection")
    chunk = remaining[:finish.start()]
    positions = list(re.finditer(r"(?m)^      item\r?$", chunk))
    if not 1 <= len(positions) <= 128:
        raise ValueError("Invalid private collection length")
    found: dict[str, PrivateSourceImage] = {}
    allowed = set(ALLOWED_TASK_NAMES)
    for index, item in enumerate(positions):
        end = (positions[index + 1].start()
               if index + 1 < len(positions) else len(chunk))
        block = chunk[item.end():end]
        match = re.search(
            r"(?m)^        Name = '([A-Za-z0-9_]{1,48})'\r?$", block)
        if match is None or match.group(1) not in allowed:
            continue
        name = match.group(1)
        if name in found:
            raise ValueError("Duplicate private source icon name")
        encoded = re.findall(
            r"Image\.Data\s*=\s*\{([0-9A-Fa-f\s]+)\}", block)
        if not 1 <= len(encoded) <= 8:
            raise ValueError("Missing/private icon size variants")
        variants = []
        for source in encoded:
            hex_data = re.sub(r"\s+", "", source)
            if (not hex_data or len(hex_data) % 2
                    or len(hex_data) > 2 * MAX_ICON_BYTES):
                raise ValueError("Invalid private image hex length")
            png = bytes.fromhex(hex_data)
            width, height = _inspect_png(png)
            variants.append(PrivateSourceImage(name, width, height, png))
        target = ICON_SIZE_PREFERENCE[name]
        found[name] = min(
            variants,
            key=lambda x: (abs(x.width - target) + abs(x.height - target),
                           -x.width))
    if set(found) != allowed:
        raise ValueError("Incomplete private source task icons")
    return found
