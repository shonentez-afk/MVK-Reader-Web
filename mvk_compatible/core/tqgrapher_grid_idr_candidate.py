"""Stage111Z31E: source-derived TQGrapher grid spacing / label candidates.

Original code in operator-provided Projects.7z (never committed here):
 _Unit128.pas SpecGrapher initialization 00844B2B/00844B32:
     AutoVSpacing=10; AutoHSpacing=10
 _Unit115.pas TQGrapher.Draw 007CAC89..007CACAF:
     HLineSpacing=ScrHeight/AutoHSpacing;
     VLineSpacing=abs(ScrWidth/AutoVSpacing)
 Grid points: integer k * spacing, within current screen bounds with
 0.0001 extended-real tolerance at 007CAD35 / 007CAD53 et al.

The source establishes spacing logic, *not* verified exact runtime
Font/TCanvas, integer rounding, display format (007B2090), GDI color,
physical-pixel line positions or other native drawing behavior. This is an
opt-in Qt research comparison on already verified original Power/Y ONLY.
"""
from __future__ import annotations

import math
import numbers

import numpy as np

SOURCE = "APP_DERIVED_TQGRAPHER_SOURCE_10X10_GRID_CANDIDATE"
ORIGINAL_SOURCE_AUTO_H_SPACING = 10
ORIGINAL_SOURCE_AUTO_V_SPACING = 10
MAX_TICKS = 1000


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + ": real numeric value required")
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(name + ": finite numeric value required")
    return v


def _index_ticks(lo, hi, step):
    if step <= 0 or hi < lo:
        raise ValueError("Positive spacing and ascending screen bounds required")
    # Source computes the bounds with extended-real 0.0001 tolerance.
    # Integer-conversion RTL and x87 ties are NOT runtime-attested.
    low = math.ceil(lo / step - 0.0001)
    high = math.floor(hi / step + 0.0001)
    count = high - low + 1
    if count < 0:
        return ()
    if count > MAX_TICKS:
        raise ValueError("TQGrapher grid candidate tick limit exceeded")
    return tuple(
        (0.0 if k == 0 else float(np.float32(float(k) * step)))
        for k in range(low, high + 1))


def _label(value, step):
    """Readable Qt label, NOT a proven copy of native 007B2090."""
    v = _finite(value, "tick value")
    s = _finite(step, "tick spacing")
    if abs(v) < max(1e-9, s * 1e-6):
        return "0"
    if abs(v - round(v)) < max(1e-7, abs(v) * 1e-7):
        return str(int(round(v)))
    text = f"{v:.7g}"
    return "0" if text in ("-0", "-0.0") else text


def source_tqgrapher_grid_candidate(
        *, scr_left, scr_width, scr_bottom, scr_height,
        auto_v_spacing=ORIGINAL_SOURCE_AUTO_V_SPACING,
        auto_h_spacing=ORIGINAL_SOURCE_AUTO_H_SPACING):
    """Calculate source-grid interval and tick positions without pixels.

    Naming is Delphi-native: VLineSpacing controls vertical (frequency X)
    lines and HLineSpacing controls horizontal (amplitude Y) lines.
    """
    left = _finite(scr_left, "ScrLeft")
    width = _finite(scr_width, "ScrWidth")
    bottom = _finite(scr_bottom, "ScrBottom")
    height = _finite(scr_height, "ScrHeight")
    if not all(type(v) is int for v in (auto_v_spacing, auto_h_spacing)):
        raise ValueError("Auto spacing counts must be original Integers")
    if not (1 <= auto_v_spacing <= 100 and 1 <= auto_h_spacing <= 100):
        raise ValueError("Invalid AutoH/VSpacing")
    if width <= 0 or height <= 0:
        raise ValueError("This Qt reference needs positive screen ranges")
    if not all(np.isfinite(np.float32(v)) for v in (left, width, bottom, height)):
        raise ValueError("Screen range overflows original Delphi Single")
    # Original GetSpectrum TQGrapher stores the line spacing as Single.
    spacing_v = float(np.float32(width / auto_v_spacing))
    spacing_h = float(np.float32(height / auto_h_spacing))
    if not (math.isfinite(spacing_v) and spacing_v > 0
            and math.isfinite(spacing_h) and spacing_h > 0):
        raise ValueError("Unrepresentable original Single TQGrapher grid spacing")
    x = _index_ticks(left, left + width, spacing_v)
    y = _index_ticks(bottom, bottom + height, spacing_h)
    return {
        "source": SOURCE,
        "source_original_units_verified": True,
        "source_auto_v_spacing": auto_v_spacing,
        "source_auto_h_spacing": auto_h_spacing,
        "source_v_line_spacing_x_single": spacing_v,
        "source_h_line_spacing_y_single": spacing_h,
        "x_grid_ticks": x,
        "y_grid_ticks": y,
        "x_tick_labels_candidate": tuple(_label(v, spacing_v) for v in x),
        "y_tick_labels_candidate": tuple(_label(v, spacing_h) for v in y),
        "source_approx_index_tolerance": 0.0001,
        "original_runtime_source_grid_counts_verified": False,
        "original_rtl_tick_format_parity_verified": False,
        "original_gdi_grid_pen_color_verified": False,
        "original_runtime_tcanvas_font_verified": False,
        "original_delphi_pixel_grid_parity_verified": False,
        "native_canvas_or_dpi_inputs_used": False,
    }
