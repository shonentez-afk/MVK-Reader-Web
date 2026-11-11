"""Stage111Z31AY: draw source 1px pmXor cursor into SAME 32bpp bitmap.

The operator-private _Unit115.pas 007CA793..007CAAFB changes TCanvas Pen
to clGreen/pmXor, erases prior vertical and 1/2 horizontal lines and draws
new lines with MoveTo/LineTo. This preview uses the existing independent
GDI line model on the visible offscreen TCo2Draw bitmap; Qt's QPainter
RasterOp would instead affect physical DPR-scaled device pixels.

Only source-derived formulas and synthetic pixels are used. The original
runtime TCanvas/GDI/DPI/screenshot parity is NOT yet demonstrated.
No original Delphi source, IDP, DFM, captures or device content are shipped.
"""
from __future__ import annotations

import numpy as np

from .tqgrapher_canvas_idr_candidate import SOURCE as CANVAS_SOURCE
from .tqgrapher_gdi_xor_idr_candidate import (
    CL_GREEN_RGB, GdiLineTo, MAX_RASTER_PIXELS, xor_gdi_line,
)

SOURCE = 'APP_DERIVED_TQGRAPHER_PMXOR_SAME_BITMAP_CURSOR_STAGE111Z31AY'


def source_bitmap_xor_contract() -> dict:
    return {
        'source': SOURCE,
        'source_original_pm_xor': True,
        'source_original_cursor_pen_rgb': CL_GREEN_RGB,
        'source_horizontal_line_start': 'PixelLeft',
        'source_horizontal_line_end_exclusive': 'PixelRight',
        'source_vertical_line_start': 'PixelTop',
        'source_vertical_line_end_exclusive': 'PixelBottom',
        'source_double_xor_at_intersection_cancels': True,
        'source_bitmap_cursor_is_a_reversible_presentation': True,
        'original_tcanvas_device_pixel_parity_verified': False,
        'original_runtime_tcanvas_font_verified': False,
    }


def source_bitmap_xor_cursor(base_rgba: np.ndarray, *,
                             canvas: dict,
                             cursor_pixel: tuple[int, int] | None = None
                             ) -> np.ndarray:
    """Compose optional native-coordinate cursor without changing background.

    This is a full redraw from the immutable offscreen bitmap on each move,
    equivalent to erasing and drawing the source XOR strokes without the
    risk of re-XORing stale pixels after a resize, zoom or mode change.
    The crossing pixel is XORed TWICE, as in original VCL MoveTo/LineTo.
    """
    if (not isinstance(base_rgba, np.ndarray)
            or base_rgba.ndim != 3 or base_rgba.shape[2] != 4
            or base_rgba.dtype != np.uint8):
        raise ValueError('Opaque HxWx4 uint8 source bitmap required')
    h, w = base_rgba.shape[:2]
    if (h < 4 or w < 4 or h * w > MAX_RASTER_PIXELS
            or not bool(np.all(base_rgba[:, :, 3] == 255))):
        raise ValueError('Bounded opaque source bitmap required')
    if (not isinstance(canvas, dict)
            or canvas.get('source') != CANVAS_SOURCE
            or canvas.get('canvas_width') != w
            or canvas.get('canvas_height') != h):
        raise ValueError('Matching TQGrapher source canvas required')
    try:
        left, right, top, bottom = (
            canvas[k] for k in
            ('pixel_left', 'pixel_right', 'pixel_top', 'pixel_bottom'))
    except KeyError as e:
        raise ValueError('Missing source PixelRect') from e
    if (any(type(p) is not int for p in (left, right, top, bottom))
            or not 0 <= left < right < w
            or not 0 <= top < bottom < h):
        raise ValueError('Invalid original source PixelRect')

    out = np.ascontiguousarray(base_rgba).copy()
    if cursor_pixel is None:
        return out
    if (not isinstance(cursor_pixel, tuple) or len(cursor_pixel) != 2
            or any(type(v) is not int for v in cursor_pixel)):
        raise ValueError('Native cursor point must be pair of integers')
    x, y = cursor_pixel
    if not left <= x <= right or not top <= y <= bottom:
        raise ValueError('Cursor must be clamped to the source PixelRect')
    # The original vertical and horizontal GDI lines are drawn in that
    # exact order and LineTo excludes the last pixel. Reuse Stage111P
    # checked bitwise GDI line implementation on the RGB view of the
    # PRIVATE copy (not on the input, source samples or FFT arrays).
    rgb = out[:, :, :3]
    xor_gdi_line(
        rgb, GdiLineTo('vertical', None, (x, top), (x, bottom)))
    xor_gdi_line(
        rgb, GdiLineTo('horizontal', 0, (left, y), (right, y)))
    return out
