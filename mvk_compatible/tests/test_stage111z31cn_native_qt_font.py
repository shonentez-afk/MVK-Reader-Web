"""Stage111Z31CN: distinguish Qt text raster from Win32 GDI on Windows CI.

This probes glyph *pixels*, not QRawFont's cmap/supportsCharacter, whose
reported coverage cannot prove that QPainter actually rendered a glyph.
The diagnostic is device-free, creates only fake text in memory, and never
declares parity with the closed Delphi MVKView executable.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QRawFont

from .test_desktop_qt import qt_app
from ..desktop.win32_gdi_source_candidate import Win32SourceTextCanvas

CHARS = ("0", "1", "2", "A", "Б", "Ж")
SIDE = 64
SOURCE = "STAGE111Z31CN_NATIVE_QPA_FONT_PIXEL_DIAGNOSTIC_NOT_ORIGINAL"


def _qt_letter(ch: str, font: QFont) -> np.ndarray:
    img = QImage(SIDE, SIDE, QImage.Format_RGBA8888)
    img.fill(QColor(255, 255, 255, 255))
    p = QPainter(img)
    assert p.isActive()
    p.setPen(QColor(0, 0, 0))
    p.setFont(font)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.drawText(8, 35, ch)
    p.end()
    assert not img.isNull()
    return np.frombuffer(img.constBits(), dtype=np.uint8,
                         count=img.sizeInBytes()).reshape(SIDE, SIDE, 4).copy()


def _gdi_letter(ch: str, ctx: Win32SourceTextCanvas) -> np.ndarray:
    base = np.full((SIDE, SIDE, 4), 255, dtype=np.uint8)
    # Original source _Unit115 uses Win32 TextOutW, not a widget font.
    return ctx.draw_text(base, [{"kind": "x_tick", "x": 8, "y": 13,
                                 "text": ch}])


def _audit_raster(pictures) -> dict:
    metrics = []
    for glyph, pixels in zip(CHARS, pictures):
        ink = np.min(pixels[:, :, :3], axis=2) < 245
        ys, xs = np.where(ink)
        metrics.append({
            "glyph": glyph,
            "ink_pixels": int(np.count_nonzero(ink)),
            "bounds": ([int(xs.min()), int(ys.min()), int(xs.max()),
                        int(ys.max())] if len(xs) else None),
            "rgba_sha256": sha256(pixels.tobytes()).hexdigest(),
        })
    return {
        "glyphs": metrics,
        "different_raster_shapes": len(set(m["rgba_sha256"] for m in metrics)),
        "zero_ink_glyphs": [m["glyph"] for m in metrics if not m["ink_pixels"]],
        "candidate_box_substitution": (
            len(set(m["rgba_sha256"] for m in metrics)) <= 2),
    }


def _save_visual_strip(target: Path, qt_images, gdi_images):
    # Two labelled 6-glyph rows: Qt first, independent native GDI second.
    # No original/vendor images or proprietary fonts, only fake glyphs.
    strip = np.full((SIDE * 2, SIDE * len(CHARS), 4), 255, dtype=np.uint8)
    for index, pixels in enumerate(qt_images):
        strip[:SIDE, index * SIDE:(index + 1) * SIDE] = pixels
    for index, pixels in enumerate(gdi_images):
        strip[SIDE:, index * SIDE:(index + 1) * SIDE] = pixels
    img = QImage(strip.data, strip.shape[1], strip.shape[0],
                 strip.strides[0], QImage.Format_RGBA8888).copy()
    assert not img.isNull()
    assert img.save(str(target), "PNG")


def test_actual_glyph_rasters_are_recorded_not_just_declared_by_cmap(qt_app):
    font = QFont("Tahoma", 10)
    raw = QRawFont.fromFont(font)
    qt_images = [_qt_letter(ch, font) for ch in CHARS]
    qt_result = _audit_raster(qt_images)
    assert len(qt_images) == 6
    # The test does NOT assert diversity on offscreen: its output is
    # intentionally a truthful receipt even if Qt paints tofu squares.
    gdi_result = None
    gdi_images = []
    gdi_metrics = None
    if sys.platform == "win32":
        with Win32SourceTextCanvas(font_face="Tahoma",
                                   font_height=-13) as dc:
            gdi_metrics = dc.diagnostics()
            gdi_images = [_gdi_letter(ch, dc) for ch in CHARS]
        gdi_result = _audit_raster(gdi_images)
    else:
        gdi_images = qt_images
    report = {
        "source": SOURCE,
        "platform": sys.platform,
        "qpa_platform": os.environ.get("QT_QPA_PLATFORM", "default"),
        "qt_scale": os.environ.get("QT_SCALE_FACTOR", "default"),
        "source_font": "Tahoma",
        "qt_raw_font_valid": raw.isValid(),
        "qt_raw_font_supports_character": (
            {ch: bool(raw.supportsCharacter(ord(ch))) for ch in CHARS}
            if raw.isValid() else None),
        "qt_raster": qt_result,
        "gdi_raster": gdi_result,
        "gdi_font": gdi_metrics,
        "original_executable_1to1_verified": False,
        "hardware_used": False,
        "proprietary_assets_included": False,
    }
    if os.environ.get("MVK_SOURCE_FONT_QA_DIR"):
        folder = Path(os.environ["MVK_SOURCE_FONT_QA_DIR"])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "font_backend_probe.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n", encoding="utf-8")
        _save_visual_strip(folder / "font_backend_probe.png",
                           qt_images, gdi_images)
    assert all(item["ink_pixels"] >= 0 for item in qt_result["glyphs"])
    # Windows native QPA must be audited, but a CI host missing fonts
    # must not be falsely reported as proof that EXE is correct.
    if os.environ.get("MVK_REQUIRE_NATIVE_QPA_GLYPHS") == "1":
        assert os.environ.get("QT_QPA_PLATFORM") == "windows"
        assert qt_result["different_raster_shapes"] >= 4, report
        assert not qt_result["zero_ink_glyphs"], report
        assert gdi_result is not None
        assert gdi_result["different_raster_shapes"] >= 4, report
        assert not gdi_result["zero_ink_glyphs"], report
