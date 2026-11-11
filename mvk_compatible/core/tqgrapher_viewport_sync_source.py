"""Stage111Z31AX: source bitmap viewport and cursor registration (offline).

Derived from operator-private _Unit115 TQGrapher 007CA593..007CA6C9,
007CA75C..007CAAEE and 007CAB94/007CABE4. Original IDP/PAS, captures
and bitmaps remain PRIVATE and are NOT embedded.

A Qt ViewBox scene-local X is NOT the original PaintBox X. Source graphics
use an inset PixelLeft..PixelRight within a complete bitmap. The same
registered canvas drives the raster and optional source cursor.
Native original runtime Font/DPI/GDI pixel parity is NOT asserted.
"""
from __future__ import annotations
import math
import numbers
import numpy as np
from .tqgrapher_canvas_idr_candidate import cursor_geometry_from_canvas

SOURCE = 'SOURCE_DERIVED_TQGRAPHER_BITMAP_VIEWPORT_CURSOR_REGISTRATION_STAGE111Z31AX'


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + ' must be finite numeric')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + ' must be finite numeric')
    return value


def _range(value, name: str) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(name + ' must contain two bounds')
    lo, hi = (_finite(v, name) for v in value)
    if not lo < hi:
        raise ValueError(name + ' must be increasing')
    return lo, hi


def bitmap_viewport_signature(*, view_x, view_y, width, height,
                              raster: bool, composite: bool) -> tuple:
    """Invalidate rendered pixels for every changed view, not only tick text."""
    xr = _range(view_x, 'view_x')
    yr = _range(view_y, 'view_y')
    if (type(width) is not int or type(height) is not int or
            not 4 <= width <= 10000 or not 4 <= height <= 10000 or
            width * height > 6_000_000):
        raise ValueError('bounded source bitmap dimensions required')
    if type(raster) is not bool or type(composite) is not bool or (composite and not raster):
        raise ValueError('valid raster/composite flags required')
    return (xr[0], xr[1], yr[0], yr[1], width, height, raster, composite)


def bitmap_cursor_geometry(*, canvas: dict, scene_local_x: float,
                           scene_width: float):
    """Return native-candidate integer X and source affine geometry.

    A cursor over the axis/text margin does NOT select FFT bin zero.
    """
    geometry = cursor_geometry_from_canvas(canvas)
    x = _finite(scene_local_x, 'scene_local_x')
    sw = _finite(scene_width, 'scene_width')
    if sw <= 0:
        raise ValueError('positive scene width required')
    cw = canvas['canvas_width']
    if type(cw) is not int or cw < 4 or x < 0 or x > sw:
        raise ValueError('cursor outside bounded bitmap scene')
    pixel = math.trunc(x * cw / sw)
    if not geometry.pixel_left < pixel < geometry.pixel_right:
        return None
    return pixel, geometry


def bitmap_cursor_overlay_coordinates(*, canvas: dict, bin_index: int,
                                      raw_y: float, view_x, view_y) -> dict:
    """Map original bitmap line/XOR position back to Qt ViewBox coordinates.

    Candidate source Single arithmetic and integer rounding only. Source
    coordinates are not a runtime original Delphi screenshot/GDI acceptance.
    """
    geometry = cursor_geometry_from_canvas(canvas)
    if type(bin_index) is not int or bin_index < 0:
        raise ValueError('nonnegative source bin_index required')
    y = _finite(raw_y, 'raw_y')
    xlo, xhi = _range(view_x, 'view_x')
    ylo, yhi = _range(view_y, 'view_y')
    with np.errstate(over='ignore', invalid='ignore'):
        native_x = float(np.float32(bin_index * geometry.itos_m + geometry.itos_c))
        native_y = float(np.float32(y * canvas['ytos_m'] + canvas['ytos_c']))
    if not math.isfinite(native_x) or not math.isfinite(native_y):
        raise ValueError('original source pixel transform overflow')
    native_x = max(geometry.pixel_left, min(geometry.pixel_right, native_x))
    native_y = max(float(canvas['pixel_top']), min(float(canvas['pixel_bottom']), native_y))
    ix, iy = int(round(native_x)), int(round(native_y))
    cw, ch = canvas['canvas_width'], canvas['canvas_height']
    if type(cw) is not int or type(ch) is not int or cw <= 0 or ch <= 0:
        raise ValueError('invalid source bitmap canvas size')
    return {
        'qt_x': xlo + ix / cw * (xhi - xlo),
        'qt_y': yhi - iy / ch * (yhi - ylo),
        'bitmap_pixel_x': ix,
        'bitmap_pixel_y': iy,
        'source': SOURCE,
        'source_inset_pixel_rect_used': True,
        'original_gdi_pixel_parity_verified': False,
    }
