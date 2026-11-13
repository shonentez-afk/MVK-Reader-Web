"""Live TQGrapher grid and cursor clipping shared by PageAdc/PageSpectrum.

Derived from private _Unit115 TQGrapher.Draw 007CAC68..007CB129 and
UpdateCursor 007CA75C..007CAB03, without redistributing PAS/DFM/IDP.

The original draws TCo2Draw #c0c0c0 software-grid strokes before the
series; UpdateCursor tests PixelLeft < X < PixelRight, uses pmXor clGreen,
and clamps a selected series' Y line to the plot rectangle. Qt retains
its own font, logical pixel and rasterization; original running Win32/GDI
pixel parity is NOT established by these static-source contracts.
"""
from __future__ import annotations

import math
import numbers

from .original_live_axis_ticks import source_live_axis_ticks
from .tco2draw_grid_source import GRID_LINE_HEX, BACKGROUND_HEX
from .tqgrapher_gdi_xor_idr_candidate import CL_GREEN_RGB

SOURCE = "APP_DERIVED_TQGRAPHER_LIVE_GRID_CURSOR_CLIP_STAGE111Z31CE"


def _finite(value, field):
    if (isinstance(value, bool) or
            not isinstance(value, numbers.Real)):
        raise ValueError(field + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(field + " must be finite")
    return value


def _rect(lo, hi, field):
    lo = _finite(lo, field + " left")
    hi = _finite(hi, field + " right")
    if not lo < hi:
        raise ValueError(field + " needs increasing bounds")
    return lo, hi


def source_live_grid_frame(*, view_x, view_y):
    """Current source tick lines, with no data/FFT array in the input."""
    if (not isinstance(view_x, (tuple, list)) or len(view_x) != 2 or
            not isinstance(view_y, (tuple, list)) or len(view_y) != 2):
        raise ValueError("Two view ranges required")
    x0, x1 = _rect(*view_x, "X viewport")
    y0, y1 = _rect(*view_y, "Y viewport")
    x = source_live_axis_ticks(scr_left=x0, scr_width=x1-x0)
    y = source_live_axis_ticks(scr_left=y0, scr_width=y1-y0)
    return {
        "source": SOURCE,
        "viewport_x": (x0, x1),
        "viewport_y": (y0, y1),
        "x_ticks": tuple(x["values"]),
        "y_ticks": tuple(y["values"]),
        "x_tick_labels": tuple(x["texts"]),
        "y_tick_labels": tuple(y["texts"]),
        "x_spacing_single": x["spacing_single"],
        "y_spacing_single": y["spacing_single"],
        "source_original_grid_before_series": True,
        "source_grid_hex": GRID_LINE_HEX,
        "source_background_hex": BACKGROUND_HEX,
        "source_cursor_xor_pen_rgb": CL_GREEN_RGB,
        "qt_canvas_pixel_parity_verified": False,
        "original_gdi_raster_pixel_parity_verified": False,
    }


def source_live_cursor_hit(*, canvas, scene_left, scene_right, scene_x):
    """Map Qt ViewBox mouse X to source PixelLeft..Right logical candidate.

    Original _Unit115:007CA811 tests integer X strictly inside both
    boundaries; the Y coordinate of MouseMove does not control selection.
    The scene is the measured Qt ViewBox, NOT the entire PaintBox bitmap.
    Do not apply Windows DPR to logical candidate pixels.
    """
    if (not isinstance(canvas, dict) or
            not canvas.get("original_source_formula_verified", False)):
        raise ValueError("Source-derived graph rectangle required")
    try:
        left = canvas["pixel_left"]
        right = canvas["pixel_right"]
    except KeyError as exc:
        raise ValueError("Source PixelRect missing") from exc
    if (type(left) is not int or type(right) is not int or
            left < 0 or right <= left):
        raise ValueError("Invalid source PixelLeft/PixelRight")
    scene_left, scene_right = _rect(scene_left, scene_right, "Qt scene")
    x = _finite(scene_x, "Qt mouse X")
    local = math.trunc((x-scene_left)*(right-left)/(scene_right-scene_left))
    native = left + local
    return {
        "source": SOURCE,
        "native_pixel_x_candidate": native,
        "inside_original_pixel_rect": (
            scene_left < x < scene_right and left < native < right),
        "source_strict_left_and_right_gate": True,
        "source_mouse_y_ignored": True,
        "qt_logical_pixel_space": True,
        "original_paintbox_runtime_registration_verified": False,
    }


def source_live_clip_crosshair(*, left, right, top, bottom, x, y):
    """Qt XOR presentation clip for original TQGrapher selected cursor.

    X outside the interior clears the crosshair; signed raw-series Y is
    saturated to a visible edge, as source 007CAC18 does before @ROUND.
    The selected numeric sample is NEVER altered by display clipping.
    """
    left, right = _rect(left, right, "X clipping")
    top, bottom = _rect(top, bottom, "Y clipping")
    x = _finite(x, "cursor X")
    y = _finite(y, "cursor Y")
    if not left < x < right:
        return None
    actual = min(bottom, max(top, y))
    return {
        "source": SOURCE,
        "x": x,
        "y": actual,
        "raw_y_unchanged": y,
        "y_clipped_for_presentation": actual != y,
        "source_vertical_segment": (x, top, x, bottom),
        "source_horizontal_segment": (left, actual, right, actual),
        "source_original_pm_xor": True,
        "source_xor_pen_rgb": CL_GREEN_RGB,
        "original_windows_gdi_pixel_parity_verified": False,
    }
