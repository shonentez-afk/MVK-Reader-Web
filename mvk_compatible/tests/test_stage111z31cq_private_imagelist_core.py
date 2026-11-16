"""Synthetic-only tests for opt-in Delphi private icAllImages extraction.

The fixture creates new coloured PNGs. It NEVER contains source icon
bytes, the user's screenshot, original DFM contents, or device records.
"""
from __future__ import annotations

from hashlib import sha256
import struct
import zlib

import pytest

from ..core.original_private_imagelist import (
    ALLOWED_TASK_NAMES, source_task_icons_from_dfm,
)


def synthetic_png(width: int, height: int, rgba=(120, 190, 240, 255)) -> bytes:
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    body = (b"\x00" + bytes(rgba) * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(body)) + chunk(b"IEND", b""))


def synthetic_task_dfm(background=(255, 240, 200, 255), *,
                       missing=(), duplicate=False) -> bytes:
    names = ("Gears", "Open", "EditGear", "EditNet", "BWHand")
    lines = ["object mvkform: Tmvkform"]
    for name in ("imBackL", "imBackR", "imLogo"):
        png = synthetic_png(16, 16, background)
        stream = b"\x09TPngImage" + png
        lines += [
            "        object " + name + ": TImage",
            "          Picture.Data = {",
            "            " + stream.hex().upper(),
            "          }",
            "        end",
        ]
    lines.extend(("  object icAllImages: TImageCollection", "    Images = <"))
    entries = list(names)
    if duplicate:
        entries.append("Gears")
    for name in entries:
        if name in missing:
            continue
        lines += [
            "      item", "        Name = '" + name + "'",
            "        SourceImages = <",
        ]
        for width in ((24, 48) if name == "BWHand" else (32, 64, 128)):
            png = synthetic_png(width, width)
            lines += [
                "          item", "            Image.Data = {",
                "              " + png.hex().upper(),
                "            }", "          end",
            ]
        lines += ["        end>", "      end"]
    lines += ["    >", "  end", "end"]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def test_five_task_icons_including_bw_hand_selected_at_exact_dpi_size():
    raw = synthetic_task_dfm()
    digest = sha256(raw).hexdigest()
    result = source_task_icons_from_dfm(raw)
    assert set(result) == set(ALLOWED_TASK_NAMES)
    for name, value in result.items():
        assert value.name == name
        assert value.source_is_private
        assert value.width == (24 if name == "BWHand" else 64)
        assert value.height == value.width
        assert value.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert sha256(raw).hexdigest() == digest


def test_missing_duplicate_malformed_and_oversized_original_icon_refused():
    with pytest.raises(ValueError, match="Incomplete"):
        source_task_icons_from_dfm(
            synthetic_task_dfm(missing=("EditNet",)))
    with pytest.raises(ValueError, match="Duplicate"):
        source_task_icons_from_dfm(synthetic_task_dfm(duplicate=True))
    with pytest.raises(ValueError, match="Bounded"):
        source_task_icons_from_dfm(b"")
    with pytest.raises(ValueError, match="Bounded"):
        source_task_icons_from_dfm(b"x" * (12 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="collection"):
        source_task_icons_from_dfm(b"object mvkform: Tmvkform\r\nend\r\n")
    fake = synthetic_task_dfm().replace(b"89504E47", b"00000000", 1)
    with pytest.raises(ValueError, match="Invalid"):
        source_task_icons_from_dfm(fake)


def test_user_original_screen_is_only_derived_metadata_not_fixture_bytes():
    source = source_task_icons_from_dfm(synthetic_task_dfm())
    assert all(len(item.data) < 512 * 1024 for item in source.values())
    assert tuple(sorted(source)) == tuple(sorted(ALLOWED_TASK_NAMES))
