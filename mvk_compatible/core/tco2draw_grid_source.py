"""Stage111Z31F: original _Unit115 TCo2Draw source rules, not runtime pixels.

The private disassembly was read off-repository. Only derived constants and
small independent models are published here. TCo2Draw does NOT use a Win32
GDI Pen to draw its grid: it draws into TBitmap scanlines and blends RGB
pixels in software. The source TCanvas.TextOut is used only for labels.
No private PAS, IDP, measurement BIN, screenshots or original EXE here.
"""
from __future__ import annotations

import math
import numbers


SOURCE = "MVKVIEW_TCO2DRAW_GRID_AND_TCANVAS_TEXTOUT_SOURCE"
GRID_LINE_HEX = "#c0c0c0"
BACKGROUND_HEX = "#ffffff"
GRID_LINE_RGB = (192, 192, 192)
BACKGROUND_RGB = (255, 255, 255)


def source_tco2draw_grid_contract() -> dict:
    """Source-verified palette and drawing order; no Win32 runtime proof."""
    return {
        "source": SOURCE,
        "source_background_color_hex": BACKGROUND_HEX,
        "source_grid_line_color_hex": GRID_LINE_HEX,
        "source_original_grid_software_raster": True,
        "source_original_grid_is_gdi_pen": False,
        "source_tco2draw_grid_before_series": True,
        "source_tco2draw_uses_32bit_bitmap_scanline": True,
        "source_tco2draw_blend": (
            "trunc(ink+(old-ink)*min(1,sqrt(abs(line_distance))))"),
        "source_tcanvas_brush_clear_textout": True,
        "source_tcanvas_font_copied_from_input_canvas": True,
        "source_tick_textout_anchor": "source_textout_tick_anchor",
        "original_native_tcanvas_font_pixels_verified": False,
        "original_dpi_awareness_verified": False,
        "original_original_vs_qt_software_antialias_pixels_verified": False,
    }


def _rgb(value: tuple[int, int, int], name: str) -> tuple[int, int, int]:
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(isinstance(v, bool) or
                not isinstance(v, numbers.Integral) or
                not 0 <= v <= 255 for v in value)):
        raise ValueError(name + " must be exactly three 8-bit RGB channels")
    return tuple(int(v) for v in value)


def source_tco2draw_blend_rgb(
        ink: tuple[int, int, int], old: tuple[int, int, int],
        perpendicular_distance: float) -> tuple[int, int, int]:
    """One 007C9808 pixel, given distance from source line rasterizer.

    007C98B4/007C9A30 calculate sqrt(abs(distance)) then call 007C9808.
    007C9808 starts from INK and blends towards OLD by that factor,
    caps it at 1, and @TRUNCs each channel independently. This is the
    source colour arithmetic only; actual pixel selection/coordinates and
    native FPU tie cases are not independently runtime verified.
    """
    ink = _rgb(ink, "ink")
    old = _rgb(old, "old")
    if isinstance(perpendicular_distance, bool) or not isinstance(
            perpendicular_distance, numbers.Real):
        raise ValueError("perpendicular_distance must be real")
    value = float(perpendicular_distance)
    if not math.isfinite(value):
        raise ValueError("perpendicular_distance must be finite")
    factor = min(1.0, math.sqrt(abs(value)))
    return tuple(int(a + (b - a) * factor) for a, b in zip(ink, old))


def source_textout_tick_anchor(
        *, axis: str, projected_pixel: float,
        text_width: int, pixel_left: int, pixel_bottom: int,
        text_offset: int) -> tuple[int, int]:
    """Source placement of tick TextOut, not Qt AxisItem placement.

    _Unit115 007CAE0D..007CAE29: Y tick text is left of PixelLeft;
    007CAF3B..007CAF5F: X tick text centered under PixelBottom.
    Text widths and TextOffset are ORIGINAL TCanvas runtime inputs,
    unknown until measured. Python round is only a native @ROUND model.
    """
    for name, n in (("text_width", text_width), ("pixel_left", pixel_left),
                    ("pixel_bottom", pixel_bottom), ("text_offset", text_offset)):
        if isinstance(n, bool) or not isinstance(n, numbers.Integral):
            raise ValueError(name + " must be an integer")
    if text_width < 0 or text_offset < 0:
        raise ValueError("text_width and text_offset must be nonnegative")
    if isinstance(projected_pixel, bool) or not isinstance(
            projected_pixel, numbers.Real):
        raise ValueError("projected_pixel must be a finite real")
    pixel = float(projected_pixel)
    if not math.isfinite(pixel) or abs(pixel) > 1e8:
        raise ValueError("projected_pixel out of supported range")
    coord = round(pixel)  # @ROUND tie behaviour of native FPU is still OPEN.
    if axis == "frequency_x":
        return (coord - text_width // 2, pixel_bottom + text_offset)
    if axis == "amplitude_y":
        return (pixel_left - text_width - text_offset,
                coord - text_offset)
    raise ValueError("axis must be frequency_x or amplitude_y")
